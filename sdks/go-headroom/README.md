# go-cutctx

Go client for [Cutctx](https://cutctx.sh) — route LLM API calls through the Cutctx proxy for automatic context compression.

## Installation

```bash
go get github.com/cutctx-labs/go-cutctx
```

## Usage

```go
package main

import (
	"fmt"
	"net/http"
	"strings"

	cutctx "github.com/cutctx-labs/go-cutctx"
)

func main() {
	// Create a Cutctx client proxying through localhost:8080
	client := cutctx.NewClient("http://localhost:8080")

	// Build your LLM API request as usual
	body := strings.NewReader(`{
		"model": "claude-3-5-sonnet-20241022",
		"max_tokens": 1024,
		"messages": [{"role": "user", "content": "Hello, world!"}]
	}`)

	req, err := http.NewRequest("POST", "https://api.anthropic.com/v1/messages", body)
	if err != nil {
		panic(err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", "your-anthropic-api-key")
	req.Header.Set("anthropic-version", "2023-06-01")

	// Execute through Cutctx — context is automatically compressed
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	fmt.Println("Status:", resp.Status)
	// Response body contains the LLM output as usual
}
```

## Using as an HTTP Transport

You can also use the Cutctx client as an `http.RoundTripper`:

```go
client := &http.Client{
	Transport: cutctx.NewClient("http://localhost:8080"),
}

resp, err := client.Post("https://api.anthropic.com/v1/messages", "application/json", body)
```

## How It Works

1. **Cutctx proxy** runs locally on port 8080 (or any port)
2. The Go client **rewrites requests** to route through the proxy
3. Cutctx **compresses prompt context** before forwarding to the model provider
4. You get **60-95% fewer tokens** with minimal quality loss

```
Your Go App → Cutctx Proxy (localhost:8080) → LLM Provider (Anthropic/OpenAI/etc.)
                   ↓
            Context compression
            Token count reduction
            Cache alignment
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `CUTCTX_PROXY_URL` | Proxy URL | `http://localhost:8080` |

## Agent Compatibility

Cutctx works with any HTTP client that supports proxy configuration:

- Claude Code
- OpenAI Codex
- Cursor
- Aider
- GitHub Copilot CLI
- Custom Go applications

## License

Apache 2.0
