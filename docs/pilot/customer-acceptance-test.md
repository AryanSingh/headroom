# Customer Acceptance Test

Run this test from a clean supported installation. Replace example hosts,
models, and tokens with customer-approved test values. Keep provider spend
bounded.

## 1. Configuration and health

```bash
cutctx config-check
curl --fail --silent https://cutctx.customer.example/readyz
```

Expected: configuration reports no blocking issue and `/readyz` returns a
successful response.

## 2. Authentication rejection

```bash
curl --fail-with-body https://cutctx.customer.example/v1/models
```

Expected: the network proxy rejects the request. A valid provider request must
send `X-Cutctx-Proxy-Key` with the `CUTCTX_PROXY_API_KEY` value.

## 3. OpenAI and Codex path

Configure Codex or an OpenAI-compatible SDK with the Cutctx base URL and proxy
key. Send a small non-streaming request and a streaming request. Confirm the
provider response, tool-call fields, finish reason, and model record remain
valid.

## 4. Anthropic and Claude Code path

Configure Claude Code or an Anthropic-compatible SDK with the Cutctx base URL
and proxy key. Send a message with a tool definition, then run one streaming
message. Confirm the content blocks and stop reason match Anthropic semantics.

## 5. Claude Desktop MCP path

```bash
cutctx mcp install --gateway
cutctx mcp status
```

Restart Claude Desktop when requested. Invoke an MCP tool that returns a large
structured payload. Confirm the gateway reports compression or safe
pass-through and that retrieval markers remain usable. Claude Desktop hosted
model traffic does not enter the proxy.

## 6. Operator evidence

Confirm health, request count, routed model, error status, latency, and savings
appear in metrics or the dashboard. Confirm logs omit provider credentials,
license keys, authorization headers, and prompt bodies.

## 7. Recovery and rollback

Create a pilot backup, perform the documented restore check, deploy the current
candidate over the previous image, and perform a rollback to the previous image
or package. Repeat the `/readyz` check after each operation.

## 8. Removal

```bash
cutctx mcp uninstall
```

Stop and remove the proxy through the selected deployment procedure. Confirm
the installer preserves unrelated Codex, Claude Code, and Claude Desktop
configuration.

Record the result, evidence path, customer approver, date, and unresolved risk.

