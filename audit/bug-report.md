# Bug Report: Compression Failure Handling

## Bug 1: Oversized frames cause hard disconnects for Codex clients
**Severity Assessment:** High
**Reproduction Steps:**
1. Connect Codex client through Cutctx proxy.
2. Send a request that exceeds `WS_COMPRESSION_OVERSIZE_BYTES_ENV` (e.g., >256KB) where compression fails or is skipped due to size.
3. The proxy returns a 413 Payload Too Large error (or 1009 over WS).
4. Codex client treats this as a hard connection failure and resets the session history.

**Expected vs Actual Behavior:**
- *Expected:* The proxy should either fail-open (forward the payload to the upstream to let it handle it) or return a graceful error that the client understands without dropping the session.
- *Actual:* The proxy refuses the connection with 413, causing Codex to drop all session history.

**Suggested Fix:**
- Remove the `asyncio.TimeoutError` limitation for Codex client overrides in `decide_compression_failure_action`. Fail-open for *all* compression failures when the client is Codex. *(Note: This was partially fixed in the previous turn, but tests were not updated to reflect it).*

## Bug 2: Missing test coverage for Codex oversized frames
**Severity Assessment:** Medium
**Reproduction Steps:**
1. Run `pytest tests/test_proxy/test_compression_failure_action.py`
2. Observe that there are no tests ensuring Codex clients fail-open on oversized frames (only timeouts are explicitly tested).

**Expected vs Actual Behavior:**
- *Expected:* There should be testcases `test_codex_client_oversize_fails_open` and `test_codex_client_any_error_fails_open`.
- *Actual:* Missing tests.

**Suggested Fix:**
- Add tests to `test_compression_failure_action.py` to cover the new logic for Codex clients.

## Bug 3: Hardcoding "codex" might miss other fragile clients
**Severity Assessment:** Medium
**Reproduction Steps:**
1. Connect other clients that lack graceful 413/1009 handling (e.g., `aider`, `windsurf`) and trigger an oversized frame refusal.
2. Observe if they also drop session history.

**Expected vs Actual Behavior:**
- *Expected:* All clients should gracefully handle context limits or the proxy should fail-open for them.
- *Actual:* Only "codex" is specifically whitelisted to fail-open. 

**Suggested Fix:**
- Investigate other clients' handling of 413s. For now, ensure the `codex` fix is thoroughly tested and consider making the fail-open configurable per-client.
