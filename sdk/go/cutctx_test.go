package cutctx

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestNew(t *testing.T) {
	c := New()
	if c.proxyURL != "http://localhost:8787" {
		t.Errorf("expected default proxy URL, got %s", c.proxyURL)
	}
	if c.model != "claude-sonnet-4-20250514" {
		t.Errorf("expected default model, got %s", c.model)
	}
}

func TestNewWithOptions(t *testing.T) {
	c := New(
		WithProxyURL("http://custom:9999"),
		WithAPIKey("test-key"),
		WithModel("gpt-4"),
	)
	if c.proxyURL != "http://custom:9999" {
		t.Errorf("expected custom proxy URL, got %s", c.proxyURL)
	}
	if c.apiKey != "test-key" {
		t.Errorf("expected API key, got %s", c.apiKey)
	}
	if c.model != "gpt-4" {
		t.Errorf("expected custom model, got %s", c.model)
	}
}

func TestCompress(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/v1/compress" {
			t.Errorf("expected /v1/compress, got %s", r.URL.Path)
		}

		var req compressRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("failed to decode request: %v", err)
		}
		if len(req.Messages) != 1 {
			t.Fatalf("expected 1 message, got %d", len(req.Messages))
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(compressResponse{
			Compressed: []Message{
				{Role: "user", Content: "compressed content"},
			},
			OriginalTokens:   100,
			CompressedTokens: 50,
			SavingsPercent:   50.0,
		})
	}))
	defer server.Close()

	c := New(WithProxyURL(server.URL))
	messages := []Message{{Role: "user", Content: "Hello, how are you?"}}
	result, err := c.Compress(context.Background(), messages)
	if err != nil {
		t.Fatalf("Compress failed: %v", err)
	}
	if len(result) != 1 {
		t.Fatalf("expected 1 compressed message, got %d", len(result))
	}
	if result[0].Content != "compressed content" {
		t.Errorf("expected 'compressed content', got %s", result[0].Content)
	}
}

func TestRetrieve(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/retrieve" {
			t.Errorf("expected /v1/retrieve, got %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"content": "original content"})
	}))
	defer server.Close()

	c := New(WithProxyURL(server.URL))
	content, err := c.Retrieve(context.Background(), "ccr:abc123")
	if err != nil {
		t.Fatalf("Retrieve failed: %v", err)
	}
	if content != "original content" {
		t.Errorf("expected 'original content', got %s", content)
	}
}

func TestStats(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/stats" {
			t.Errorf("expected /stats, got %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(Stats{
			RequestsTotal:    100,
			TokensInputTotal: 10000,
			TokensSavedTotal: 5000,
			CompressionRatio: 0.5,
		})
	}))
	defer server.Close()

	c := New(WithProxyURL(server.URL))
	stats, err := c.Stats(context.Background())
	if err != nil {
		t.Fatalf("Stats failed: %v", err)
	}
	if stats.RequestsTotal != 100 {
		t.Errorf("expected 100 requests, got %d", stats.RequestsTotal)
	}
	if stats.CompressionRatio != 0.5 {
		t.Errorf("expected 0.5 compression ratio, got %f", stats.CompressionRatio)
	}
}

func TestCompressError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("internal error"))
	}))
	defer server.Close()

	c := New(WithProxyURL(server.URL))
	_, err := c.Compress(context.Background(), []Message{{Role: "user", Content: "test"}})
	if err == nil {
		t.Fatal("expected error for 500 response")
	}
}

func TestCompressWithContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(compressResponse{Compressed: []Message{{Role: "user", Content: "ok"}}})
	}))
	defer server.Close()

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	c := New(WithProxyURL(server.URL))
	_, err := c.Compress(ctx, []Message{{Role: "user", Content: "test"}})
	if err == nil {
		t.Fatal("expected error for cancelled context")
	}
}
