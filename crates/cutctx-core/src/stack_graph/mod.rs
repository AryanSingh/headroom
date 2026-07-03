//! Stack-graph-based cross-file code navigation.
//!
//! Builds stack graphs by walking tree-sitter ASTs and creating the
//! corresponding stack graph nodes (scopes, push-symbol, pop-symbol)
//! directly.  TSG rule files serve as executable specifications of the
//! graph structure and are embedded for reference.

use std::collections::{HashMap, HashSet, VecDeque};
use std::path::{Path, PathBuf};

use stack_graphs::arena::Handle;
use stack_graphs::graph::{File, Node, StackGraph, Symbol as SgSymbol};
use stack_graphs::partial::PartialPaths;
use streaming_iterator::StreamingIterator;
use tree_sitter::Language as TsLanguage;

// ---------------------------------------------------------------------------
// Language aliases
// ---------------------------------------------------------------------------

/// Aliases mapping file extensions to tree-sitter language IDs.
const LANGUAGE_ALIASES: &[(&str, &str)] = &[
    ("py", "python"),
    ("js", "javascript"),
    ("jsx", "jsx"),
    ("ts", "typescript"),
    ("tsx", "tsx"),
    ("rs", "rust"),
    ("go", "go"),
    ("java", "java"),
    ("c", "c"),
    ("cpp", "cpp"),
];

// ---------------------------------------------------------------------------
// ResolvedReference
// ---------------------------------------------------------------------------

/// Result of resolving a single reference.
#[derive(Debug, Clone)]
pub struct ResolvedReference {
    pub target_file: String,
    pub target_line: usize,
    pub target_column: usize,
    pub symbol_name: String,
    pub confidence: f64,
}

// ---------------------------------------------------------------------------
// StackGraphManager
// ---------------------------------------------------------------------------

/// Manages a stack graph for code navigation across files.
pub struct StackGraphManager {
    graph: StackGraph,
    partial_paths: PartialPaths,
    parsers: HashMap<String, tree_sitter::Parser>,
    file_handles: HashMap<PathBuf, Handle<File>>,
    /// Cached source content for each indexed file.
    /// Used to rebuild the entire graph when a file is reindexed or removed,
    /// since `stack_graphs::StackGraph` has no individual file removal API.
    source_cache: HashMap<PathBuf, String>,
}

impl StackGraphManager {
    /// Create a new, empty stack graph manager.
    pub fn new() -> Self {
        Self {
            graph: StackGraph::new(),
            partial_paths: PartialPaths::new(),
            parsers: HashMap::new(),
            file_handles: HashMap::new(),
            source_cache: HashMap::new(),
        }
    }

    // -----------------------------------------------------------------------
    // Language registration
    // -----------------------------------------------------------------------

    /// Register a language (load its grammar). Returns `false` if unsupported.
    pub fn register_language(&mut self, language: &str) -> bool {
        if self.parsers.contains_key(language) {
            return true;
        }
        let grammar = match language {
            "python" => tree_sitter_python::LANGUAGE,
            "javascript" | "jsx" | "typescript" | "tsx" => tree_sitter_javascript::LANGUAGE,
            _ => return false,
        };
        let mut parser = tree_sitter::Parser::new();
        if parser.set_language(&grammar.into()).is_err() {
            return false;
        }
        self.parsers.insert(language.to_string(), parser);
        true
    }

    /// Resolve a language name to a `tree_sitter::Language` value.
    fn resolve_language(language: &str) -> Option<TsLanguage> {
        match language {
            "python" => Some(tree_sitter_python::LANGUAGE.into()),
            "javascript" | "jsx" => Some(tree_sitter_javascript::LANGUAGE.into()),
            "typescript" | "tsx" => Some(tree_sitter_javascript::LANGUAGE.into()),
            _ => None,
        }
    }

    // -----------------------------------------------------------------------
    // File addition / removal / reindex
    // -----------------------------------------------------------------------

    /// Add a source file to the stack graph.
    ///
    /// Parses the source, creates a file-level scope, then walks the concrete
    /// syntax tree to create definition and reference nodes per the embedded
    /// TSG rule specification for the detected language.
    pub fn add_file(&mut self, path: &str, source: &str) -> Result<(), String> {
        let file_path = Path::new(path);
        let ext = file_path.extension().and_then(|e| e.to_str()).unwrap_or("");
        let language = LANGUAGE_ALIASES
            .iter()
            .find(|(alias, _)| *alias == ext)
            .map(|(_, lang)| *lang)
            .unwrap_or("python");

        if !self.register_language(language) {
            return Err(format!(
                "Unsupported language: {} (file: {})",
                language, path
            ));
        }

        // Reject duplicate files
        if self.file_handles.contains_key(file_path) {
            return Err(format!("File already exists: {}", path));
        }

        let file_handle = self
            .graph
            .add_file(path)
            .map_err(|_| format!("File already exists: {}", path))?;

        // Parse the source into a CST
        let parser = self.parsers.get_mut(language).unwrap();
        let tree = parser
            .parse(source, None)
            .ok_or_else(|| format!("Failed to parse: {}", path))?;

        // --- Build stack graph from the CST ---------------------------------

        // 1. File-level scope, connected to the global root.
        let file_scope = self.graph.new_node_id(file_handle);
        let file_scope_node = self.graph.add_scope_node(file_scope, false);
        if let Some(fs) = file_scope_node {
            self.graph.add_edge(StackGraph::root_node(), fs, 0);
        }

        // 2. Walk children of the root node to find definitions and references.
        let root = tree.root_node();
        let ts_lang = Self::resolve_language(language);

        if let Some(ref lang) = ts_lang {
            let mut cursor = tree_sitter::QueryCursor::new();

            match language {
                "python" => {
                    build_python_nodes(
                        &mut self.graph,
                        file_handle,
                        source,
                        root,
                        &mut cursor,
                        lang,
                        file_scope_node,
                    );
                }
                "javascript" | "jsx" | "typescript" | "tsx" => {
                    build_javascript_nodes(
                        &mut self.graph,
                        file_handle,
                        source,
                        root,
                        &mut cursor,
                        lang,
                        file_scope_node,
                    );
                }
                _ => {}
            }
        }

        self.file_handles
            .insert(file_path.to_path_buf(), file_handle);
        self.source_cache
            .insert(file_path.to_path_buf(), source.to_string());
        Ok(())
    }

    /// Remove a file from the stack graph.
    ///
    /// Removes the file from the source cache and rebuilds the entire graph
    /// without it. Returns an error if the file was not previously indexed.
    ///
    /// Note: `stack_graphs::StackGraph` has no individual file removal API,
    /// so we rebuild the full graph from the cached source content.
    pub fn remove_file(&mut self, path: &str) -> Result<(), String> {
        let file_path = Path::new(path);
        if !self.source_cache.contains_key(file_path) {
            return Err(format!("File not indexed: {}", path));
        }
        self.source_cache.remove(file_path);
        self.rebuild_from_cache()
    }

    /// Re-index a file that may already be in the graph.
    ///
    /// Updates the cached source for the given file, then rebuilds the
    /// entire graph from the cache. This is the method to use for
    /// incremental updates (e.g. from a file watcher).
    ///
    /// Note: `stack_graphs::StackGraph` has no individual file removal API,
    /// so we rebuild the full graph from the cached source content rather
    /// than trying to remove and re-add a single file.
    pub fn reindex_file(&mut self, path: &str, source: &str) -> Result<(), String> {
        self.source_cache
            .insert(Path::new(path).to_path_buf(), source.to_string());
        self.rebuild_from_cache()
    }

    /// Rebuild the entire graph from the cached source content.
    ///
    /// Clears the current graph and partial paths, then re-adds every file
    /// from `source_cache`. This is necessary because `stack_graphs::StackGraph`
    /// is append-only and has no individual file removal API.
    fn rebuild_from_cache(&mut self) -> Result<(), String> {
        let cache = std::mem::take(&mut self.source_cache);

        // Clear the entire graph
        self.graph = StackGraph::new();
        self.partial_paths = PartialPaths::new();
        self.file_handles.clear();

        // Re-add all files from the cache
        for (path, source) in &cache {
            let path_str = path.to_string_lossy();
            self.add_file(&path_str, source)?;
        }

        // Restore the cache (add_file repopulated source_cache entries)
        self.source_cache = cache;

        Ok(())
    }

    // -----------------------------------------------------------------------
    // BFS internals
    // -----------------------------------------------------------------------

    /// BFS forward through the graph from `start_nodes`, collecting all
    /// definition nodes reached, up to `max_depth` steps.
    ///
    /// Each visited definition is returned as a `ResolvedReference`.
    /// `start_nodes` are included in the results if they are definitions.
    fn bfs_definitions(
        &self,
        start_nodes: &[Handle<Node>],
        max_depth: usize,
    ) -> Vec<ResolvedReference> {
        let mut visited: HashSet<Handle<Node>> = HashSet::new();
        let mut queue: VecDeque<(Handle<Node>, usize)> = VecDeque::new();
        let mut results: Vec<ResolvedReference> = Vec::new();

        for &node in start_nodes {
            queue.push_back((node, 0));
        }

        while let Some((current, depth)) = queue.pop_front() {
            if !visited.insert(current) {
                continue;
            }

            let node = &self.graph[current];
            if node.is_definition() {
                if let Some(sym) = node.symbol() {
                    if let Some(si) = self.graph.source_info(current) {
                        let target_path = node
                            .id()
                            .file()
                            .map(|f| self.graph[f].name().to_string())
                            .unwrap_or_default();
                        results.push(ResolvedReference {
                            target_file: target_path,
                            target_line: si.span.start.line,
                            target_column: si.span.start.column.utf8_offset,
                            symbol_name: self.graph[sym].to_string(),
                            confidence: 0.9,
                        });
                    }
                }
            }

            if depth < max_depth {
                for edge in self.graph.outgoing_edges(current) {
                    queue.push_back((edge.sink, depth + 1));
                }
            }
        }

        results
    }

    // -----------------------------------------------------------------------
    // Reachability API
    // -----------------------------------------------------------------------

    /// BFS from definitions matching `symbol_name` in the file at `path`,
    /// collecting all reachable definitions up to `max_depth` hops.
    ///
    /// Returns a `Vec<ResolvedReference>` for every definition node visited.
    /// Returns an empty `Vec` when the file is not indexed or the symbol
    /// cannot be found.
    pub fn reachable_definitions(
        &self,
        path: &str,
        symbol_name: &str,
        max_depth: usize,
    ) -> Vec<ResolvedReference> {
        let file_path = Path::new(path);
        let file_handle = match self.file_handles.get(file_path) {
            Some(h) => h,
            None => return Vec::new(),
        };

        // Find all definition nodes matching the symbol name in the file.
        let mut start_nodes: Vec<Handle<Node>> = Vec::new();
        for node_handle in self.graph.nodes_for_file(*file_handle) {
            let node = &self.graph[node_handle];
            if node.is_definition() {
                if let Some(sym_handle) = node.symbol() {
                    if self.graph[sym_handle].to_string() == symbol_name {
                        start_nodes.push(node_handle);
                    }
                }
            }
        }

        if start_nodes.is_empty() {
            return Vec::new();
        }

        self.bfs_definitions(&start_nodes, max_depth)
    }

    /// Reverse BFS: find definitions whose forward traversal reaches the
    /// definition of `symbol_name` in the file at `path`.
    ///
    /// This answers "what functions call this one?" — useful for
    /// understanding impact scope.  Returns a `Vec<ResolvedReference>`
    /// for each calling definition found (up to `max_depth` hops from
    /// caller to callee).
    pub fn callers_of(
        &self,
        path: &str,
        symbol_name: &str,
        max_depth: usize,
    ) -> Vec<ResolvedReference> {
        // Avoid O(N×E) traversal on large graphs; defense-in-depth against future regression.
        if self.node_count() > 5000 {
            return Vec::new();
        }

        let file_path = Path::new(path);
        let file_handle = match self.file_handles.get(file_path) {
            Some(h) => h,
            None => return Vec::new(),
        };

        // Identify the target definition node(s) we want callers for.
        let mut target_defs: HashSet<Handle<Node>> = HashSet::new();
        for node_handle in self.graph.nodes_for_file(*file_handle) {
            let node = &self.graph[node_handle];
            if node.is_definition() {
                if let Some(sym_handle) = node.symbol() {
                    if self.graph[sym_handle].to_string() == symbol_name {
                        target_defs.insert(node_handle);
                    }
                }
            }
        }

        if target_defs.is_empty() {
            return Vec::new();
        }

        // Iterate every definition in the graph; for each one BFS forward
        // up to max_depth to see whether we reach a target definition.
        let mut callers: Vec<ResolvedReference> = Vec::new();
        for node_handle in self.graph.iter_nodes() {
            let node = &self.graph[node_handle];
            if !node.is_definition() || target_defs.contains(&node_handle) {
                continue;
            }

            let mut visited: HashSet<Handle<Node>> = HashSet::new();
            let mut queue: VecDeque<(Handle<Node>, usize)> = VecDeque::new();
            queue.push_back((node_handle, 0));

            let mut found_target = false;
            while let Some((current, depth)) = queue.pop_front() {
                if !visited.insert(current) {
                    continue;
                }
                if target_defs.contains(&current) {
                    found_target = true;
                    break;
                }
                if depth < max_depth {
                    for edge in self.graph.outgoing_edges(current) {
                        queue.push_back((edge.sink, depth + 1));
                    }
                }
            }

            if found_target {
                if let Some(sym_handle) = node.symbol() {
                    if let Some(si) = self.graph.source_info(node_handle) {
                        let caller_path = node
                            .id()
                            .file()
                            .map(|f| self.graph[f].name().to_string())
                            .unwrap_or_default();
                        callers.push(ResolvedReference {
                            target_file: caller_path,
                            target_line: si.span.start.line,
                            target_column: si.span.start.column.utf8_offset,
                            symbol_name: self.graph[sym_handle].to_string(),
                            confidence: 0.8,
                        });
                    }
                }
            }
        }

        callers
    }

    // -----------------------------------------------------------------------
    // Reference resolution
    // -----------------------------------------------------------------------

    /// Resolve a symbol reference at a given location.
    ///
    /// Uses the stack graph to find the definition corresponding to the
    /// reference at (`line`, `column`) in `path`.  Lines and columns are
    /// 0-indexed.
    ///
    /// Returns `None` when the file is not indexed or no matching node is
    /// found.
    pub fn resolve_reference(
        &self,
        path: &str,
        line: usize,
        column: usize,
    ) -> Option<ResolvedReference> {
        let file_path = Path::new(path);
        let file_handle = self.file_handles.get(file_path)?;

        // --- Phase 1: find the reference node whose source span covers (line, col) ---

        let mut best_ref: Option<(Handle<Node>, Handle<SgSymbol>)> = None;
        let mut best_ref_span_size: usize = usize::MAX;

        for node_handle in self.graph.nodes_for_file(*file_handle) {
            let node = &self.graph[node_handle];
            if !node.is_reference() {
                continue;
            }

            if let Some(si) = self.graph.source_info(node_handle) {
                if !position_in_span(&si.span, line, column) {
                    continue;
                }
                if let Some(symbol) = node.symbol() {
                    let sz = span_size(&si.span);
                    // Pick the narrowest (most specific) match.
                    if sz < best_ref_span_size {
                        best_ref = Some((node_handle, symbol));
                        best_ref_span_size = sz;
                    }
                }
            }
        }

        let (ref_node_handle, ref_symbol) = best_ref?;
        let symbol_name = self.graph[ref_symbol].to_string();

        // --- Phase 2: BFS forward through edges looking for a matching definition ---

        let mut visited: HashSet<Handle<Node>> = HashSet::new();
        let mut queue: VecDeque<Handle<Node>> = VecDeque::new();
        queue.push_back(ref_node_handle);

        while let Some(current) = queue.pop_front() {
            if !visited.insert(current) {
                continue;
            }

            let node = &self.graph[current];
            if node.is_definition() {
                if let Some(sym) = node.symbol() {
                    if sym == ref_symbol {
                        // Found a matching definition — build the result.
                        if let Some(si) = self.graph.source_info(current) {
                            let target_path = node
                                .id()
                                .file()
                                .map(|f| self.graph[f].name().to_string())
                                .unwrap_or_else(|| path.to_string());
                            return Some(ResolvedReference {
                                target_file: target_path,
                                target_line: si.span.start.line,
                                target_column: si.span.start.column.utf8_offset,
                                symbol_name,
                                confidence: 0.9,
                            });
                        }
                    }
                }
            }

            for edge in self.graph.outgoing_edges(current) {
                queue.push_back(edge.sink);
            }
        }

        // --- Phase 3: fallback — symbol identified but no path found ---
        Some(ResolvedReference {
            target_file: path.to_string(),
            target_line: 0,
            target_column: 0,
            symbol_name,
            confidence: 0.1,
        })
    }

    // -----------------------------------------------------------------------
    // Metrics and lifecycle
    // -----------------------------------------------------------------------

    /// Number of files currently indexed.
    pub fn file_count(&self) -> usize {
        self.file_handles.len()
    }

    /// Number of nodes in the global graph.
    pub fn node_count(&self) -> usize {
        self.graph.iter_nodes().count()
    }

    /// Reset all state.
    pub fn clear(&mut self) {
        self.graph = StackGraph::new();
        self.partial_paths = PartialPaths::new();
        self.file_handles.clear();
        self.source_cache.clear();
    }
}

impl Default for StackGraphManager {
    fn default() -> Self {
        Self::new()
    }
}

// ===========================================================================
// CST-walking helpers
// ===========================================================================

/// Walk a Python CST and create stack graph nodes for definitions and
/// references.  Mirrors `tsg_rules/python.tsg`.
fn build_python_nodes(
    graph: &mut StackGraph,
    file: Handle<File>,
    source: &str,
    root_node: tree_sitter::Node,
    cursor: &mut tree_sitter::QueryCursor,
    ts_lang: &TsLanguage,
    parent_scope: Option<Handle<Node>>,
) {
    build_def_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(function_definition name: (identifier) @name) @def",
        "function",
        parent_scope,
    );

    build_def_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(class_definition name: (identifier) @name) @def",
        "class",
        parent_scope,
    );

    build_refs_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(identifier) @id",
    );
}

/// Walk a JavaScript/TypeScript CST and create stack graph nodes.
/// Mirrors `tsg_rules/javascript.tsg`.
fn build_javascript_nodes(
    graph: &mut StackGraph,
    file: Handle<File>,
    source: &str,
    root_node: tree_sitter::Node,
    cursor: &mut tree_sitter::QueryCursor,
    ts_lang: &TsLanguage,
    parent_scope: Option<Handle<Node>>,
) {
    build_def_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(function_declaration name: (identifier) @name) @def",
        "function",
        parent_scope,
    );

    build_def_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(method_definition name: (property_identifier) @name) @def",
        "method",
        parent_scope,
    );

    build_def_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(class_declaration name: (identifier) @name) @def",
        "class",
        parent_scope,
    );

    build_def_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(variable_declarator name: (identifier) @name) @def",
        "variable",
        parent_scope,
    );

    build_refs_from_query(
        graph,
        file,
        source,
        cursor,
        root_node,
        ts_lang,
        "(identifier) @id",
    );
}

// ===========================================================================
// Low-level node builders
// ===========================================================================

/// Create a definition node (pop-symbol) for each match of `pattern`.
#[allow(clippy::too_many_arguments)]
fn build_def_from_query(
    graph: &mut StackGraph,
    file: Handle<File>,
    source: &str,
    cursor: &mut tree_sitter::QueryCursor,
    root_node: tree_sitter::Node,
    ts_lang: &TsLanguage,
    pattern: &str,
    syntax_type: &str,
    parent_scope: Option<Handle<Node>>,
) {
    let query = match tree_sitter::Query::new(ts_lang, pattern) {
        Ok(q) => q,
        Err(_) => return,
    };
    let mut matches = cursor.matches(&query, root_node, source.as_bytes());

    while let Some(m) = matches.next() {
        let def_cap = query.capture_index_for_name("def");
        let name_cap = query.capture_index_for_name("name");

        let source_node = def_cap
            .and_then(|ci| m.nodes_for_capture_index(ci).next())
            .or_else(|| name_cap.and_then(|ci| m.nodes_for_capture_index(ci).next()));

        let name_node = name_cap.and_then(|ci| m.nodes_for_capture_index(ci).next());

        let (symbol_text, span_node) = match (name_node, source_node) {
            (Some(n), Some(s)) => match n.utf8_text(source.as_bytes()) {
                Ok(text) => (text.to_string(), s),
                Err(_) => continue,
            },
            _ => continue,
        };

        let def_id = graph.new_node_id(file);
        let sym = graph.add_symbol(&symbol_text);
        let def_handle = match graph.add_pop_symbol_node(def_id, sym, true) {
            Some(h) => h,
            None => continue,
        };

        // Attach source info for position-based lookups.
        let syntax_str = graph.add_string(syntax_type);
        let si = graph.source_info_mut(def_handle);
        si.span = span_for_node(source, span_node);
        si.syntax_type = syntax_str.into();

        // Edge from parent scope → definition (if we have one).
        if let Some(scope) = parent_scope {
            graph.add_edge(scope, def_handle, 0);
        }
    }
}

/// Create a reference node (push-symbol) for each identifier found by
/// `pattern`.
fn build_refs_from_query(
    graph: &mut StackGraph,
    file: Handle<File>,
    source: &str,
    cursor: &mut tree_sitter::QueryCursor,
    root_node: tree_sitter::Node,
    ts_lang: &TsLanguage,
    pattern: &str,
) {
    let query = match tree_sitter::Query::new(ts_lang, pattern) {
        Ok(q) => q,
        Err(_) => return,
    };
    let mut matches = cursor.matches(&query, root_node, source.as_bytes());

    while let Some(m) = matches.next() {
        let id_node = match m.nodes_for_capture_index(0).next() {
            Some(n) => n,
            None => continue,
        };
        let symbol_text = match id_node.utf8_text(source.as_bytes()) {
            Ok(t) => t,
            Err(_) => continue,
        };

        let ref_id = graph.new_node_id(file);
        let sym = graph.add_symbol(symbol_text);
        let ref_handle = match graph.add_push_symbol_node(ref_id, sym, true) {
            Some(h) => h,
            None => continue,
        };

        // Attach source info for position-based lookups.
        let si = graph.source_info_mut(ref_handle);
        si.span = span_for_node(source, id_node);
    }
}

// ===========================================================================
// Utility functions
// ===========================================================================

/// Build an `lsp_positions::Span` from a tree-sitter node.
fn span_for_node(source: &str, node: tree_sitter::Node) -> lsp_positions::Span {
    let start = node.start_position();
    let end = node.end_position();

    let start_col = line_utf8_column(source, start.row, start.column);
    let end_col = line_utf8_column(source, end.row, end.column);

    lsp_positions::Span {
        start: lsp_positions::Position {
            line: start.row,
            column: lsp_positions::Offset {
                utf8_offset: start_col,
                utf16_offset: 0,
                grapheme_offset: 0,
            },
            containing_line: 0..0,
            trimmed_line: 0..0,
        },
        end: lsp_positions::Position {
            line: end.row,
            column: lsp_positions::Offset {
                utf8_offset: end_col,
                utf16_offset: 0,
                grapheme_offset: 0,
            },
            containing_line: 0..0,
            trimmed_line: 0..0,
        },
    }
}

/// Compute the UTF-8 byte offset on the given 0-indexed line of `source`.
fn line_utf8_column(source: &str, line: usize, col: usize) -> usize {
    source
        .lines()
        .nth(line)
        .map(|l| l.len().min(col))
        .unwrap_or(0)
}

/// Returns `true` if the zero-indexed `(line, column)` falls within the span.
fn position_in_span(span: &lsp_positions::Span, line: usize, column: usize) -> bool {
    if line < span.start.line || line > span.end.line {
        return false;
    }
    if line == span.start.line && column < span.start.column.utf8_offset {
        return false;
    }
    if line == span.end.line && column >= span.end.column.utf8_offset {
        return false;
    }
    true
}

/// Returns a rough size for a span (used to prefer more specific spans).
fn span_size(span: &lsp_positions::Span) -> usize {
    let lines = span.end.line.saturating_sub(span.start.line);
    let cols = span
        .end
        .column
        .utf8_offset
        .saturating_sub(span.start.column.utf8_offset);
    lines * 1000 + cols
}
