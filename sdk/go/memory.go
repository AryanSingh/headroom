package cutctx

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
)

// MemoryClient provides access to Cutctx's episodic memory system.
type MemoryClient struct {
	client *Client
}

// NewMemoryClient creates a memory client from an existing Client.
func (c *Client) Memory() *MemoryClient {
	return &MemoryClient{client: c}
}

// MemoryEntry represents a stored memory.
type MemoryEntry struct {
	ID        string            `json:"id"`
	Content   string            `json:"content"`
	Project   string            `json:"project,omitempty"`
	Metadata  map[string]string `json:"metadata,omitempty"`
	CreatedAt string            `json:"created_at,omitempty"`
}

// Store saves content to episodic memory.
func (m *MemoryClient) Store(ctx context.Context, content, project string) error {
	body := map[string]any{
		"content": content,
		"project": project,
	}
	b, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("cutctx memory: marshal: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, m.client.proxyURL+"/v1/memory/store", bytes.NewReader(b))
	if err != nil {
		return fmt.Errorf("cutctx memory: new request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if m.client.apiKey != "" {
		req.Header.Set("X-Cutctx-Key", m.client.apiKey)
	}
	resp, err := m.client.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("cutctx memory: request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return &CutctxError{Code: resp.StatusCode, Path: "/v1/memory/store"}
	}
	return nil
}

// Search queries episodic memory.
func (m *MemoryClient) Search(ctx context.Context, query string, limit int) ([]MemoryEntry, error) {
	body := map[string]any{
		"query": query,
		"limit": limit,
	}
	b, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("cutctx memory: marshal: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, m.client.proxyURL+"/v1/memory/search", bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("cutctx memory: new request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if m.client.apiKey != "" {
		req.Header.Set("X-Cutctx-Key", m.client.apiKey)
	}
	resp, err := m.client.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cutctx memory: request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, &CutctxError{Code: resp.StatusCode, Path: "/v1/memory/search"}
	}
	var out struct {
		Entries []MemoryEntry `json:"entries"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("cutctx memory: decode: %w", err)
	}
	return out.Entries, nil
}

// List returns all stored memories.
func (m *MemoryClient) List(ctx context.Context) ([]MemoryEntry, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, m.client.proxyURL+"/v1/memory/list", nil)
	if err != nil {
		return nil, fmt.Errorf("cutctx memory: new request: %w", err)
	}
	if m.client.apiKey != "" {
		req.Header.Set("X-Cutctx-Key", m.client.apiKey)
	}
	resp, err := m.client.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cutctx memory: request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, &CutctxError{Code: resp.StatusCode, Path: "/v1/memory/list"}
	}
	var out struct {
		Entries []MemoryEntry `json:"entries"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("cutctx memory: decode: %w", err)
	}
	return out.Entries, nil
}
