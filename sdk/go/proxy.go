package cutctx

import (
	"net/http"
	"net/url"
	"strings"
)

// CutctxTransport is an http.RoundTripper that routes LLM API calls
// through the Cutctx proxy for automatic compression.
type CutctxTransport struct {
	ProxyURL string
	Wrapped  http.RoundTripper
	APIKey   string
}

// RoundTrip implements http.RoundTripper.
func (t *CutctxTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	if isLLMRequest(req) {
		req = req.Clone(req.Context())
		proxyURL, err := url.Parse(t.ProxyURL)
		if err == nil {
			req.URL.Host = proxyURL.Host
			req.URL.Scheme = proxyURL.Scheme
		}
		if t.APIKey != "" {
			req.Header.Set("X-Cutctx-Key", t.APIKey)
		}
	}
	if t.Wrapped != nil {
		return t.Wrapped.RoundTrip(req)
	}
	return http.DefaultTransport.RoundTrip(req)
}

// isLLMRequest checks if the request targets a known LLM API.
func isLLMRequest(req *http.Request) bool {
	host := req.URL.Hostname()
	return strings.HasSuffix(host, "api.anthropic.com") ||
		strings.HasSuffix(host, "api.openai.com") ||
		strings.HasSuffix(host, "generativelanguage.googleapis.com")
}

// ProxyConfig holds configuration for creating a proxy-aware HTTP client.
type ProxyConfig struct {
	ProxyURL string
	APIKey   string
	Wrapped  http.RoundTripper
}

// NewProxyClient creates an http.Client that routes LLM calls through the proxy.
func NewProxyClient(cfg ProxyConfig) *http.Client {
	transport := &CutctxTransport{
		ProxyURL: cfg.ProxyURL,
		Wrapped:  cfg.Wrapped,
		APIKey:   cfg.APIKey,
	}
	return &http.Client{Transport: transport}
}
