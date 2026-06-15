package cutctx_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	cutctx "github.com/cutctx/cutctx-go"
)

func TestNew_Defaults(t *testing.T) {
	c := cutctx.New()
	stats := c.Stats()
	if stats.RequestsTotal != 0 {
		t.Errorf("expected 0 requests, got %d", stats.RequestsTotal)
	}
	if stats.TokensOriginal != 0 || stats.TokensCompressed != 0 {
		t.Errorf("expected zero token counts on fresh client")
	}
	if stats.CompressionRatio != 0.0 {
		t.Errorf("expected 0.0 ratio on fresh client, got %f", stats.CompressionRatio)
	}
}

func TestWithProxyURL(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"messages": []map[string]string{
				{"role": "user", "content": "compressed"},
			},
		})
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	msgs, err := c.Compress(context.Background(), []cutctx.Message{
		{Role: "user", Content: "hello world"},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(msgs) == 0 {
		t.Fatal("expected at least one message in response")
	}
}
func TestCompress_SendsPostToCorrectPath(t *testing.T) {
	var gotMethod, gotPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod = r.Method
		gotPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"messages": []map[string]string{
				{"role": "assistant", "content": "compressed reply"},
			},
		})
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	msgs, err := c.Compress(context.Background(), []cutctx.Message{
		{Role: "user", Content: "test message"},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if gotMethod != http.MethodPost {
		t.Errorf("expected POST, got %s", gotMethod)
	}
	if gotPath != "/v1/compress" {
		t.Errorf("expected path /v1/compress, got %s", gotPath)
	}
	if len(msgs) != 1 || msgs[0].Content != "compressed reply" {
		t.Errorf("unexpected messages: %+v", msgs)
	}
	if c.Stats().RequestsTotal != 1 {
		t.Errorf("expected 1 request counted, got %d", c.Stats().RequestsTotal)
	}
}

func TestRetrieve_SendsGetToCorrectPath(t *testing.T) {
	var gotMethod, gotPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod = r.Method
		gotPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"content": "original stored content",
		})
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	content, err := c.Retrieve(context.Background(), "abc123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if gotMethod != http.MethodGet {
		t.Errorf("expected GET, got %s", gotMethod)
	}
	if gotPath != "/v1/retrieve/abc123" {
		t.Errorf("expected /v1/retrieve/abc123, got %s", gotPath)
	}
	if content != "original stored content" {
		t.Errorf("unexpected content: %q", content)
	}
}
func TestStats_ZerosOnFreshClient(t *testing.T) {
	c := cutctx.New()
	s := c.Stats()
	if s.TokensOriginal != 0 {
		t.Errorf("TokensOriginal: want 0, got %d", s.TokensOriginal)
	}
	if s.TokensCompressed != 0 {
		t.Errorf("TokensCompressed: want 0, got %d", s.TokensCompressed)
	}
	if s.RequestsTotal != 0 {
		t.Errorf("RequestsTotal: want 0, got %d", s.RequestsTotal)
	}
	if s.CompressionRatio != 0.0 {
		t.Errorf("CompressionRatio: want 0.0, got %f", s.CompressionRatio)
	}
}

func TestWithTimeout(t *testing.T) {
	// Server that delays beyond the configured timeout
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := cutctx.New(
		cutctx.WithProxyURL(srv.URL),
		cutctx.WithTimeout(50*time.Millisecond),
	)
	_, err := c.Compress(context.Background(), []cutctx.Message{{Role: "user", Content: "hi"}})
	if err == nil {
		t.Error("expected timeout error, got nil")
	}
}
