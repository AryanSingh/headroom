package cutctx

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync/atomic"
	"time"
)

// Message is a chat message passed to/from the LLM
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// CompressRequest is sent to the proxy
type CompressRequest struct {
	Messages []Message `json:"messages"`
	Model    string    `json:"model,omitempty"`
}

// Stats holds lifetime compression statistics for this client
type Stats struct {
	TokensOriginal   int64
	TokensCompressed int64
	RequestsTotal    int64
	CompressionRatio float64
}

// Client is the Cutctx compression client
type Client struct {
	proxyURL   string
	apiKey     string
	model      string
	httpClient *http.Client
	origTotal  atomic.Int64
	compTotal  atomic.Int64
	reqTotal   atomic.Int64
}
// New creates a new Client. Defaults: proxyURL=http://localhost:8787, timeout=30s
func New(opts ...Option) *Client {
	c := &Client{
		proxyURL: "http://localhost:8787",
		model:    "claude-sonnet-4-6",
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}
	for _, o := range opts {
		o(c)
	}
	return c
}

// Compress sends messages through Cutctx and returns compressed messages.
// POST {proxyURL}/v1/compress
func (c *Client) Compress(ctx context.Context, messages []Message) ([]Message, error) {
	body, err := json.Marshal(CompressRequest{Messages: messages, Model: c.model})
	if err != nil {
		return nil, fmt.Errorf("cutctx: marshal: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.proxyURL+"/v1/compress", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("cutctx: new request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("X-Cutctx-Key", c.apiKey)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cutctx: compress request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("cutctx: compress: status %d", resp.StatusCode)
	}
	var out struct {
		Messages []Message `json:"messages"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("cutctx: decode response: %w", err)
	}
	c.reqTotal.Add(1)
	return out.Messages, nil
}

// Retrieve fetches original content for a [cutctx:ref:HASH] pointer.
// GET {proxyURL}/v1/retrieve/{ref}
func (c *Client) Retrieve(ctx context.Context, ref string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.proxyURL+"/v1/retrieve/"+ref, nil)
	if err != nil {
		return "", fmt.Errorf("cutctx: retrieve request: %w", err)
	}
	if c.apiKey != "" {
		req.Header.Set("X-Cutctx-Key", c.apiKey)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("cutctx: retrieve: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("cutctx: retrieve: status %d", resp.StatusCode)
	}
	var out struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", fmt.Errorf("cutctx: retrieve decode: %w", err)
	}
	return out.Content, nil
}

// Stats returns current lifetime statistics
func (c *Client) Stats() Stats {
	orig := c.origTotal.Load()
	comp := c.compTotal.Load()
	ratio := 0.0
	if orig > 0 {
		ratio = float64(comp) / float64(orig)
	}
	return Stats{
		TokensOriginal:   orig,
		TokensCompressed: comp,
		RequestsTotal:    c.reqTotal.Load(),
		CompressionRatio: ratio,
	}
}
