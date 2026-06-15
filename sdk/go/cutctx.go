// Package cutctx provides a Go client for the CutCtx context compression proxy.
//
// CutCtx compresses LLM context windows by 50-70% with zero quality loss.
// This SDK communicates with the CutCtx proxy HTTP API — no native bindings needed.
//
// Quickstart:
//
//	client := cutctx.New(cutctx.WithProxyURL("http://localhost:8787"))
//	messages := []cutctx.Message{
//	    {Role: "user", Content: "Hello, how are you?"},
//	}
//	compressed, err := client.Compress(context.Background(), messages)
package cutctx

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Message represents a chat message in the OpenAI/Anthropic format.
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// Stats represents compression statistics from the proxy.
type Stats struct {
	RequestsTotal      int     `json:"requests_total"`
	TokensInputTotal   int     `json:"tokens_input_total"`
	TokensSavedTotal   int     `json:"tokens_saved_total"`
	CompressionRatio   float64 `json:"compression_ratio"`
}

// Client is the CutCtx client for compressing and retrieving context.
type Client struct {
	proxyURL    string
	apiKey      string
	httpClient  *http.Client
	model       string
}

// Option configures the Client.
type Option func(*Client)

// WithProxyURL sets the CutCtx proxy URL (default: http://localhost:8787).
func WithProxyURL(url string) Option {
	return func(c *Client) { c.proxyURL = url }
}

// WithAPIKey sets the API key for the upstream LLM provider.
func WithAPIKey(key string) Option {
	return func(c *Client) { c.apiKey = key }
}

// WithHTTPClient sets a custom HTTP client.
func WithHTTPClient(client *http.Client) Option {
	return func(c *Client) { c.httpClient = client }
}

// WithModel sets the model name for compression requests.
func WithModel(model string) Option {
	return func(c *Client) { c.model = model }
}

// WithTimeout sets the HTTP client timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *Client) { c.httpClient.Timeout = d }
}

// New creates a new CutCtx client with the given options.
func New(opts ...Option) *Client {
	c := &Client{
		proxyURL: "http://localhost:8787",
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		model: "claude-sonnet-4-20250514",
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

// compressRequest is the request body for POST /v1/compress.
type compressRequest struct {
	Messages []Message `json:"messages"`
	Model    string    `json:"model,omitempty"`
}

// compressResponse is the response from POST /v1/compress.
type compressResponse struct {
	Compressed  []Message `json:"compressed"`
	OriginalTokens int   `json:"original_tokens"`
	CompressedTokens int `json:"compressed_tokens"`
	SavingsPercent float64 `json:"savings_percent"`
}

// Compress sends messages through the CutCtx proxy for compression.
func (c *Client) Compress(ctx context.Context, messages []Message) ([]Message, error) {
	reqBody := compressRequest{
		Messages: messages,
		Model:    c.model,
	}
	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("cutctx: failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.proxyURL+"/v1/compress", bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("cutctx: failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cutctx: request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cutctx: proxy returned %d: %s", resp.StatusCode, string(respBody))
	}

	var result compressResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("cutctx: failed to decode response: %w", err)
	}

	return result.Compressed, nil
}

// Retrieve fetches the original content for a CCR reference.
func (c *Client) Retrieve(ctx context.Context, ref string) (string, error) {
	reqBody := map[string]string{"ref": ref}
	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("cutctx: failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.proxyURL+"/v1/retrieve", bytes.NewReader(bodyBytes))
	if err != nil {
		return "", fmt.Errorf("cutctx: failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("cutctx: request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("cutctx: proxy returned %d: %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("cutctx: failed to decode response: %w", err)
	}

	return result.Content, nil
}

// Stats fetches compression statistics from the proxy.
func (c *Client) Stats(ctx context.Context) (*Stats, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.proxyURL+"/stats", nil)
	if err != nil {
		return nil, fmt.Errorf("cutctx: failed to create request: %w", err)
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cutctx: request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cutctx: proxy returned %d: %s", resp.StatusCode, string(respBody))
	}

	var stats Stats
	if err := json.NewDecoder(resp.Body).Decode(&stats); err != nil {
		return nil, fmt.Errorf("cutctx: failed to decode response: %w", err)
	}

	return &stats, nil
}
