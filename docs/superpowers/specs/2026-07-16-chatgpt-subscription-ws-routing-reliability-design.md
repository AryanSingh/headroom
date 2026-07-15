# ChatGPT Subscription Continuation Reliability

## Problem

The `codex-gpt54mini-high` preset can rewrite a Codex ChatGPT-subscription
turn from the model requested by Codex (for example, `gpt-5.6-sol`) to a
different model. That is unsafe when the turn contains opaque or encrypted
continuation state produced by the requested model.

Session `019f6752-d143-7e70-b780-34396670b634` exposed a second failure in the
same boundary. Its live WebSocket turn reported roughly 194,000 input tokens,
but after the connection ended CutCtx's generic tokenizer estimated the rebuilt
944 KB continuation frame at 294,402 tokens. CutCtx refused the WebSocket retry
against a 242,400-token threshold. Codex then used HTTP fallback, where CutCtx
rewrote `gpt-5.6-sol` to `gpt-5.6-luna`; ChatGPT rejected the model-bound
continuation with HTTP 400.

## Design

ChatGPT-subscription requests retain their requested model across both
WebSocket and HTTP transports. The existing router remains active for API-key
OpenAI traffic and continues to expose routing metadata. Transport support for
a target model is not treated as proof that opaque continuation state can move
between models.

The local Responses context guard remains available for ordinary payloads, but
it does not hard-refuse or trigger destructive emergency truncation for a
ChatGPT-subscription continuation containing opaque encrypted state. The proxy
forwards that request unchanged and lets ChatGPT's authoritative tokenizer and
context-management path accept it or return a precise upstream context error.
CutCtx must not turn an uncertain estimate into a corrupted request.

The initial WebSocket frame, later `response.create` frames, and HTTP fallback
all use the same model-preservation policy. Upstream WebSocket error frames log
a bounded error type and message for diagnosis without logging request content,
encrypted state, or credentials.

## Error Handling

- Approximate local token counts for opaque subscription continuations are
  advisory only.
- Genuine upstream context-limit errors are relayed without changing the model
  or destructively pruning encrypted continuation state.
- Non-subscription/API-key requests retain current routing, context guarding,
  and emergency truncation behavior.

## Verification

- A regression test reproduces the observed false-positive context estimate and
  proves an opaque ChatGPT-subscription WebSocket continuation is forwarded.
- A regression test proves HTTP fallback keeps `gpt-5.6-sol` for the same
  continuation instead of routing it to `gpt-5.6-luna`.
- Existing tests continue to prove API-key routing can select a configured
  lower-cost model and ordinary non-opaque context guards still operate.
- Existing model-router and OpenAI handler tests remain green.
- The live proxy is restarted with the same preset and its health endpoint,
  request logs, and a fresh continuation/retry turn are checked.
