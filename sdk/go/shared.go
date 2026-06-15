package cutctx

import (
	"fmt"
	"sort"
	"sync"
)

// SharedContext provides thread-safe key-value storage for sharing
// context across multiple operations.
type SharedContext struct {
	mu    sync.RWMutex
	items map[string]string
}

// SharedStats holds statistics about the shared context.
type SharedStats struct {
	Entries int      `json:"entries"`
	Keys    []string `json:"keys"`
}

// NewSharedContext creates a new SharedContext.
func NewSharedContext() *SharedContext {
	return &SharedContext{
		items: make(map[string]string),
	}
}

// Put stores a key-value pair in the shared context.
func (sc *SharedContext) Put(key, value string) {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	sc.items[key] = value
}

// Get retrieves a value by key. Returns the value and whether it was found.
func (sc *SharedContext) Get(key string) (string, bool) {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	val, ok := sc.items[key]
	return val, ok
}

// List returns a copy of all entries in the shared context.
func (sc *SharedContext) List() map[string]string {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	result := make(map[string]string, len(sc.items))
	for k, v := range sc.items {
		result[k] = v
	}
	return result
}

// Clear removes all entries from the shared context.
func (sc *SharedContext) Clear() {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	sc.items = make(map[string]string)
}

// Stats returns statistics about the shared context.
func (sc *SharedContext) Stats() SharedStats {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	keys := make([]string, 0, len(sc.items))
	for k := range sc.items {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return SharedStats{
		Entries: len(sc.items),
		Keys:    keys,
	}
}

// String returns a human-readable representation.
func (sc *SharedContext) String() string {
	stats := sc.Stats()
	return fmt.Sprintf("SharedContext{entries=%d, keys=%v}", stats.Entries, stats.Keys)
}
