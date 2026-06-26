package cutctx

import (
	"net/http"
	"strings"
)

// Middleware returns an http.Handler that intercepts LLM API calls
// and routes them through the Cutctx proxy.
//
// Usage:
//
//	client := cutctx.New(cutctx.WithProxyURL("http://localhost:8787"))
//	handler := cutctx.Middleware(client)(myHandler)
func Middleware(c *Client) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if shouldIntercept(r) {
				r = r.Clone(r.Context())
				r.Header.Set("X-Cutctx-Key", c.apiKey)
			}
			next.ServeHTTP(w, r)
		})
	}
}

// shouldIntercept determines if a request should be routed through Cutctx.
func shouldIntercept(r *http.Request) bool {
	host := r.URL.Hostname()
	if strings.HasSuffix(host, "api.anthropic.com") ||
		strings.HasSuffix(host, "api.openai.com") ||
		strings.HasSuffix(host, "generativelanguage.googleapis.com") {
		return true
	}
	// Intercept POST to known LLM paths on the proxy itself
	if r.Method == http.MethodPost {
		path := r.URL.Path
		return strings.HasPrefix(path, "/v1/messages") ||
			strings.HasPrefix(path, "/v1/chat/completions") ||
			strings.HasPrefix(path, "/v1/completions")
	}
	return false
}
