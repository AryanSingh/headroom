"""Tests for CutCtx SDK shared context."""

from __future__ import annotations

import threading

from cutctx_sdk.shared import SharedContext


class TestSharedContext:
    def test_put_get(self):
        sc = SharedContext()
        sc.put("k", "v")
        val, ok = sc.get("k")
        assert ok is True
        assert val == "v"

    def test_get_missing(self):
        sc = SharedContext()
        val, ok = sc.get("missing")
        assert ok is False
        assert val is None

    def test_list_returns_copy(self):
        sc = SharedContext()
        sc.put("a", "1")
        items = sc.list()
        items["b"] = "2"  # mutate copy
        _, ok = sc.get("b")
        assert ok is False  # should not leak

    def test_clear(self):
        sc = SharedContext()
        sc.put("x", "1")
        sc.clear()
        _, ok = sc.get("x")
        assert ok is False

    def test_stats(self):
        sc = SharedContext()
        sc.put("beta", "2")
        sc.put("alpha", "1")
        stats = sc.stats()
        assert stats["entries"] == 2
        assert stats["keys"] == ["alpha", "beta"]

    def test_thread_safety(self):
        sc = SharedContext()
        wg = threading.Barrier(50)

        def writer():
            wg.wait()
            for i in range(100):
                sc.put(f"key-{i}", str(i))

        def reader():
            wg.wait()
            for i in range(100):
                sc.get(f"key-{i}")

        threads = [threading.Thread(target=writer) for _ in range(25)]
        threads += [threading.Thread(target=reader) for _ in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # No exception = pass

    def test_repr(self):
        sc = SharedContext()
        sc.put("a", "1")
        r = repr(sc)
        assert "SharedContext" in r
        assert "1" in r
