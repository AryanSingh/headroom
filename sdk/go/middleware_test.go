package cutctx_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	cutctx "github.com/cutctx/cutctx-go"
)

func TestMemoryClient_Store(t *testing.T) {
	var gotBody map[string]string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&gotBody)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok": true}`))
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	err := c.Memory().Store(context.Background(), "test memory", "my-project")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if gotBody["content"] != "test memory" {
		t.Errorf("expected content 'test memory', got %q", gotBody["content"])
	}
}

func TestMemoryClient_Search(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"entries": []map[string]string{
				{"id": "1", "content": "found memory"},
			},
		})
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	entries, err := c.Memory().Search(context.Background(), "test query", 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(entries))
	}
	if entries[0].Content != "found memory" {
		t.Errorf("unexpected content: %q", entries[0].Content)
	}
}

func TestMemoryClient_List(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("expected GET, got %s", r.Method)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"entries": []map[string]string{},
		})
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	entries, err := c.Memory().List(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(entries) != 0 {
		t.Errorf("expected 0 entries, got %d", len(entries))
	}
}

func TestMemoryClient_Error(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"detail": "server error"}`))
	}))
	defer srv.Close()

	c := cutctx.New(cutctx.WithProxyURL(srv.URL))
	err := c.Memory().Store(context.Background(), "test", "")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestMiddleware_InterceptsLLMRequest(t *testing.T) {
	var gotHeaders http.Header

	c := cutctx.New(
		cutctx.WithProxyURL("http://localhost:9999"),
		cutctx.WithAPIKey("test-key"),
	)

	handler := cutctx.Middleware(c)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotHeaders = r.Header
		w.WriteHeader(http.StatusOK)
	}))

	// Create request to Anthropic API
	req := httptest.NewRequest(http.MethodPost, "https://api.anthropic.com/v1/messages", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if gotHeaders.Get("X-Cutctx-Key") != "test-key" {
		t.Errorf("expected X-Cutctx-Key header, got %q", gotHeaders.Get("X-Cutctx-Key"))
	}
}

func TestMiddleware_SkipsNonLLMRequest(t *testing.T) {
	var gotHeaders http.Header
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotHeaders = r.Header
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := cutctx.New(
		cutctx.WithProxyURL(srv.URL),
		cutctx.WithAPIKey("test-key"),
	)

	handler := cutctx.Middleware(c)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Create request to non-LLM API
	req := httptest.NewRequest(http.MethodGet, "https://example.com/api/data", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if gotHeaders.Get("X-Cutctx-Key") != "" {
		t.Errorf("expected no X-Cutctx-Key header for non-LLM request")
	}
}

func TestNewProxyClient(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := cutctx.NewProxyClient(cutctx.ProxyConfig{
		ProxyURL: srv.URL,
		APIKey:   "test",
	})
	if c == nil {
		t.Fatal("expected non-nil client")
	}
}
