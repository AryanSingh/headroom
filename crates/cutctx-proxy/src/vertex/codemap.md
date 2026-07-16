# crates/cutctx-proxy/src/vertex/

## Responsibility
Adapts Vertex AI Anthropic `:rawPredict` and `:streamRawPredict` routes with Application Default Credential authentication and live-zone compression.

## Design
`TokenSource` abstracts bearer acquisition; `GcpAdcTokenSource` lazily resolves ADC and refreshes cached tokens. Envelope helpers preserve Vertex-required fields. A shared dispatcher distinguishes verbs and forwards through one implementation; streaming attaches the Anthropic SSE tee.

## Flow
Route extracts project/location/model/verb -> token source returns a bearer -> parse Vertex envelope and compress inner Anthropic payload -> forward to Vertex with authorization -> return JSON unchanged or stream SSE bytes with non-blocking telemetry parsing.

## Integration
- Registered by the proxy router and configured through `AppState`.
- Uses `compression/`, `sse/anthropic`, GCP auth, headers, and observability.
