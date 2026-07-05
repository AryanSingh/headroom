# Shared Proxy Instability — 2026-07-03 to 2026-07-04

## Summary

Across roughly 24 hours, the shared production proxy (`com.cutctx.proxy`,
port 8787 — the one every wrapped harness on this machine depends on,
including the Codex desktop app) went unstable repeatedly, each time
surfacing to the user as vague, generic symptoms ("codex tripped",
"Bad Request", "stream disconnected before completion"). It took four
separate root causes, found one at a time as each fix exposed the next
issue underneath it, plus one purely operational problem that had nothing
to do with code at all.

The recurring difficulty: **every distinct root cause produced the exact
same user-visible symptom.** Diagnosing this required abandoning
`tail -N` on the error log (which mixes hours of history with no
per-entry timestamps and repeatedly looked like "the same crash again"
when it was stale content) in favor of a strict methodology: mark the
current log line count, generate real traffic through the suspected code
path, then check whether *anything new* was appended.

## Root causes found, in the order they were uncovered

### 1. `litellm` circular-import bug crashing the whole proxy on live traffic

`cutctx/proxy/savings_tracker.py`'s `_get_litellm_module()` only caught
`ImportError` around `import litellm`. The installed `litellm` package has
its own internal circular-import bug that raises `AttributeError`
("partially initialized module 'litellm' has no attribute
'litellm_core_utils'") instead. That exception sailed past the narrow
`except ImportError`, propagated up through
`record_request → emit_request_outcome → _record_request_outcome →
_finalize_stream_response`, and crashed the entire proxy process — on
essentially any request that needed a USD cost estimate, i.e. very often.

**Fix:** broadened the catch to `except Exception`. Losing one request's
cost estimate is an acceptable degradation; losing the whole proxy is not.
Backed with `tests/test_savings_tracker_litellm_resilience.py`, which
explicitly asserts an `AttributeError` during the import is swallowed —
this was written *because* the fix got silently reverted once already by
a concurrent edit to the same file mid-incident (see "Contributing
factor" below).

### 2. uvicorn's default WebSocket keepalive (20s) too short for real agent turns

Codex's `/v1/responses` WebSocket session stays open across an entire
agent turn, including local tool calls that can run for minutes (a shell
command, a test suite). uvicorn's `ws_ping_interval`/`ws_ping_timeout`
default to 20 seconds each and were never overridden, so any turn with a
tool call slower than ~20s would miss the pong window and get closed
**server-side**, mid-turn. This surfaced as "stream disconnected before
completion," and Codex's own reconnect attempts then failed with
"Bad Request" because a fresh WebSocket can't resume the prior turn's
pending tool-call state.

**Fix:** set `ws_ping_interval=600` / `ws_ping_timeout=600` in the
`uvicorn.run()` call in `cutctx/proxy/server.py`. Verified with a real
Codex turn spanning a 30s `sleep` — survived cleanly where it previously
would have disconnected.

### 3. Restarting the shared proxy drops every other connected client

Once (1) and (2) were fixed, the *exact same symptom* kept recurring with
zero new tracebacks in the log — because it wasn't a crash. The proxy's
own startup banner appeared 15 times in a tight burst with no errors
between them: something was deliberately stopping/starting the shared
proxy repeatedly (most likely a concurrent session iterating on its own
fix-test-reload loop directly against port 8787 instead of using the
`cutctx-dev` port-8788 alternative that exists for exactly this purpose).
Every restart kills every other in-flight connection, including whichever
Codex session happens to be live at that moment.

**Partial fix:** added `timeout_graceful_shutdown=45` to `uvicorn.run()`,
which gives in-flight requests/streams real time to finish before being
force-closed on SIGTERM. **This does not fully solve the problem** — it
only protects connections that are already open at shutdown time; it does
nothing about the gap between the old process releasing the port and the
new one re-binding it, during which any *new* connection attempt gets a
flat "Connection refused." Verified directly: manually restarting the
proxy mid-turn reproduced the identical "Reconnecting 2/5...5/5" sequence
the user had been seeing, and it self-recovered only because Codex's
5-retry budget happened to outlast this particular restart. A true fix
requires zero-downtime restart (socket handoff between old/new processes,
or a reverse proxy doing blue-green switching) — not implemented; flagged
as follow-up.

### 4. A second, unmanaged proxy process squatting on the shared port

The most severe issue, found last. Someone started `cutctx proxy`
directly from the dev checkout's own `.venv/bin/cutctx` — outside
`launchctl`, with no `--port` override, no `CUTCTX_ADMIN_API_KEY` set
(the proxy auto-generates and logs a random key when that env var is
absent), and no guard-script supervision. It grabbed port 8787, blocking
the legitimate LaunchAgent-managed instance from binding at all (visible
in the log as `[Errno 48] address already in use`). All traffic —
including the user's actual Codex sessions — was silently going through
this rogue, unsupervised, wrong-auth process instead of the real one.

**Fix:** killed the rogue process (PID identified via `ps -p <pid> -o
command` after `lsof -i :8787` showed an unexpected python3 owner); the
LaunchAgent-managed process bound the now-free port immediately and the
correct admin key started working again.

## Contributing factor: concurrent, uncoordinated edits to the same files

Multiple sessions were actively editing `cutctx/proxy/server.py` and
`cutctx/proxy/savings_tracker.py` throughout this window (branch
verification work, a dashboard packaging fix, this incident's own fixes).
This caused real regressions independent of any of the four root causes
above:

- The fix from root cause (1) was silently reverted back to
  `except ImportError` by a concurrent edit before the proxy had even
  been confirmed stable, and had to be reapplied.
- The fix from root cause (3) (`timeout_graceful_shutdown`) disappeared
  entirely from a later version of `server.py` after the file was
  restructured by a concurrent large edit (line count dropped from
  ~6250 to ~4040, then back up past 6200) — never reapplied, since by
  that point it was understood to only be a partial mitigation anyway.
- `cutctx/dashboard/__init__.py` was independently fixed by a different
  session for the same root cause already fixed here in a prior
  incident (see `artifacts/codex-session-recovery/`), converging on a
  similar but not identical solution.

None of this was caused by the file changes being *wrong* — each
individual edit was reasonable in isolation. The problem is that a single
shared checkout, a single shared installed venv (`~/.cutctx-proxy-venv`),
and a single shared running process on port 8787 were all being treated
as personal scratch space by multiple concurrent agents at once, with no
coordination and no merge step between them.

## Diagnostic methodology that actually worked

- **Never trust `tail -N` on the error log for "is this happening now."**
  It has no per-line timestamps and accumulates the entire day's crashes
  in one stream. Mark the line count first (`wc -l`), generate real
  traffic through the suspected path, then diff.
- **Reproduce with the real client, not just curl**, once code-level
  hypotheses run out — `codex exec --skip-git-repo-check "..."` with a
  deliberately slow shell command (`sleep 30`, `sleep 45`) was what
  actually surfaced root causes (2) and (3); synthetic curl payloads to
  `/v1/responses` never reproduced either.
- **Compare the file on disk against the file actually loaded in the
  running process**, not just "did I save the edit" — hot-patching
  `~/.cutctx-proxy-venv/lib/python3.11/site-packages/cutctx/...` directly
  (rather than a full `cutctx-promote` reinstall, given how fragile the
  proxy already was) repeatedly diverged from the dev repo source due to
  the concurrent-editing problem above, and each diagnostic pass had to
  re-check both copies.
- **`lsof -i :<port>` plus `ps -p <pid> -o command` to identify the
  actual owning process** was what caught root cause (4) — `ps aux |
  grep cutctx` alone missed it, because the rogue process's command line
  path didn't happen to match that particular grep pattern the first
  time it was tried.

## Recommendations / follow-up

1. **Coordinate before restarting the shared proxy.** If iterating on
   proxy code, use `cutctx-dev` (port 8788) — it exists for exactly this
   purpose and was seemingly not used in the sessions that triggered
   root causes (3) and (4).
2. **True zero-downtime restart is still unsolved.** Graceful shutdown
   helps in-flight requests but not the reconnection gap. Worth
   revisiting if restarts of the shared proxy remain frequent.
3. **Consider making the dev `.venv`'s `cutctx proxy` refuse to bind port
   8787 without an explicit override**, so a bare `cutctx proxy` (missing
   `--port`) can't silently steal the production port again.
4. **`litellm`'s underlying circular-import bug is still present** in the
   installed package — the proxy no longer crashes because of it, but a
   `pip install --upgrade litellm` in the stable venv would resolve the
   root cause rather than just containing it.
5. **When several sessions are editing the same file concurrently, expect
   silent reverts of unrelated-looking fixes.** Regression tests (like
   `tests/test_savings_tracker_litellm_resilience.py`) are the only thing
   that reliably survived this — comments alone did not.
