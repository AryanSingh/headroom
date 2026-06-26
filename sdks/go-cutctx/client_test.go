package cutctx

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestNewClient(t *testing.T) {
	cl := NewClient("http://localhost:8080")
	if cl.baseURL != "http://localhost:8080" {
		t.Errorf("expected baseURL http://localhost:8080, got %s", cl.baseURL)
	}
	if cl.httpClient == nil {
		t.Error("expected httpClient to be non-nil")
	}
}

func TestNewClientWithOptions(t *testing.T) {
	custom := &http.Client{Timeout: 5 * time.Second}
	cl := NewClient("http://proxy:9090", WithHTTPClient(custom), WithBaseURL("http://other:3000"))
	if cl.baseURL != "http://other:3000" {
		t.Errorf("expected baseURL http://other:3000, got %s", cl.baseURL)
	}
	if cl.httpClient != custom {
		t.Error("expected custom httpClient")
	}
}

func TestProxyRewrite(t *testing.T) {
	cl := NewClient("http://proxy:8080")
	target, _ := url.Parse("https://api.openai.com/v1/chat/completions")
	proxyURL, err := cl.proxyRewrite(target)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if proxyURL.Host != "proxy:8080" {
		t.Errorf("expected host proxy:8080, got %s", proxyURL.Host)
	}
	if proxyURL.Query().Get("_target") != "https://api.openai.com/v1/chat/completions" {
		t.Errorf("expected _target parameter, got %s", proxyURL.Query().Get("_target"))
	}
}

func TestDoRequest(t *testing.T) {
	var receivedTarget string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedTarget = r.URL.Query().Get("_target")
		w.WriteHeader(200)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer ts.Close()

	cl := NewClient(ts.URL)
	req, _ := http.NewRequest("GET", "https://api.example.com/data", nil)
	resp, err := cl.Do(req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if receivedTarget != "https://api.example.com/data" {
		t.Errorf("expected _target=https://api.example.com/data, got %s", receivedTarget)
	}
	if resp.StatusCode != 200 {
		t.Errorf("expected status 200, got %d", resp.StatusCode)
	}
}

func TestRoundTrip(t *testing.T) {
	var receivedTarget string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedTarget = r.URL.Query().Get("_target")
		w.WriteHeader(200)
	}))
	defer ts.Close()

	cl := NewClient(ts.URL, WithHTTPClient(&http.Client{
		Transport: &http.Transport{},
	}))
	req, _ := http.NewRequest("POST", "https://api.openai.com/v1/embeddings", nil)
	resp, err := cl.RoundTrip(req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if receivedTarget != "https://api.openai.com/v1/embeddings" {
		t.Errorf("expected _target=https://api.openai.com/v1/embeddings, got %s", receivedTarget)
	}
}

func TestGetConvenience(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("hello"))
	}))
	defer ts.Close()

	cl := NewClient(ts.URL)
	resp, err := cl.Get("https://api.example.com/test")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Errorf("expected status 200, got %d", resp.StatusCode)
	}
}

func TestProxyRewriteWithPath(t *testing.T) {
	cl := NewClient("http://proxy:8080")
	target, _ := url.Parse("https://api.openai.com/v1/models?limit=10")
	proxyURL, err := cl.proxyRewrite(target)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if proxyURL.Path != "/v1/models" {
		t.Errorf("expected path /v1/models, got %s", proxyURL.Path)
	}
	if proxyURL.Query().Get("limit") != "10" {
		t.Errorf("expected limit=10 in query, got %s", proxyURL.RawQuery)
	}
}

func TestPostConvenience(t *testing.T) {
	var receivedContentType string
	var receivedBody string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedContentType = r.Header.Get("Content-Type")
		body, _ := io.ReadAll(r.Body)
		receivedBody = string(body)
		w.WriteHeader(200)
	}))
	defer ts.Close()

	cl := NewClient(ts.URL)
	body := strings.NewReader(`{"prompt":"hello"}`)
	resp, err := cl.Post("https://api.example.com/data", "application/json", body)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if receivedContentType != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", receivedContentType)
	}
	if receivedBody != `{"prompt":"hello"}` {
		t.Errorf("expected body {\"prompt\":\"hello\"}, got %s", receivedBody)
	}
}
