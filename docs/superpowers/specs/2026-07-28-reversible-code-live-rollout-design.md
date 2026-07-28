# Reversible Code Compression Live Rollout Design

## Goal

Enable CCR-backed, reversible Python code compression by default for new Cutctx
proxy processes and let an authenticated administrator enable or disable it in
an already-running proxy without dropping active Codex or ChatGPT sessions.

## Decision

The proxy will keep a default configuration value of `True` for reversible code
compression. The existing `/config/flags` and `/admin/config/flags` management
surfaces will expose `reversible_code`; a POST updates the live
`ContentRouterConfig` instances in the already-created Anthropic and OpenAI
pipelines. This is an in-process assignment only: it does not restart Uvicorn,
close upstream clients, drain the connection pool, or close WebSockets.

The setting affects only future compression decisions. A request already being
processed retains the router configuration it read at the start of its unit
compression. Every transformed Python body still must be CCR-stored,
parseable after elision, structurally safe, and smaller on the wire; otherwise
the original content is forwarded unchanged.

## Safety boundary

- Do not add extraction coverage for user, assistant, reasoning, compaction,
  or tool-call arguments.
- Do not turn on existing lossy `code_aware` compression as part of this work.
- Do not alter existing WebSocket connections or restart the process during
  runtime activation.
- Keep a live kill switch: `POST /admin/config/flags` with
  `{ "reversible_code": false }` takes effect for future requests immediately.

## Verification design

Tests prove four claims:

1. New `ProxyConfig` instances default to enabled, while an explicit `False`
   keeps byte-preserving behavior.
2. The authenticated flag API reflects and updates both pipeline routers in
   process, and rejects unauthenticated requests.
3. A real OpenAI Responses function-call output gains a CCR marker only after
   enablement; non-Python, parse-invalid, nested-definition, small, and opaque
   payloads remain unchanged.
4. A fake active WebSocket survives a live toggle and forwards frames before
   and after the update without close or restart calls.

The rollout validation runs focused contract, HTTP, and WebSocket tests, then
the full repository suite and the pinned Ruff version. Live activation uses
the existing local admin endpoint, snapshots `/livez` and active WebSocket
session count before and after, and does not send a signal to the proxy PID.
