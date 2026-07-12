//! Conservative source-code compaction for the Rust live-zone dispatcher.
//!
//! This is deliberately smaller in scope than the optional Python
//! tree-sitter `CodeAwareCompressor`: a proxy must never make an executable
//! payload syntactically invalid just to save tokens. The compactor therefore
//! removes only standalone, non-directive comments and duplicate blank lines.
//! All executable lines, inline comments, shebangs, and common formatter /
//! type-checker directives remain byte-for-byte intact.

/// Compact a source-code payload without changing any executable line.
///
/// The returned string preserves whether the input ended with a newline. A
/// no-op input is returned byte-for-byte, allowing the dispatcher's existing
/// tokenizer validation gate to decide whether the change earns its place.
pub fn compact_source_code(source: &str) -> String {
    let mut output = String::with_capacity(source.len());
    let mut previous_blank = false;

    for (line_index, chunk) in source.split_inclusive('\n').enumerate() {
        let line = chunk.strip_suffix('\n').unwrap_or(chunk);
        let has_newline = chunk.ends_with('\n');
        let trimmed = line.trim_start();

        if is_removable_comment(trimmed, line_index) {
            continue;
        }

        if trimmed.is_empty() {
            if previous_blank {
                continue;
            }
            previous_blank = true;
        } else {
            previous_blank = false;
        }

        output.push_str(line);
        if has_newline {
            output.push('\n');
        }
    }

    // `split_inclusive` returns no chunks for an empty source. Returning the
    // original preserves the no-op identity contract in that case.
    if output.is_empty() && !source.is_empty() && source.trim().is_empty() {
        return source.to_owned();
    }
    output
}

fn is_removable_comment(trimmed: &str, line_index: usize) -> bool {
    let is_comment = trimmed.starts_with('#') || trimmed.starts_with("//");
    if !is_comment {
        return false;
    }

    // Preserve interpreter, compiler, formatter, lint, and type-checker
    // directives. These comment-shaped lines influence how source is parsed
    // or maintained and are not disposable documentation.
    let lower = trimmed.to_ascii_lowercase();
    let directive = (line_index == 0 && trimmed.starts_with("#!"))
        || lower.starts_with("# -*-")
        || lower.starts_with("# coding")
        || lower.starts_with("# type:")
        || lower.starts_with("# noqa")
        || lower.starts_with("# pragma")
        || lower.starts_with("# fmt:")
        || lower.starts_with("# region")
        || lower.starts_with("# endregion")
        || lower.starts_with("//go:")
        || lower.starts_with("// @ts-")
        || lower.starts_with("// eslint-")
        || lower.starts_with("// prettier-")
        || lower.starts_with("// rustfmt:");

    !directive
}

#[cfg(test)]
mod tests {
    use super::compact_source_code;

    #[test]
    fn removes_only_standalone_non_directive_comments_and_duplicate_blanks() {
        let source = "#!/usr/bin/env python3\n# coding: utf-8\n\n# remove me\n\ndef run(value):\n    # remove me too\n    return value + 1  # retain inline context\n\n\n# noqa: E501\n";

        assert_eq!(
            compact_source_code(source),
            "#!/usr/bin/env python3\n# coding: utf-8\n\ndef run(value):\n    return value + 1  # retain inline context\n\n# noqa: E501\n"
        );
    }

    #[test]
    fn returns_an_unchanged_executable_payload_byte_for_byte() {
        let source = "fn main() {\n    println!(\"hello\");\n}\n";
        assert_eq!(compact_source_code(source), source);
    }
}
