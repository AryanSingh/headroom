# Codex Responses Content-Encoding Normalization

## Problem

Codex Desktop sends some `/v1/responses` requests with `Content-Encoding: zstd`.
Cutctx decodes that payload before parsing it, then forwards a JSON body to the
ChatGPT subscription Responses endpoint while retaining the original
`Content-Encoding` header. The upstream therefore attempts to decode ordinary
JSON as zstd and rejects the request with HTTP 400.

## Decision

Normalize request headers at the OpenAI Responses forwarding boundary: after
Cutctx has decoded the inbound body, remove `content-encoding` along with
`content-length`, `host`, and `accept-encoding` before any upstream request is
made. HTTPX will calculate the new content length for the serialized JSON.

The proxy will not recompress the outgoing body. Recompression would add a
second encoding path and risks future header/body divergence without providing
an upstream compatibility benefit.

## Scope and behavior

- Applies only to the OpenAI Responses handler's upstream-bound request
  headers.
- Preserves all provider-authentication, Codex attestation, request identity,
  and feature headers.
- Does not alter inbound decompression, model routing, context handling, or
  response-header normalization.

## Verification

Add a regression test using a zstd-encoded inbound Responses request. It must
prove that the handler decodes the payload and that the mocked upstream sees:

- valid JSON body content;
- no `content-encoding` header; and
- no stale `content-length` header.

Run the focused regression test, the relevant OpenAI Responses test module,
and Ruff against changed Python files.

## Non-goals

- Recompressing outbound requests.
- Changing ChatGPT subscription authentication or model selection.
- Altering unrelated Anthropic, Gemini, or OpenAI Chat Completions forwarding.
