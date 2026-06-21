# cutctx-go

Go SDK for [CutCtx](https://cutctx.dev) — AI context compression proxy.

## Quickstart

```go
import cutctx "github.com/cutctx/cutctx-go"

client := cutctx.New(
    cutctx.WithAPIKey(os.Getenv("CUTCTX_LICENSE_KEY")),
)
compressed, err := client.Compress(ctx, messages)
// Use compressed messages with your LLM client — tokens reduced 60–95%
```

## Installation

```
go get github.com/cutctx/cutctx-go
```

## Options

| Option | Default | Description |
|---|---|---|
| `WithProxyURL(url)` | `http://localhost:8787` | CutCtx proxy base URL |
| `WithAPIKey(key)` | `""` | License key sent as `X-CutCtx-Key` header |
| `WithModel(model)` | `claude-sonnet-4-6` | Target model for cost estimation |
| `WithTimeout(d)` | `30s` | HTTP client timeout |

## API

### `Compress(ctx, messages) ([]Message, error)`

POST `/v1/compress` — returns semantically compressed messages.

### `Retrieve(ctx, ref) (string, error)`

GET `/v1/retrieve/{ref}` — fetches original content for a `[cutctx:ref:HASH]` pointer.

### `Stats() Stats`

Returns lifetime statistics: `TokensOriginal`, `TokensCompressed`, `RequestsTotal`, `CompressionRatio`.

## Shared Context

Thread-safe key-value store for sharing context across operations:

```go
sc := cutctx.NewSharedContext()
sc.Put("project", "my-app")
val, ok := sc.Get("project")  // ("my-app", true)
stats := sc.Stats()            // SharedStats{Entries: 1, Keys: ["project"]}
sc.Clear()
```

### `SharedContext` API

| Method | Description |
|---|---|
| `Put(key, value)` | Store a key-value pair |
| `Get(key) (string, bool)` | Retrieve a value by key |
| `List() map[string]string` | Return a copy of all entries |
| `Clear()` | Remove all entries |
| `Stats() SharedStats` | Get entry count and sorted keys |
