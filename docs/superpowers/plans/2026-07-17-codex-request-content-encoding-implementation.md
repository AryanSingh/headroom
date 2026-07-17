# Codex Responses Content-Encoding Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent ChatGPT subscription Responses requests from retaining a stale request-compression header after Cutctx decodes their body.

**Architecture:** The OpenAI Responses handler receives decoded JSON from `read_request_json_with_bytes`, then forwards it upstream. Normalize the upstream-only header copy at that boundary so `Content-Encoding` cannot describe an already-decoded body. Preserve all other Codex subscription headers.

**Tech Stack:** Python 3.11, FastAPI/Starlette, HTTPX, pytest, Ruff.

## Global Constraints

- Remove only stale request transport metadata; retain authorization, Codex attestation, session, and feature headers.
- Do not recompress outbound request bodies.
- Keep the change within the OpenAI Responses forwarding path.
- Preserve the unrelated untracked `audit/competitor-report-2026-07-17.md`.

---

### Task 1: Normalize decoded Responses request headers

**Files:**

- Modify: `tests/test_proxy_openai_responses_integration.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py:2560-2566`

**Interfaces:**

- Consumes: `Request.headers`, which may include `content-encoding: zstd` even though `read_request_json_with_bytes` has produced decoded JSON.
- Produces: an upstream header mapping that omits `host`, `content-length`, `content-encoding`, and `accept-encoding` while retaining safe provider and Codex headers.

- [ ] **Step 1: Write the failing regression test**

Add a focused Responses integration test that builds a zstd-encoded request with a small valid `input` payload, invokes the handler with a mocked upstream transport, and asserts:

```python
assert captured_body["input"][0]["content"] == "header normalization regression"
assert "content-encoding" not in {key.lower() for key in captured_headers}
assert "content-length" not in {key.lower() for key in captured_headers}
assert captured_headers["x-codex-window-id"] == "window-regression"
```

- [ ] **Step 2: Run the regression test and verify it fails**

Run `pytest tests/test_proxy_openai_responses_integration.py -k content_encoding -v`.

Expected: the test fails because the upstream request still carries `content-encoding: zstd`.

- [ ] **Step 3: Implement the minimal production change**

In the existing request-header setup in `cutctx/proxy/handlers/openai/responses.py`, add:

```python
headers.pop("host", None)
headers.pop("content-length", None)
headers.pop("content-encoding", None)
headers.pop("accept-encoding", None)
```

- [ ] **Step 4: Run the regression test and verify it passes**

Run `pytest tests/test_proxy_openai_responses_integration.py -k content_encoding -v`.

Expected: one passing test; the mocked upstream sees decoded JSON and no stale encoding or length headers.

- [ ] **Step 5: Run focused safety checks**

Run `pytest tests/test_proxy_openai_responses_integration.py tests/test_openai_codex_routing.py -q` and `ruff check cutctx/proxy/handlers/openai/responses.py tests/test_proxy_openai_responses_integration.py`.

Expected: zero test failures and zero Ruff errors.

- [ ] **Step 6: Commit the fix**

Stage only `cutctx/proxy/handlers/openai/responses.py` and `tests/test_proxy_openai_responses_integration.py`, then create a `fix: clear decoded Responses content encoding` commit.

## Plan Self-Review

- Spec coverage: Task 1 removes the stale header, preserves required Codex headers, avoids recompression, and supplies a zstd regression test.
- Placeholder scan: no incomplete requirements or deferred implementation items remain.
- Type consistency: the task uses the existing request-header dictionary and does not introduce a new public interface.
