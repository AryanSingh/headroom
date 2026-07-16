# Remote Compaction Passthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve Codex remote-compaction Responses requests across the local subscription proxy.

**Architecture:** Add a narrow request-shape classifier in the OpenAI Responses handler. When it identifies a large remote-compaction subscription request, the HTTP path bypasses only transformations that corrupt provider-owned continuation state while retaining the existing upstream route and headers.

**Tech Stack:** Python, FastAPI, pytest.

## Global Constraints

- Preserve ordinary subscription Responses safeguards.
- Do not log request content or credentials.
- Prove the bypass with a failing regression test before implementation.

---

### Task 1: Protect remote compact requests

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Modify: `tests/test_openai_codex_routing.py`

**Interfaces:**
- Produces: a private predicate that accepts a parsed Responses request body and identifies the remote-compaction shape.

- [ ] **Step 1: Write the failing test**

Create a representative 2 MB subscription body containing the remote-compaction-only field set and assert the dummy upstream receives the exact original body.

- [ ] **Step 2: Run the focused test**

Run: `pytest -q tests/test_openai_codex_routing.py::test_remote_compaction_subscription_body_is_forwarded_unchanged`

Expected: FAIL because the current sanitizer removes provider-owned fields.

- [ ] **Step 3: Add the minimal classifier and bypass**

Skip model routing, sanitization, compression, and context truncation only when the classifier returns true; preserve the ChatGPT subscription upstream route.

- [ ] **Step 4: Run focused verification**

Run: `pytest -q tests/test_openai_codex_routing.py tests/test_openai_responses_context_compaction.py`

Expected: PASS.

- [ ] **Step 5: Promote and restart**

Install the tested source into the stable proxy environment, restart the managed service, and poll `/readyz` until healthy.
