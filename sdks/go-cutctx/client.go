// Package cutctx provides a Go client for the Cutctx AI context compression proxy.
//
// Cutctx reduces LLM API token usage by 60-95% by compressing prompt context
// before forwarding requests to the model provider.
package cutctx

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
)

// Client wraps an HTTP client to route requests through a Cutctx proxy.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// Option configures the client.
type Option func(*Client)

// WithHTTPClient sets a custom HTTP client.
func WithHTTPClient(c *http.Client) Option {
	return func(cl *Client) { cl.httpClient = c }
}

// WithBaseURL overrides the proxy base URL.
func WithBaseURL(u string) Option {
	return func(cl *Client) { cl.baseURL = u }
}

// NewClient creates a new Cutctx client that routes requests through the given proxy URL.
func NewClient(proxyURL string, opts ...Option) *Client {
	cl := &Client{
		baseURL:    proxyURL,
		httpClient: http.DefaultClient,
	}
	for _, o := range opts {
		o(cl)
	}
	return cl
}

// proxyRewrite rewrites a target URL to go through the proxy.
func (c *Client) proxyRewrite(target *url.URL) (*url.URL, error) {
	proxyURL, err := url.Parse(c.baseURL)
	if err != nil {
		return nil, fmt.Errorf("cutctx: invalid proxy URL: %w", err)
	}

	// Build the proxied URL
	q := target.Query()
	q.Set("_target", target.String())

	return &url.URL{
		Scheme:   proxyURL.Scheme,
		Host:     proxyURL.Host,
		Path:     proxyURL.Path + target.Path,
		RawQuery: q.Encode(),
	}, nil
}

// Do executes an HTTP request through the Cutctx proxy.
// The original request URL is passed to the proxy so it can forward to the correct upstream.
func (c *Client) Do(req *http.Request) (*http.Response, error) {
	if c.baseURL == "" {
		return nil, fmt.Errorf("cutctx: ProxyURL is required")
	}

	// Store the original target URL
	originalURL := req.URL.String()

	// Rewrite request to go through the proxy
	proxyURL, err := url.Parse(c.baseURL)
	if err != nil {
		return nil, fmt.Errorf("cutctx: invalid proxy URL: %w", err)
	}

	req.URL.Scheme = proxyURL.Scheme
	req.URL.Host = proxyURL.Host
	req.URL.Path = proxyURL.Path + req.URL.Path

	// Pass the original URL as a query parameter for the proxy to forward to
	q := req.URL.Query()
	q.Set("_target", originalURL)
	req.URL.RawQuery = q.Encode()

	client := c.httpClient
	if client == nil {
		client = http.DefaultClient
	}

	return client.Do(req)
}

// RoundTrip implements the http.RoundTripper interface, allowing the client
// to be used as a transport for http.Client or as an HTTP proxy.
func (c *Client) RoundTrip(req *http.Request) (*http.Response, error) {
	return c.Do(req)
}

// Convenience methods

// Get sends a GET request through the proxy.
func (c *Client) Get(targetURL string) (*http.Response, error) {
	req, err := http.NewRequest("GET", targetURL, nil)
	if err != nil {
		return nil, err
	}
	return c.Do(req)
}

// Post sends a POST request through the proxy.
// The body parameter accepts an io.Reader for streaming request bodies.
func (c *Client) Post(targetURL, contentType string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequest("POST", targetURL, body)
	if err != nil {
		return nil, err
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	return c.Do(req)
}
