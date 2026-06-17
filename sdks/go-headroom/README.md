# go-headroom

Go client for [Headroom](https://headroom.sh) — route LLM API calls through the Headroom proxy for automatic context compression.

## Installation

```bash
go get github.com/headroom-labs/go-headroom
```

## Usage

```go
package main

import (
	"fmt"
	"net/http"
	"strings"

	headroom "github.com/headroom-labs/go-headroom"
)

func main() {
	// Create a Headroom client proxying through localhost:8080
	client := headroom.NewClient("http://localhost:8080")

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

	// Execute through Headroom — context is automatically compressed
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

You can also use the Headroom client as an `http.RoundTripper`:

```go
client := &http.Client{
	Transport: headroom.NewClient("http://localhost:8080"),
}

resp, err := client.Post("https://api.anthropic.com/v1/messages", "application/json", body)
```

## How It Works

1. **Headroom proxy** runs locally on port 8080 (or any port)
2. The Go client **rewrites requests** to route through the proxy
3. Headroom **compresses prompt context** before forwarding to the model provider
4. You get **60-95% fewer tokens** with minimal quality loss

```
Your Go App → Headroom Proxy (localhost:8080) → LLM Provider (Anthropic/OpenAI/etc.)
                   ↓
            Context compression
            Token count reduction
            Cache alignment
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `HEADROOM_PROXY_URL` | Proxy URL | `http://localhost:8080` |

## Agent Compatibility

Headroom works with any HTTP client that supports proxy configuration:

- Claude Code
- OpenAI Codex
- Cursor
- Aider
- GitHub Copilot CLI
- Custom Go applications

## License

Apache 2.0
