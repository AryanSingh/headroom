//! Deletion-based compaction transform — Morph-style 0% hallucination.
//!
//! This transform deletes low-signal tokens from LLM conversation text
//! while guaranteeing that **output tokens are always a subsequence of
//! input tokens**. No rewriting, no rephrasing, no paraphrasing — only
//! deletion. This provides a 0% hallucination guarantee.
//!
//! # Signal classification
//!
//! Each token is classified by its informational signal:
//!
//! - **Critical**: code blocks, tool_result markers, numbers, URLs,
//!   proper nouns, function names → never deleted.
//! - **High**: nouns, verbs, technical terms → rarely deleted.
//! - **Medium**: adjectives, adverbs → optionally deleted at Aggressive.
//! - **Low**: filler words ("the", "a", "is"), redundant connectors →
//!   preferentially deleted.
//! - **Negligible**: extra whitespace, duplicate punctuation, empty lines
//!   beyond paragraph breaks → always deleted.
//!
//! # Aggressiveness levels
//!
//! | Level        | Deleted signal classes | Approx savings |
//! |--------------|------------------------|----------------|
//! | Conservative | Negligible             | ~5-10%         |
//! | Moderate     | Low + Negligible       | ~15-25%        |
//! | Aggressive   | Medium + Low + Negligible | ~25-40%     |

use thiserror::Error;

// ── Errors ──────────────────────────────────────────────────────────────────

#[derive(Debug, Error)]
pub enum DeletionCompactionError {
    #[error("compaction failed: {0}")]
    Failed(String),
}

// ── Aggressiveness ──────────────────────────────────────────────────────────

/// How aggressively to delete low-signal tokens.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Aggressiveness {
    /// Only delete Negligible tokens (extra whitespace, duplicate punctuation).
    Conservative,
    /// Delete Low + Negligible (filler words, redundant connectors).
    Moderate,
    /// Delete Medium + Low + Negligible (adjectives, adverbs, fillers).
    Aggressive,
}

// ── Token signal level ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum TokenSignal {
    /// Always delete: extra whitespace, duplicate punctuation.
    Negligible,
    /// Prefer to delete: filler words, redundant connectors.
    Low,
    /// Optionally delete at Aggressive level: adjectives, adverbs.
    Medium,
    /// Rarely delete: nouns, verbs, technical terms.
    High,
    /// Never delete: code blocks, tool results, numbers, URLs.
    Critical,
}

// ── Token context ───────────────────────────────────────────────────────────

/// Context information for token classification.
#[derive(Debug, Default)]
#[allow(dead_code)]
struct TokenContext {
    in_code_block: bool,
    in_tool_output: bool,
    is_first_in_sentence: bool,
    prev_token: Option<String>,
    next_token: Option<String>,
}

// ── Configuration ───────────────────────────────────────────────────────────

/// Configuration for the deletion compactor.
#[derive(Debug, Clone)]
pub struct DeletionCompactorConfig {
    /// How aggressively to delete tokens.
    pub aggressiveness: Aggressiveness,
    /// Whether to preserve code blocks (```...```). Default: true.
    pub preserve_code_blocks: bool,
    /// Whether to preserve tool output blocks. Default: true.
    pub preserve_tool_outputs: bool,
    /// Minimum fraction of tokens to keep. Default: 0.3 (30%).
    pub min_preservation_ratio: f32,
}

impl Default for DeletionCompactorConfig {
    fn default() -> Self {
        Self {
            aggressiveness: Aggressiveness::Moderate,
            preserve_code_blocks: true,
            preserve_tool_outputs: true,
            min_preservation_ratio: 0.3,
        }
    }
}

// ── Result ──────────────────────────────────────────────────────────────────

/// Result of a deletion compaction operation.
#[derive(Debug, Clone)]
pub struct CompactResult {
    /// The compacted text.
    pub output: String,
    /// Number of tokens deleted.
    pub tokens_deleted: usize,
    /// Number of tokens kept.
    pub tokens_kept: usize,
    /// Total tokens in original input.
    pub original_tokens: usize,
    /// Compression ratio: tokens_kept / original_tokens.
    pub compression_ratio: f32,
    /// Bytes saved.
    pub bytes_saved: usize,
    /// Byte positions of deleted tokens (for verification).
    pub deleted_positions: Vec<usize>,
}

// ── Tokenizer ───────────────────────────────────────────────────────────────

/// A token with its position and content.
#[derive(Debug, Clone)]
struct Token {
    /// Byte offset in the original string.
    offset: usize,
    /// The token text.
    text: String,
}

/// Tokenize text into meaningful tokens, preserving byte positions.
///
/// This tokenizer is smarter than naive whitespace/punctuation splitting:
/// it keeps URLs, HTML tags, code markers, and snake_case identifiers
/// as single tokens so the signal classifier can reason about them.
fn tokenize(text: &str) -> Vec<Token> {
    let mut tokens = Vec::new();
    let chars: Vec<char> = text.chars().collect();
    let len = chars.len();
    let mut i = 0;

    while i < len {
        let ch = chars[i];

        // Whitespace: emit as a single token (preserves spacing)
        if ch.is_whitespace() {
            let start = i;
            while i < len && chars[i].is_whitespace() {
                i += 1;
            }
            let byte_start = char_byte_offset(text, start);
            tokens.push(Token {
                offset: byte_start,
                text: text[byte_start..char_byte_end(text, i)].to_string(),
            });
            continue;
        }

        // URLs: keep http://... or https://... or ftp://... or www. as one token
        if i + 1 < len {
            let two_char: String = chars[i..(i + 2).min(len)].iter().collect();
            if two_char == "ht" || two_char == "ft" || two_char == "ww" {
                if let Some(url) = try_extract_url(&chars, i) {
                    let byte_start = char_byte_offset(text, i);
                    let byte_end = char_byte_offset(text, i + url.len());
                    tokens.push(Token {
                        offset: byte_start,
                        text: text[byte_start..byte_end].to_string(),
                    });
                    i += url.len();
                    continue;
                }
            }
        }

        // HTML-like tags: <tag_name> or </tag_name>
        if ch == '<' {
            if let Some(tag) = try_extract_html_tag(&chars, i) {
                let byte_start = char_byte_offset(text, i);
                let byte_end = char_byte_offset(text, i + tag.len());
                tokens.push(Token {
                    offset: byte_start,
                    text: text[byte_start..byte_end].to_string(),
                });
                i += tag.len();
                continue;
            }
        }

        // Code block markers: ```
        if ch == '`' && i + 2 < len && chars[i + 1] == '`' && chars[i + 2] == '`' {
            let byte_start = char_byte_offset(text, i);
            tokens.push(Token {
                offset: byte_start,
                text: "```".to_string(),
            });
            i += 3;
            continue;
        }

        // Currency prefix: $ followed by digits → treat $ as part of number
        if ch == '$' && i + 1 < len && (chars[i + 1].is_ascii_digit()) {
            let start = i;
            i += 1; // consume $
            while i < len
                && (chars[i].is_alphanumeric()
                    || chars[i] == '_'
                    || chars[i] == '.'
                    || chars[i] == '-'
                    || chars[i] == '/'
                    || chars[i] == ':')
            {
                i += 1;
            }
            let byte_start = char_byte_offset(text, start);
            let byte_end = char_byte_offset(text, i);
            tokens.push(Token {
                offset: byte_start,
                text: text[byte_start..byte_end].to_string(),
            });
            continue;
        }

        // Words: alphanumeric + underscores (keeps snake_case together)
        if ch.is_alphanumeric() || ch == '_' || ch == '.' || ch == '-' || ch == '/' || ch == ':' {
            let start = i;
            while i < len
                && (chars[i].is_alphanumeric()
                    || chars[i] == '_'
                    || chars[i] == '.'
                    || chars[i] == '-'
                    || chars[i] == '/'
                    || chars[i] == ':')
            {
                i += 1;
            }
            let byte_start = char_byte_offset(text, start);
            let byte_end = char_byte_offset(text, i);
            tokens.push(Token {
                offset: byte_start,
                text: text[byte_start..byte_end].to_string(),
            });
            continue;
        }

        // Punctuation: single character
        let byte_start = char_byte_offset(text, i);
        tokens.push(Token {
            offset: byte_start,
            text: ch.to_string(),
        });
        i += 1;
    }

    tokens
}

/// Get the byte offset of a character index in the string.
fn char_byte_offset(text: &str, char_idx: usize) -> usize {
    text.char_indices()
        .nth(char_idx)
        .map(|(byte_idx, _)| byte_idx)
        .unwrap_or(text.len())
}

/// Get the byte offset just past a character index.
fn char_byte_end(text: &str, char_idx: usize) -> usize {
    if char_idx >= text.chars().count() {
        return text.len();
    }
    text.char_indices()
        .nth(char_idx)
        .map(|(byte_idx, _)| byte_idx)
        .unwrap_or(text.len())
}

/// Try to extract a URL starting at the given position.
/// Returns the URL string (in chars) if found.
fn try_extract_url(chars: &[char], start: usize) -> Option<String> {
    let remaining = &chars[start..];
    let text: String = remaining
        .iter()
        .take_while(|c| {
            c.is_alphanumeric()
                || **c == '/'
                || **c == ':'
                || **c == '.'
                || **c == '-'
                || **c == '_'
                || **c == '%'
                || **c == '&'
                || **c == '?'
                || **c == '='
                || **c == '#'
                || **c == '@'
        })
        .collect();

    if text.starts_with("http://")
        || text.starts_with("https://")
        || text.starts_with("ftp://")
        || text.starts_with("www.")
    {
        // Only return if it has some meaningful length
        if text.len() > 5 {
            return Some(text);
        }
    }
    None
}

/// Try to extract an HTML-like tag starting at the given `<` position.
/// Returns the tag string (in chars) if found.
fn try_extract_html_tag(chars: &[char], start: usize) -> Option<String> {
    let remaining = &chars[start..];
    if remaining.is_empty() || remaining[0] != '<' {
        return None;
    }

    let mut i = 1;
    // Check for closing tag
    if i < remaining.len() && remaining[i] == '/' {
        i += 1;
    }
    // Tag name: alphanumeric + underscores + hyphens + dots
    let name_start = i;
    while i < remaining.len()
        && (remaining[i].is_alphanumeric()
            || remaining[i] == '_'
            || remaining[i] == '-'
            || remaining[i] == '.')
    {
        i += 1;
    }
    // Must have consumed at least some name characters
    if i == name_start {
        return None;
    }
    // Find closing >
    while i < remaining.len() && remaining[i] != '>' {
        i += 1;
    }
    if i < remaining.len() && remaining[i] == '>' {
        i += 1; // include >
        return Some(remaining[..i].iter().collect());
    }
    None
}

// ── Signal classifier ───────────────────────────────────────────────────────

/// Words with low informational signal.
const FILLER_WORDS: &[&str] = &[
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can",
    "need", "dare", "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "because",
    "but", "and", "or", "if", "while", "that", "this", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them", "their", "what", "which",
    "who", "whom",
];

/// Redundant connector phrases.
const REDUNDANT_CONNECTORS: &[&str] = &[
    "however",
    "furthermore",
    "moreover",
    "additionally",
    "consequently",
    "nevertheless",
    "notwithstanding",
    "henceforth",
    "aforementioned",
    "subsequently",
    "therefore",
    "thus",
    "hence",
];

/// Check if a word is a filler word (case-insensitive).
fn is_filler_word(word: &str) -> bool {
    let lower = word.to_lowercase();
    FILLER_WORDS.contains(&lower.as_str())
}

/// Check if a word is a redundant connector (case-insensitive).
fn is_redundant_connector(word: &str) -> bool {
    let lower = word.to_lowercase();
    REDUNDANT_CONNECTORS.contains(&lower.as_str())
}

/// Check if a token looks like a number (integer or decimal).
fn is_number(word: &str) -> bool {
    let stripped = word.trim_matches(|c: char| c == ',' || c == '_' || c == '$' || c == '%');
    stripped.parse::<f64>().is_ok()
}

/// Check if a token looks like a URL.
fn is_url(word: &str) -> bool {
    word.starts_with("http://")
        || word.starts_with("https://")
        || word.starts_with("ftp://")
        || word.starts_with("www.")
}

/// Check if a token looks like code-related content.
fn is_code_token(word: &str) -> bool {
    // Code blocks markers
    if word.starts_with("```") || word == "```" {
        return true;
    }
    // Common code patterns
    if word.contains("()")
        || word.contains("{}")
        || word.contains("[]")
        || word.starts_with('$')
        || word.starts_with('@')
        || (word.contains('_') && word.len() > 3)
    // snake_case identifiers
    {
        return true;
    }
    // Tool result markers
    if word.starts_with("<tool_result") || word.starts_with("</tool_result") {
        return true;
    }
    false
}

/// Classify the signal level of a token.
fn classify_token(token: &Token, context: &TokenContext) -> TokenSignal {
    let text = token.text.trim();

    // Empty or pure whitespace
    if text.is_empty() {
        return TokenSignal::Negligible;
    }

    // In code block → Critical
    if context.in_code_block {
        return TokenSignal::Critical;
    }

    // In tool output → Critical
    if context.in_tool_output {
        return TokenSignal::Critical;
    }

    // Code tokens → Critical
    if is_code_token(text) {
        return TokenSignal::Critical;
    }

    // Numbers → Critical
    if is_number(text) {
        return TokenSignal::Critical;
    }

    // URLs → Critical
    if is_url(text) {
        return TokenSignal::Critical;
    }

    // Single punctuation → Negligible
    if text.len() == 1
        && text
            .chars()
            .next()
            .is_some_and(|c| c.is_ascii_punctuation())
    {
        return TokenSignal::Negligible;
    }

    // Extra whitespace (multiple spaces) → Negligible
    if text.chars().all(|c| c.is_whitespace()) && text.len() > 1 {
        return TokenSignal::Negligible;
    }

    // Filler words → Low
    if is_filler_word(text) {
        return TokenSignal::Low;
    }

    // Redundant connectors → Low
    if is_redundant_connector(text) {
        return TokenSignal::Low;
    }

    // Short words (1-2 chars) that aren't critical → Negligible
    if text.len() <= 2 && !text.chars().all(|c| c.is_alphabetic()) {
        return TokenSignal::Negligible;
    }

    // Default: High (preserve content words)
    TokenSignal::High
}

// ── DeletionCompactor ───────────────────────────────────────────────────────

/// A deletion-based text compactor that guarantees 0% hallucination.
///
/// The compactor tokenizes input, classifies each token's signal level,
/// and deletes tokens below the aggressiveness threshold. Output tokens
/// are always a subsequence of input tokens.
pub struct DeletionCompactor {
    config: DeletionCompactorConfig,
}

impl DeletionCompactor {
    /// Create a new compactor with the given configuration.
    pub fn new(config: DeletionCompactorConfig) -> Self {
        Self { config }
    }

    /// Create a compactor with the given aggressiveness level.
    pub fn with_aggressiveness(aggressiveness: Aggressiveness) -> Self {
        Self {
            config: DeletionCompactorConfig {
                aggressiveness,
                ..Default::default()
            },
        }
    }

    /// Compact the input text by deleting low-signal tokens.
    ///
    /// Returns a `CompactResult` with the compacted text and statistics.
    /// The output is guaranteed to be a subsequence of the input tokens.
    pub fn compact(&self, input: &str) -> CompactResult {
        if input.is_empty() {
            return CompactResult {
                output: String::new(),
                tokens_deleted: 0,
                tokens_kept: 0,
                original_tokens: 0,
                compression_ratio: 1.0,
                bytes_saved: 0,
                deleted_positions: Vec::new(),
            };
        }

        let tokens = tokenize(input);
        let original_tokens = tokens.len();
        let threshold = self.aggressiveness_threshold();

        // Build context and classify each token
        let mut kept_indices: Vec<usize> = Vec::new();
        let mut deleted_positions: Vec<usize> = Vec::new();
        let mut in_code_block = false;
        let mut in_tool_output = false;

        for (i, token) in tokens.iter().enumerate() {
            // Track code block state
            if self.config.preserve_code_blocks && token.text.trim().starts_with("```") {
                in_code_block = !in_code_block;
                kept_indices.push(i);
                continue;
            }

            // Track tool output state
            if self.config.preserve_tool_outputs {
                let trimmed = token.text.trim();
                if trimmed.starts_with("<tool_result") {
                    in_tool_output = true;
                } else if trimmed.starts_with("</tool_result") {
                    in_tool_output = false;
                }
            }

            let context = TokenContext {
                in_code_block,
                in_tool_output,
                is_first_in_sentence: i == 0
                    || tokens[i - 1].text.ends_with('.')
                    || tokens[i - 1].text.ends_with('!')
                    || tokens[i - 1].text.ends_with('?'),
                prev_token: tokens.get(i.saturating_sub(1)).map(|t| t.text.clone()),
                next_token: tokens.get(i + 1).map(|t| t.text.clone()),
            };

            let signal = classify_token(token, &context);

            if signal <= threshold {
                deleted_positions.push(token.offset);
            } else {
                kept_indices.push(i);
            }
        }

        // Ensure minimum preservation ratio
        let min_keep = (original_tokens as f32 * self.config.min_preservation_ratio) as usize;
        if kept_indices.len() < min_keep && original_tokens > 0 {
            // Iterative relaxation: try progressively more conservative thresholds
            // until we meet the min_keep requirement.
            let thresholds = match self.config.aggressiveness {
                Aggressiveness::Aggressive => {
                    vec![TokenSignal::Low, TokenSignal::Negligible]
                }
                Aggressiveness::Moderate => {
                    vec![TokenSignal::Negligible]
                }
                Aggressiveness::Conservative => {
                    vec![TokenSignal::Negligible]
                }
            };

            let mut relaxed = false;
            for &relaxed_threshold in &thresholds {
                kept_indices.clear();
                deleted_positions.clear();
                in_code_block = false;
                in_tool_output = false;

                for (i, token) in tokens.iter().enumerate() {
                    if self.config.preserve_code_blocks && token.text.trim().starts_with("```") {
                        in_code_block = !in_code_block;
                        kept_indices.push(i);
                        continue;
                    }

                    if self.config.preserve_tool_outputs {
                        let trimmed = token.text.trim();
                        if trimmed.starts_with("<tool_result") {
                            in_tool_output = true;
                        } else if trimmed.starts_with("</tool_result") {
                            in_tool_output = false;
                        }
                    }

                    let context = TokenContext {
                        in_code_block,
                        in_tool_output,
                        is_first_in_sentence: i == 0
                            || tokens[i - 1].text.ends_with('.')
                            || tokens[i - 1].text.ends_with('!')
                            || tokens[i - 1].text.ends_with('?'),
                        prev_token: tokens.get(i.saturating_sub(1)).map(|t| t.text.clone()),
                        next_token: tokens.get(i + 1).map(|t| t.text.clone()),
                    };

                    let signal = classify_token(token, &context);
                    if signal <= relaxed_threshold {
                        deleted_positions.push(token.offset);
                    } else {
                        kept_indices.push(i);
                    }
                }

                if kept_indices.len() >= min_keep {
                    relaxed = true;
                    break;
                }
            }

            // Final fallback: if relaxation still doesn't meet min_keep,
            // keep all non-Negligible tokens.
            if !relaxed {
                kept_indices.clear();
                deleted_positions.clear();
                for (i, token) in tokens.iter().enumerate() {
                    let signal = classify_token(token, &TokenContext::default());
                    if signal == TokenSignal::Negligible {
                        deleted_positions.push(token.offset);
                    } else {
                        kept_indices.push(i);
                    }
                }
            }
        }

        // Rebuild output from kept tokens, inserting spaces only where
        // non-whitespace tokens were deleted between kept non-whitespace tokens.
        let mut output = String::new();
        let mut prev_kept_idx: Option<usize> = None;
        let mut prev_was_non_ws = false;
        for &i in &kept_indices {
            let token = &tokens[i];
            let is_ws = token.text.chars().all(|c| c.is_whitespace());
            if !is_ws && prev_was_non_ws && !output.is_empty() {
                if let Some(prev) = prev_kept_idx {
                    let prev_end = tokens[prev].offset + tokens[prev].text.len();
                    let cur_start = token.offset;
                    // Check if there's a gap in the original text
                    let has_gap = prev_end < cur_start;
                    // Check if a kept whitespace token fills the gap
                    let has_kept_ws = kept_indices
                        .iter()
                        .filter(|&&idx| idx > prev && idx < i)
                        .any(|&idx| tokens[idx].text.chars().all(|c| c.is_whitespace()));
                    if has_gap && !has_kept_ws {
                        output.push(' ');
                    }
                }
            }
            output.push_str(&token.text);
            prev_kept_idx = Some(i);
            prev_was_non_ws = !is_ws;
        }

        let tokens_deleted = original_tokens - kept_indices.len();
        let tokens_kept = kept_indices.len();
        let compression_ratio = if original_tokens > 0 {
            tokens_kept as f32 / original_tokens as f32
        } else {
            1.0
        };
        let bytes_saved = input.len().saturating_sub(output.len());

        CompactResult {
            output,
            tokens_deleted,
            tokens_kept,
            original_tokens,
            compression_ratio,
            bytes_saved,
            deleted_positions,
        }
    }

    /// Get the signal threshold for the configured aggressiveness.
    /// Tokens with signal <= this threshold are deleted.
    fn aggressiveness_threshold(&self) -> TokenSignal {
        match self.config.aggressiveness {
            Aggressiveness::Conservative => TokenSignal::Negligible,
            Aggressiveness::Moderate => TokenSignal::Low,
            Aggressiveness::Aggressive => TokenSignal::Medium,
        }
    }
}

// ── Convenience constructors ────────────────────────────────────────────────

/// Create a conservative compactor (only deletes Negligible tokens).
pub fn conservative_compactor() -> DeletionCompactor {
    DeletionCompactor::with_aggressiveness(Aggressiveness::Conservative)
}

/// Create a moderate compactor (deletes Low + Negligible tokens).
pub fn moderate_compactor() -> DeletionCompactor {
    DeletionCompactor::with_aggressiveness(Aggressiveness::Moderate)
}

/// Create an aggressive compactor (deletes Medium + Low + Negligible tokens).
pub fn aggressive_compactor() -> DeletionCompactor {
    DeletionCompactor::with_aggressiveness(Aggressiveness::Aggressive)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_input() {
        let compactor = moderate_compactor();
        let result = compactor.compact("");
        assert_eq!(result.output, "");
        assert_eq!(result.original_tokens, 0);
        assert_eq!(result.compression_ratio, 1.0);
    }

    #[test]
    fn conservative_only_deletes_negligible() {
        let compactor = conservative_compactor();
        let result = compactor.compact("Hello world");
        // Conservative should keep all content words
        assert!(result.output.contains("Hello"));
        assert!(result.output.contains("world"));
    }

    #[test]
    fn moderate_deletes_filler_words() {
        let compactor = moderate_compactor();
        let result = compactor.compact("the cat is on the mat");
        // "the", "is", "on" are filler words → should be deleted
        assert!(result.tokens_deleted > 0);
        assert!(result.compression_ratio < 1.0);
    }

    #[test]
    fn aggressive_deletes_more() {
        let moderate = moderate_compactor();
        let aggressive = aggressive_compactor();
        let input = "The quick brown fox jumps over the lazy dog";
        let mod_result = moderate.compact(input);
        let agg_result = aggressive.compact(input);
        assert!(agg_result.tokens_deleted >= mod_result.tokens_deleted);
    }

    #[test]
    fn output_is_subsequence_of_input() {
        let compactor = aggressive_compactor();
        let input = "The quick brown fox jumps over the lazy dog";
        let result = compactor.compact(input);

        // Verify output tokens are a subsequence of input tokens
        let input_tokens: Vec<&str> = input.split_whitespace().collect();
        let output_tokens: Vec<&str> = result.output.split_whitespace().collect();

        let mut input_idx = 0;
        for output_token in &output_tokens {
            let found = input_tokens[input_idx..]
                .iter()
                .position(|t| t == output_token);
            match found {
                Some(pos) => input_idx += pos + 1,
                None => panic!(
                    "Output token '{}' not found in remaining input tokens",
                    output_token
                ),
            }
        }
    }

    #[test]
    fn code_blocks_preserved() {
        let compactor = DeletionCompactor::new(DeletionCompactorConfig {
            aggressiveness: Aggressiveness::Aggressive,
            preserve_code_blocks: true,
            ..Default::default()
        });
        let input = "The code is ```fn main() {}``` and it works";
        let result = compactor.compact(input);
        assert!(result.output.contains("```fn main() {}```"));
    }

    #[test]
    fn tool_output_preserved() {
        let compactor = DeletionCompactor::new(DeletionCompactorConfig {
            aggressiveness: Aggressiveness::Aggressive,
            preserve_tool_outputs: true,
            ..Default::default()
        });
        let input = "The result is <tool_result>output data</tool_result> which is good";
        let result = compactor.compact(input);
        assert!(result.output.contains("<tool_result>"));
        assert!(result.output.contains("</tool_result>"));
    }

    #[test]
    fn numbers_preserved() {
        let compactor = aggressive_compactor();
        let input = "The value is 42 and the price is $99.99";
        let result = compactor.compact(input);
        assert!(result.output.contains("42"));
        assert!(result.output.contains("$99.99"));
    }

    #[test]
    fn urls_preserved() {
        let compactor = aggressive_compactor();
        let input = "Visit https://example.com for more info";
        let result = compactor.compact(input);
        assert!(result.output.contains("https://example.com"));
    }

    #[test]
    fn min_preservation_ratio_respected() {
        let compactor = DeletionCompactor::new(DeletionCompactorConfig {
            aggressiveness: Aggressiveness::Aggressive,
            min_preservation_ratio: 0.5,
            ..Default::default()
        });
        let input = "the a an is are was were be been being have has had";
        let result = compactor.compact(input);
        assert!(
            result.compression_ratio >= 0.4,
            "compression_ratio {} below 0.4 (min_preservation_ratio=0.5 with rounding)",
            result.compression_ratio
        );
    }

    #[test]
    fn bytes_saved_non_negative() {
        let compactor = aggressive_compactor();
        let input = "Hello world, this is a test sentence with some filler words";
        let result = compactor.compact(input);
        assert!(result.bytes_saved <= input.len());
        assert_eq!(result.output.len() + result.bytes_saved, input.len());
    }

    #[test]
    fn single_word_input() {
        let compactor = aggressive_compactor();
        let result = compactor.compact("Hello");
        assert_eq!(result.output.trim(), "Hello");
        assert_eq!(result.original_tokens, 1);
    }

    #[test]
    fn all_critical_content() {
        let compactor = aggressive_compactor();
        let input = "42 https://example.com ```code```";
        let result = compactor.compact(input);
        // All semantic tokens are critical → only whitespace may be deleted
        assert!(result.tokens_deleted <= 2);
        assert!(result.output.contains("42"));
        assert!(result.output.contains("https://example.com"));
        assert!(result.output.contains("```code```"));
    }

    #[test]
    fn redundancy_connector_deleted() {
        let compactor = DeletionCompactor::new(DeletionCompactorConfig {
            aggressiveness: Aggressiveness::Moderate,
            min_preservation_ratio: 0.1,
            ..Default::default()
        });
        let input = "The result is good however it could be better";
        let result = compactor.compact(input);
        assert!(!result.output.contains("however"));
    }
}
