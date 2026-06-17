# Headroom Go SDK Tests

## Running Tests

```bash
cd sdks/go-headroom
go test -v ./...
```

## Test Coverage

| Test | Description |
|------|-------------|
| TestNewClient | Verify default URL and HTTP client |
| TestNewClientWithOptions | Verify custom URL and HTTP client options |
| TestProxyRewrite | Verify URL rewriting with _target parameter |
| TestProxyRewriteWithPath | Verify path and query string preservation |
| TestDoRequest | Verify proxy routing via Do() method |
| TestRoundTrip | Verify http.RoundTripper implementation |
| TestGetConvenience | Verify Get() convenience method |
| TestPostConvenience | Verify Post() convenience method with Content-Type |

## Architecture

```
Client → proxyRewrite() → Headroom Proxy → Target API
         (adds _target)    (compresses)     (receives original)
```

The client rewrites all request URLs to route through the Headroom proxy.
The proxy intercepts the request, compresses the context, and forwards to the target.
