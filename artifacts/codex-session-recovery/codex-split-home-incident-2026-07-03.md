# Codex "Lost Session History / Settings" Incident — 2026-07-03

## Summary

Codex desktop app and CLI appeared to intermittently "lose" chat session
history and show a broken Settings/Usage panel. No chat data was ever
actually lost. The root cause was a duplicate Codex home directory
(`~/.codex-cutctx`) created during earlier CutCtx proxy-integration work,
left active via a stray, unpersisted `launchctl setenv CODEX_HOME` override.
This caused some processes to read/write a second copy of Codex's
Electron UI-state file, which silently diverged from the real one. The
data itself (SQLite databases, session rollouts) was always shared via
symlinks and never actually diverged — only a small UI-state file
(pins, drafts, prompt history) drifted, and it drifted **repeatedly**
because a long-running Codex process kept re-flushing its stale in-memory
copy over any fix applied while it was still open.

This is not the first occurrence — recovered history in this same repo
shows the same "session history lost" complaint as far back as
2026-06-25 (see `headroom-timeline.md` in this directory), meaning the
underlying split-home condition had been present, undiagnosed, for over
a week before this fix.

## Reported symptom

- "codex is broken, doesn't work with claude app or opencode or gemini"
- "codex again broke, i was trying to fix session history and settings and it broke"
- "restore all chat sessions to codex, settings are also not available fully"

## Root cause

Three independent things were tangled together, only one of which was a
real bug:

1. **Real OpenAI account cap (not a bug).** Codex requests were correctly
   routed through the CutCtx proxy to OpenAI and correctly relayed a real
   `"You've hit your usage limit... try again at 2:01 AM"` response. This
   reproduced identically with every CutCtx env var stripped and the proxy
   fully bypassed — confirmed independent of CutCtx. It later cleared on
   its own once the reset time passed.

2. **A stray, unpersisted global env override (the actual bug).**
   `launchctl setenv CODEX_HOME /Users/aryansingh/.codex-cutctx` was set at
   some earlier point (no backing LaunchAgent plist — a manual leftover
   from earlier proxy-integration debugging). This redirected Codex's
   config/state home for any process that inherited it, while
   `~/.codex/config.toml` *also* independently had the CutCtx provider
   injected directly (from an earlier `cutctx wrap codex` run). Two
   parallel, overlapping mechanisms were routing Codex through CutCtx at
   once.

3. **Partial mirroring inside the shadow home.** `~/.codex-cutctx`
   symlinked most of its contents back to `~/.codex` (`sessions/`,
   `archived_sessions/`, `session_index.jsonl`, all four SQLite databases)
   — so actual chat content was *never* at risk. But
   `.codex-global-state.json` (Electron's UI-state file — pinned threads,
   composer drafts, prompt history, unread markers, sidebar state) was a
   **real, independent file** in both homes, not a symlink. Whichever
   process last wrote to a given home's copy would silently diverge from
   the other.

4. **macOS env-cache staleness compounded it.** `launchctl unsetenv
   CODEX_HOME` only affects newly-spawned processes; shells and GUI apps
   already forked before the change kept resolving the old value for the
   rest of their process lifetime. This meant a first `unsetenv` fix
   looked incomplete when re-tested from an already-running shell.

5. **Electron's own persistence model kept reverting manual fixes.** The
   Codex desktop app loads `.codex-global-state.json` into memory at
   launch and periodically (and on quit) flushes its in-memory copy back
   to disk. Any direct edit made to that file while the app was still
   running got silently overwritten on the next autosave/quit — this is
   normal app behavior, not a CutCtx-caused bug, but it meant the first
   two attempts at restoring dropped state (3 pinned threads) were
   clobbered within minutes.

## What was investigated (in order)

1. Confirmed all three coding-harness complaints (Codex, Gemini, opencode)
   independently rather than assuming a shared cause:
   - **Codex**: real usage-limit lockout, proxy routing itself was correct.
   - **Gemini**: no auth configured on the machine at all — reproduced
     identically with zero CutCtx env vars present. Unrelated to CutCtx.
   - **opencode**: routes through a third-party plugin
     (`oh-my-opencode-slim`) with its own hardcoded gateway providers
     (`opencode-go`, `kimi-for-coding`) that never consult
     `OPENAI_BASE_URL`/`ANTHROPIC_BASE_URL`. CutCtx's env-var wrap is a
     silent no-op there by design of that plugin, not a defect.
   - **Claude Desktop**: MCP server (`cutctx mcp serve`) confirmed
     registered and live-tested working (`cutctx_stats`, `cutctx_compress`
     both responded correctly). The consumer chat app's own model traffic
     can't be intercepted by any local proxy (session-cookie auth, not an
     SDK base-URL path) — a platform constraint, not a bug.

2. Found and removed the stray `CODEX_HOME` launchctl override.

3. Diffed `~/.codex/.codex-global-state.json` against
   `~/.codex-cutctx/.codex-global-state.json` field-by-field to confirm
   the *only* real divergence was UI-state (pins, drafts, prompt history,
   unread markers) — never thread/session content.

4. Verified via `codex doctor` and direct SQLite `PRAGMA integrity_check`
   that all 4 databases (`state_5`, `logs_2`, `goals_1`, `memories_1`)
   were healthy, and rollout-file vs. state-DB thread inventory agreed
   with zero mismatches — 305 active + 184 archived threads throughout.

## What worked

- **Removing the stray `CODEX_HOME` launchctl override** — confirmed via
  `launchctl print gui/<uid>` showing only the two intended vars
  (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`) afterward.
- **Converting `~/.codex-cutctx` from a real directory into a symlink to
  `~/.codex`** — this is the actual permanent fix. Any process that still
  resolves the old `CODEX_HOME` value (due to env-cache staleness) now
  transparently lands on the exact same files as the real home, making
  future divergence structurally impossible regardless of how long stale
  env values linger in old shells or already-running processes.
- **Doing the state-file merge (pins, drafts, prompt history, unread
  markers) with a strict union strategy** — real and shadow copies had
  disjoint key sets in every dict field, so no data was overwritten;
  everything from both sides was kept.
- **Waiting for full app quit before the final write** — confirmed via
  `ps aux` that no `Codex.app` or `codex app-server` process was running,
  wrote the file, then immediately re-read it back to confirm no
  in-flight process had already re-clobbered it.
- **`codex doctor`** as the source of truth for verification instead of
  guessing — it directly reports SQLite integrity and thread-inventory
  agreement, which is stronger evidence than inspecting files by hand.

## What didn't work (first two attempts)

- Editing `.codex-global-state.json` **while the desktop app was still
  running**. Twice, the merged pin data (`pinned-thread-ids`) was silently
  reverted within minutes because the live app process held an
  in-memory snapshot from before the edit and flushed it back over the
  fix on its own autosave cycle.
- Trusting `launchctl unsetenv` as immediately authoritative from within
  the same shell session that had the stale value — `env`/`ps` checks
  from that shell kept reporting the old `CODEX_HOME` even after the
  launchd registry itself (`launchctl getenv`) was confirmed clean,
  because that shell had inherited the value at its own startup and
  never re-read the launchd environment afterward.

## Final verified state

- `~/.codex-cutctx` → symlink → `~/.codex` (no longer a real directory;
  old contents preserved at `~/.codex-cutctx.orphaned-<timestamp>` for
  reference, safe to delete).
- `codex doctor`: 17 ok · 1 idle · 3 notes · **0 warn · 0 fail**.
- All 4 SQLite databases: integrity `ok`.
- 305 active + 184 archived rollout threads, 0 scan errors, 0 stale rows,
  0 archive mismatches.
- `pinned-thread-ids` restored (3 threads), written and verified while no
  Codex process was running to overwrite it.
- Composer draft and full prompt history across all 15 threads with
  history preserved via union merge.
- Duplicate/redundant CutCtx init hooks in `~/.gemini/settings.json`
  deduped to a single hook pointing at the production binary
  (`/opt/homebrew/bin/cutctx`) instead of firing twice per event against
  two different binary paths.

## Not fixed (out of CutCtx's control)

- **Gemini CLI has no auth configured** on this machine — needs a manual
  `gemini` login / API key, unrelated to CutCtx.
- **opencode's real provider setup bypasses CutCtx entirely** via the
  `oh-my-opencode-slim` plugin's own gateway providers. To get
  compression there, one of opencode's providers would need to be
  reconfigured to point at `http://127.0.0.1:8787` directly — a change on
  the opencode config side, not something CutCtx can inject.
- **A stale Cloudflare-hosted MCP server OAuth token** in Codex's own MCP
  config produces a harmless but noisy `AuthRequiredError` on every
  `codex exec` invocation. Unrelated to CutCtx; not addressed here.

## Follow-up / recommendations

- Delete `~/.codex-cutctx.orphaned-<timestamp>` once confirmed nothing is
  needed from it (it's a straight copy of pre-fix state, kept only as a
  safety net).
- Avoid ever creating a second `CODEX_HOME` for CutCtx integration again —
  the supported mechanism is direct `config.toml` provider injection
  (what `cutctx wrap codex` already does), not a parallel home directory.
- If Codex's Settings/Usage panel appears unavailable again, check for a
  real account-level cap first (`codex exec` will surface the actual
  OpenAI error) before assuming a local config problem.
