# ChatGPT Subscription Continuation Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Codex ChatGPT-subscription retries from being falsely rejected, destructively truncated, or moved to another model when they contain opaque continuation state.

**Architecture:** Add one recursive shape predicate for opaque Responses continuation items. Use it at the HTTP and WebSocket context-guard boundaries so subscription continuations are forwarded unchanged, while ordinary/API-key payloads retain existing guards. Apply the existing transport-safe routing restriction to subscription HTTP requests as well as WebSockets.

**Tech Stack:** Python 3.14, FastAPI, pytest, AnyIO, mocked WebSocket lifecycle tests, live CutCtx proxy wrappers.

## Global Constraints

- Preserve the requested model for ChatGPT-subscription traffic across WebSocket and HTTP transports.
- Treat approximate local token counts as advisory for opaque subscription continuations.
- Do not mutate encrypted continuation state.
- Preserve existing routing and context-guard behavior for ordinary API-key traffic.
- Do not overwrite unrelated dirty-worktree changes.

---

### Task 1: Reproduce the Subscription Continuation Failures

**Files:**
- Modify: `tests/test_openai_codex_ws_lifecycle.py`
- Modify: `tests/test_openai_codex_routing.py`

**Interfaces:**
- Consumes: `OpenAIHandlerMixin.handle_openai_responses_ws`, `OpenAIHandlerMixin.handle_openai_responses`
- Produces: regression coverage for opaque WebSocket forwarding and HTTP model preservation

- [ ] **Step 1: Add a failing WebSocket regression**

Create a ChatGPT-authenticated `response.create` frame whose `input` includes a reasoning item with `encrypted_content`. Force `_openai_responses_context_guard` to report the observed false-positive estimate `(True, 294402, 242400, 258400)`. Assert that the upstream receives the frame and the client is not closed with code `1009`.

- [ ] **Step 2: Run the WebSocket regression and verify RED**

Run: `rtk pytest tests/test_openai_codex_ws_lifecycle.py -k opaque_continuation -q`

Expected: FAIL because the current handler closes the client instead of forwarding the frame.

- [ ] **Step 3: Add a failing HTTP regression**

Send the same opaque continuation with ChatGPT subscription headers and a router configured to downgrade `gpt-5.6-sol`. Assert the captured upstream body still uses `gpt-5.6-sol`, retains `encrypted_content`, and bypasses emergency truncation even when the local guard returns the observed false-positive estimate.

- [ ] **Step 4: Run the HTTP regression and verify RED**

Run: `rtk pytest tests/test_openai_codex_routing.py -k opaque_continuation -q`

Expected: FAIL because transport-safe HTTP routing currently selects `gpt-5.6-luna` or the context guard truncates/refuses the request.

### Task 2: Preserve Opaque Subscription Continuations

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Test: `tests/test_openai_codex_ws_lifecycle.py`
- Test: `tests/test_openai_codex_routing.py`

**Interfaces:**
- Produces: `_contains_opaque_responses_continuation(payload: Any) -> bool`
- Consumes: `is_chatgpt_auth`, `is_chatgpt_subscription`, `prepare_model_routing`

- [ ] **Step 1: Add the minimal shape predicate**

Implement a bounded recursive walk over dictionaries and lists that returns `True` when it finds a non-empty `encrypted_content` field. Do not inspect, log, decode, truncate, or copy the encrypted value.

- [ ] **Step 2: Preserve the subscription HTTP model**

Pass `allow_transport_safe_targets=not is_chatgpt_subscription` to the HTTP `prepare_model_routing` call, matching the existing WebSocket policy.

- [ ] **Step 3: Make the HTTP context guard advisory for opaque subscription state**

Skip emergency truncation/refusal only when both ChatGPT subscription authentication and the opaque predicate are true. Log bounded metadata containing model, estimate, threshold, and context limit without payload content.

- [ ] **Step 4: Make all WebSocket context-refusal sites advisory for opaque subscription state**

Apply the same condition to the first-frame guard, compression-failure guard, no-op guard, and post-compression guard. Forward the original/sanitized frame without mutating opaque state.

- [ ] **Step 5: Run the two regressions and verify GREEN**

Run: `rtk pytest tests/test_openai_codex_ws_lifecycle.py -k opaque_continuation -q && rtk pytest tests/test_openai_codex_routing.py -k opaque_continuation -q`

Expected: all selected tests pass.

### Task 3: Regression and Runtime Verification

**Files:**
- Modify: `audit/bug-report.md`

**Interfaces:**
- Consumes: project test suites, installed CutCtx wrapper commands, live proxy logs
- Produces: fresh evidence for unit, integration, and CLI behavior

- [ ] **Step 1: Run focused Responses and routing suites**

Run: `rtk pytest tests/test_openai_codex_ws_lifecycle.py tests/test_openai_codex_routing.py tests/test_openai_responses_context_compaction.py tests/test_model_router.py -q`

Expected: zero failures.

- [ ] **Step 2: Run broader proxy tests and lint**

Run the relevant OpenAI proxy suite discovered from the repository, followed by `rtk ruff check` on the modified Python files.

Expected: zero failures and zero lint errors.

- [ ] **Step 3: Restart and health-check the live proxy**

Use the repository's documented non-interactive restart command, confirm the new process is healthy, and confirm logs show the expected preset and model policy.

- [ ] **Step 4: Smoke-test the three clients**

Run non-interactive wrapped requests through Codex, Claude CLI, and OpenCode. Use safe read-only prompts and timeouts. Confirm each exits successfully and the proxy logs show no new `Bad Request`, `context_refused`, or subscription model rewrite for the test requests.

- [ ] **Step 5: Record the evidence**

Update `audit/bug-report.md` with reproduction steps, expected versus actual behavior, severity, root cause, implemented fix, and verification evidence.

- [ ] **Step 6: Inspect the final diff and commit only scoped files**

Use `rtk git diff --check`, inspect the scoped diff, and commit the implementation/tests/report without staging unrelated user changes.
