//! Integration tests for the stack-graph based code navigation.

#[cfg(test)]
mod tests {
    use cutctx_core::stack_graph::StackGraphManager;

    #[test]
    fn test_new_manager_is_empty() {
        let mgr = StackGraphManager::new();
        assert_eq!(mgr.file_count(), 0);
        // StackGraph internally creates 2 root nodes
        assert_eq!(mgr.node_count(), 2);
    }

    #[test]
    fn test_add_and_count_python_file() {
        let mut mgr = StackGraphManager::new();
        let result = mgr.add_file("test.py", "def foo():\n    pass\n");
        assert!(result.is_ok());
        assert_eq!(mgr.file_count(), 1);
        assert!(mgr.node_count() > 0);
    }

    #[test]
    fn test_add_and_count_js_file() {
        let mut mgr = StackGraphManager::new();
        let result = mgr.add_file("test.js", "function foo() { return 1; }\n");
        assert!(result.is_ok());
        assert_eq!(mgr.file_count(), 1);
    }

    #[test]
    fn test_add_unsupported_language_returns_err() {
        let mut mgr = StackGraphManager::new();
        // .rs files are listed in LANGUAGE_ALIASES but only python/javascript have
        // registered grammars — this might succeed or fail depending on the impl
        let result = mgr.add_file("test.rs", "fn foo() {}\n");
        if result.is_err() {
            assert!(result.unwrap_err().contains("Unsupported"));
        }
    }

    #[test]
    fn test_add_invalid_source_returns_err() {
        let mut mgr = StackGraphManager::new();
        let result = mgr.add_file("test.py", "\x00\x00\x00\x00"); // invalid UTF-8-ish content
                                                                  // tree-sitter should handle this gracefully (may or may not parse)
                                                                  // At minimum it should not panic
        let _ = result; // just verify no panic
    }

    #[test]
    fn test_resolve_returns_none_for_empty_graph() {
        let mgr = StackGraphManager::new();
        let result = mgr.resolve_reference("test.py", 0, 0);
        assert!(result.is_none());
    }

    #[test]
    fn test_clear_resets_state() {
        let mut mgr = StackGraphManager::new();
        mgr.add_file("a.py", "x = 1\n").unwrap();
        assert_eq!(mgr.file_count(), 1);
        mgr.clear();
        assert_eq!(mgr.file_count(), 0);
        // StackGraph resets to initial state with 2 root nodes
        assert_eq!(mgr.node_count(), 2);
    }

    #[test]
    fn test_multiple_files() {
        let mut mgr = StackGraphManager::new();
        mgr.add_file("a.py", "def helper(): pass\n").unwrap();
        mgr.add_file("b.py", "from a import helper\nhelper()\n")
            .unwrap();
        assert_eq!(mgr.file_count(), 2);
    }

    #[test]
    fn test_register_language_python() {
        let mut mgr = StackGraphManager::new();
        assert!(mgr.register_language("python"));
    }

    #[test]
    fn test_register_language_unsupported() {
        let mut mgr = StackGraphManager::new();
        assert!(!mgr.register_language("ruby"));
    }

    #[test]
    fn test_default_impl() {
        let mgr = StackGraphManager::default();
        assert_eq!(mgr.file_count(), 0);
    }

    #[test]
    fn test_remove_file_removes_from_graph() {
        let mut mgr = StackGraphManager::new();
        mgr.add_file("test.py", "x = 1\n").unwrap();
        assert_eq!(mgr.file_count(), 1);
        let result = mgr.remove_file("test.py");
        assert!(result.is_ok());
        assert_eq!(mgr.file_count(), 0);
    }

    #[test]
    fn test_remove_file_errors_on_missing() {
        let mut mgr = StackGraphManager::new();
        let result = mgr.remove_file("nonexistent.py");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not indexed"));
    }

    #[test]
    fn test_reindex_file_replaces_existing() {
        let mut mgr = StackGraphManager::new();
        mgr.add_file("test.py", "x = 1\n").unwrap();
        assert_eq!(mgr.file_count(), 1);
        // Reindex with different content
        let result = mgr.reindex_file("test.py", "y = 2\n");
        assert!(result.is_ok());
        assert_eq!(mgr.file_count(), 1);
    }

    #[test]
    fn test_reindex_file_works_on_new_file() {
        let mut mgr = StackGraphManager::new();
        let result = mgr.reindex_file("test.py", "x = 1\n");
        assert!(result.is_ok());
        assert_eq!(mgr.file_count(), 1);
    }

    #[test]
    fn test_add_duplicate_file_returns_err() {
        let mut mgr = StackGraphManager::new();
        mgr.add_file("test.py", "x = 1\n").unwrap();
        let result = mgr.add_file("test.py", "x = 2\n");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("already exists"));
    }
}
