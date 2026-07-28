## Imported Claude Cowork project instructions


<!-- cutctx:rtk-instructions -->
# RTK (Rust Token Killer) - Token-Optimized Commands

When running shell commands, **always prefix with `rtk`**. This reduces context
usage by 60-90% with zero behavior change. If rtk has no filter for a command,
it passes through unchanged — so it is always safe to use.

## Key Commands
```bash
# Git (59-80% savings)
rtk git status          rtk git diff            rtk git log

# Files & Search (60-75% savings)
rtk ls <path>           rtk read <file>         rtk grep <pattern>
rtk find <pattern>      rtk diff <file>

# Test (90-99% savings) — shows failures only
rtk pytest tests/       rtk cargo test          rtk test <cmd>

# Build & Lint (80-90% savings) — shows errors only
rtk tsc                 rtk lint                rtk cargo build
rtk prettier --check    rtk mypy                rtk ruff check

# Analysis (70-90% savings)
rtk err <cmd>           rtk log <file>          rtk json <file>
rtk summary <cmd>       rtk deps                rtk env

# GitHub (26-87% savings)
rtk gh pr view <n>      rtk gh run list         rtk gh issue list

# Infrastructure (85% savings)
rtk docker ps           rtk kubectl get         rtk docker logs <c>

# Package managers (70-90% savings)
rtk pip list            rtk pnpm install        rtk npm run <script>
```

## Rules
- In command chains, prefix each segment: `rtk git add . && rtk git commit -m "msg"`
- For debugging, use raw command without rtk prefix
- `rtk proxy <cmd>` runs command without filtering but tracks usage
<!-- /cutctx:rtk-instructions -->

## Project Notes

- Model-routing preset docs live in `docs/content/docs/model-routing-presets.mdx`.
- Canonical preset: `codex-gpt54mini-high`.
- Compatibility aliases: `codex-opencode-slim`, `oh-my-opencode-slim`.
- Low-complexity GPT tasks route to `gpt-5.4-mini` with `reasoning.effort = high`; heavier tasks stay on the requested model.
- See `cutctx/proxy/model_router.py` and the OpenAI handler tests for implementation details.

## Current state — read before compression or release work

`docs/handoff-2026-07-28.md` is the entry point. It records what changed, the
measured numbers with their reproduction commands, the open decisions, and the
traps that each produced a confidently wrong answer.

The one heuristic worth carrying: **when an engine reports 0% savings, assume
it is unreachable until proven otherwise.** Seven engines were found switched
on, throwing nothing, and doing nothing — a gate testing `"lossless"` against a
value that is always `"lossless:table(...)"`, a dict read as an object, an
enable flag with no CLI path. An engine that is enabled, silent, and saves
nothing looks exactly like one that legitimately did not apply.

Two traps that waste the most time:
- `cutctx_ai.pth` can point at a worktree, so `cutctx` CLI calls run different
  code from `python -c` in the repo (cwd wins on `sys.path`). Check it first
  when a fix appears to do nothing.
- CI pins `ruff==0.9.4`; a fresh install gets 0.14.x and they disagree on both
  rules and formatting. Verify with `uvx ruff@0.9.4 check .`.

## Repository Map

A full codemap is available at `codemap.md` in the project root.

Before working on any task, read `codemap.md` to understand:
- Project architecture and entry points
- Directory responsibilities and design patterns
- Data flow and integration points between modules

For deep work on a specific folder, also read that folder's `codemap.md`.
