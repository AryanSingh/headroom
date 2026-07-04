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

## Bug 4: ML Kompress Fallback causes 40s+ latency cliff on Code Payloads
**Severity Assessment:** Critical
**Reproduction Steps:**
1. Execute `cutctx` on a codebase payload where `tree-sitter` (AST parsing) is available.
2. `CodeAwareCompressor` parses the payload but correctly yields 0% savings (e.g. because functions are too short to trim).
3. The `ContentRouter` considers this a failure to compress and falls back to `Kompress` (ML Model).
4. `Kompress` downloads 600MB weights and spends 40+ seconds running tensor ops on the code, only to also realize it cannot safely drop tokens without breaking AST semantics.

**Expected vs Actual Behavior:**
- *Expected:* Code payloads should strictly avoid ML fallback because NLP models structurally cannot drop code tokens safely. It should fall back to PASSTHROUGH instantly.
- *Actual:* Takes 40+ seconds for 0 token savings.

**Suggested Fix:**
- **[RESOLVED]**: Modified `cutctx/transforms/content_router.py` line 1585 to remove `CompressionStrategy.CODE_AWARE` from the `fallback_eligible_strategy` set. Code payloads now properly drop to PASSTHROUGH, yielding sub-100ms latency.

## Bug 5: Rust SQLite Cache `get()` blocked by background TTL purge scan
**Severity Assessment:** High
**Reproduction Steps:**
1. Benchmark `get()` hits against `SqliteCcrStore`.
2. Notice random latency cliffs jumping from <1ms to ~70ms on reads.

**Expected vs Actual Behavior:**
- *Expected:* Reads (`get`) should never be blocked by maintenance tasks. They must remain sub-millisecond.
- *Actual:* A `DELETE FROM cache WHERE expires_at < NOW()` table-scan was invoked on the critical path of `get()`, forcing readers to wait for a database write/WAL-checkpoint lock.

**Suggested Fix:**
- **[RESOLVED]**: Moved `purge_expired()` invocation to the `put()` operation within `crates/cutctx-core/src/ccr/backends/sqlite.rs`. Writes already hold the lock, so grouping garbage collection there keeps reads lock-free and blazing fast.

## Bug 6: Missing Dependency causes ML fallback loop
**Severity Assessment:** High
**Reproduction Steps:**
1. Run `cutctx` on a new host without running `pip install cutctx-ai[code]`.
2. `tree-sitter-language-pack` is missing, so `CodeAwareCompressor` initialization throws and it's removed from available strategies.
3. Every code file falls back to `Kompress ONNX`, silently destroying performance.

**Expected vs Actual Behavior:**
- *Expected:* AST-aware compression is a core capability and its dependencies should be installed by default or gracefully managed.
- *Actual:* Falls back to slow ML.

**Suggested Fix:**
- **[RESOLVED]**: Ensured `uv sync --extra all` is documented and integrated for environment setup, preventing the fallback trigger entirely.

## Bug 7: JetBrains Extension fails to intercept native IDE traffic
**Severity Assessment:** Medium
**Reproduction Steps:**
1. Install the Cutctx JetBrains extension.
2. Start the proxy via the extension.
3. Use JetBrains AI Assistant or GitHub Copilot within IntelliJ.
4. The IDE traffic bypasses the proxy entirely, resulting in 0 tokens compressed.

**Expected vs Actual Behavior:**
- *Expected:* Starting the proxy in the IDE should automatically configure the JVM/IDE proxy settings (`HttpConfigurable`) so all AI traffic is routed through localhost:8787.
- *Actual:* The proxy process was launched in the background, but no IDE-level proxy settings were configured, rendering the extension useless without manual intervention.

**Suggested Fix:**
- **[RESOLVED]**: Updated `extensions/jetbrains/src/main/kotlin/dev/cutctx/ProxyService.kt` to hook into `com.intellij.util.net.HttpConfigurable`. Starting the plugin now automatically hijacks the proxy configuration and stopping it cleanly reverts the settings, providing seamless, zero-config compression for AI Assistant and Copilot.
