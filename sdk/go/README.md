# CutCtx Go SDK

A Go client for the [CutCtx](https://cutctx.dev) context compression proxy.

CutCtx compresses LLM context windows by 50-70% with zero quality loss. This SDK communicates with the CutCtx proxy HTTP API — no native bindings needed.

## Quickstart

```go
package main

import (
    "context"
    "fmt"
    "log"

    cutctx "github.com/AryanSingh/cutcxt/sdk/go"
)

func main() {
    client := cutctx.New(
        cutctx.WithProxyURL("http://localhost:8787"),
        cutctx.WithAPIKey("your-api-key"),
    )

    messages := []cutctx.Message{
        {Role: "user", Content: "Explain quantum computing in simple terms."},
    }

    compressed, err := client.Compress(context.Background(), messages)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Compressed %d messages\n", len(compressed))
}
```

## API

### `New(opts ...Option) *Client`

Create a new client.

| Option | Default | Description |
|--------|---------|-------------|
| `WithProxyURL(url)` | `http://localhost:8787` | CutCtx proxy URL |
| `WithAPIKey(key)` | `""` | Upstream LLM API key |
| `WithModel(model)` | `claude-sonnet-4-20250514` | Model name for compression |
| `WithHTTPClient(c)` | default | Custom HTTP client |
| `WithTimeout(d)` | `30s` | HTTP timeout |

### `client.Compress(ctx, messages) ([]Message, error)`

Compress messages through the CutCtx proxy. Returns compressed messages.

### `client.Retrieve(ctx, ref) (string, error)`

Retrieve original content for a CCR reference (e.g., `<<ccr:abc123>>`).

### `client.Stats(ctx) (*Stats, error)`

Get compression statistics from the proxy.

## Requirements

- Go 1.21+
- CutCtx proxy running (see [docs](https://cutctx.dev/docs))

## Testing

```bash
go test ./sdk/go/...
```
