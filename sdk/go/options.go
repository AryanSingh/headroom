package cutctx

import "time"

// Option configures a Client
type Option func(*Client)

// WithProxyURL sets the Cutctx proxy base URL (default: http://localhost:8787)
func WithProxyURL(url string) Option {
	return func(c *Client) { c.proxyURL = url }
}

// WithAPIKey sets the Cutctx license key sent as X-Cutctx-Key header
func WithAPIKey(key string) Option {
	return func(c *Client) { c.apiKey = key }
}

// WithModel sets the target model name used for cost estimation
func WithModel(model string) Option {
	return func(c *Client) { c.model = model }
}

// WithTimeout sets the HTTP client timeout (default: 30s)
func WithTimeout(d time.Duration) Option {
	return func(c *Client) { c.httpClient.Timeout = d }
}
