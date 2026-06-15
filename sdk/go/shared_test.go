package cutctx

import (
	"sync"
	"testing"
)

func TestSharedContext_PutGet(t *testing.T) {
	sc := NewSharedContext()
	sc.Put("key1", "value1")
	sc.Put("key2", "value2")

	if v, ok := sc.Get("key1"); !ok || v != "value1" {
		t.Errorf("expected value1, got %q (ok=%v)", v, ok)
	}
	if v, ok := sc.Get("key2"); !ok || v != "value2" {
		t.Errorf("expected value2, got %q (ok=%v)", v, ok)
	}
	if _, ok := sc.Get("missing"); ok {
		t.Error("expected missing key to return false")
	}
}

func TestSharedContext_List(t *testing.T) {
	sc := NewSharedContext()
	sc.Put("a", "1")
	sc.Put("b", "2")

	list := sc.List()
	if len(list) != 2 {
		t.Errorf("expected 2 entries, got %d", len(list))
	}
	if list["a"] != "1" || list["b"] != "2" {
		t.Errorf("unexpected list contents: %v", list)
	}

	// Mutating the returned map should not affect the original
	list["c"] = "3"
	if _, ok := sc.Get("c"); ok {
		t.Error("mutation of List() result leaked into SharedContext")
	}
}

func TestSharedContext_Clear(t *testing.T) {
	sc := NewSharedContext()
	sc.Put("x", "1")
	sc.Put("y", "2")
	sc.Clear()

	if _, ok := sc.Get("x"); ok {
		t.Error("expected x to be cleared")
	}
	if stats := sc.Stats(); stats.Entries != 0 {
		t.Errorf("expected 0 entries after clear, got %d", stats.Entries)
	}
}

func TestSharedContext_Stats(t *testing.T) {
	sc := NewSharedContext()
	sc.Put("beta", "2")
	sc.Put("alpha", "1")

	stats := sc.Stats()
	if stats.Entries != 2 {
		t.Errorf("expected 2 entries, got %d", stats.Entries)
	}
	if len(stats.Keys) != 2 {
		t.Errorf("expected 2 keys, got %d", len(stats.Keys))
	}
	// Keys should be sorted
	if stats.Keys[0] != "alpha" || stats.Keys[1] != "beta" {
		t.Errorf("expected sorted keys [alpha, beta], got %v", stats.Keys)
	}
}

func TestSharedContext_ThreadSafety(t *testing.T) {
	sc := NewSharedContext()
	var wg sync.WaitGroup

	// Concurrent writers
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			key := string(rune('a'+n%26)) + string(rune('0'+n/26))
			sc.Put(key, "value")
		}(i)
	}

	// Concurrent readers
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			sc.Get("alpha0")
			sc.List()
			sc.Stats()
		}(i)
	}

	wg.Wait()
	// No race detector panic = pass
}

func TestSharedContext_String(t *testing.T) {
	sc := NewSharedContext()
	sc.Put("k", "v")
	s := sc.String()
	if s == "" {
		t.Error("String() should return non-empty string")
	}
}
