import json
import os
import tempfile

from cutctx.cache.compression_store import CompressionStore


def test_episodic_memory_ccr_bridge():
    """Verify that Python and Rust CCR stores interoperate correctly using SQLite."""
    # 1. Set up a temporary sqlite database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_ccr.db")

        from cutctx.cache.backends.sqlite import SqliteBackend

        backend = SqliteBackend(db_path)

        # Initialize the Python store with our custom backend
        store = CompressionStore(backend=backend)

        # 2. Instantiate Rust compressor from Python
        # We need to simulate how the SmartCrusher is constructed with ccr_db_path.
        # However, SmartCrusher.__init__ hardcodes os.path.expanduser("~/.cutctx/ccr.db").
        # To test it cleanly without modifying the global ~/.cutctx/ccr.db, we can mock os.path.expanduser
        # or we can construct the rust object directly.
        from cutctx._core import SmartCrusher as _RustSmartCrusher
        from cutctx._core import SmartCrusherConfig as _RustSmartCrusherConfig

        rust_cfg = _RustSmartCrusherConfig(
            lossless_min_savings_ratio=0.99,  # force lossy
            enable_ccr_marker=True,
            first_fraction=0.0,
            last_fraction=0.0,
            max_items_after_crush=1,
            min_items_to_analyze=1,
        )

        # Pass the custom db path to Rust
        crusher = _RustSmartCrusher.without_compaction(rust_cfg, ccr_db_path=db_path)

        # 3. Compress an episodic memory block
        items = [{"role": "user", "content": f"Message {i}"} for i in range(50)]
        items_json = json.dumps(items)

        # Crush the array using Rust
        result = crusher.crush_array_json(items_json, query="Message 9", bias=1.0)

        # Verify the marker was generated
        ccr_hash = result["ccr_hash"]
        assert ccr_hash is not None, (
            f"CCR marker should be generated. Items returned: {len(json.loads(result['items']))}"
        )
        assert len(ccr_hash) == 16, "CCR hash should be 16 chars"

        # 4. Use pure Python to query the SQLite DB and retrieve the original memory block
        retrieved_entry = store.retrieve(ccr_hash)

        assert retrieved_entry is not None, "Failed to retrieve the entry from Python"

        # Verify the retrieved content matches the original
        retrieved_items = json.loads(retrieved_entry.original_content)
        assert len(retrieved_items) == 50
        assert retrieved_items[0]["content"] == "Message 0"
        assert retrieved_items[49]["content"] == "Message 49"


if __name__ == "__main__":
    test_episodic_memory_ccr_bridge()
