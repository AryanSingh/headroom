# Test Unskip Handoff - 2026-07-01

## Goal

Continue the "install optional packages, unskip more tests, and fix newly exposed regressions" effort without disturbing unrelated in-flight work in this repo.

## Important Environment Note

Do **not** source `.env.local` wholesale for test runs.

That file mutates many Cutctx runtime settings and caused unrelated memory/backend regressions during full-suite runs.

Use only the OpenAI key from `.env.local`:

```bash
OPENAI_API_KEY="$(
  /opt/homebrew/opt/python@3.11/bin/python3.11 - <<'PY'
from pathlib import Path
vals = {}
for raw in Path('.env.local').read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    vals[k.strip()] = v.strip()
print(vals.get('CUTCTX_UPSTREAM_OPENAI_API_KEY', ''))
PY
)" /opt/homebrew/opt/python@3.11/bin/python3.11 -m pytest -q --maxfail=1
```

Use Python 3.11 tooling consistently. Do **not** use bare `pytest` or `python3 -m pip`, because the machine also has a different Python 3.14 environment.

## Optional Packages Installed

Installed into Python 3.11:

- `usearch`
- `strands-agents`
- `agno`
- `langchain-core`
- `langchain-openai`
- `langchain-ollama`

## Progress Completed

### Earlier blockers fixed

- Fixed malformed favicon 404 line in [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py).
- Added proxy import regression coverage in [tests/test_proxy_server_import.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_proxy_server_import.py).
- Isolated RBAC DB state in [tests/test_management_api_entitlements.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_management_api_entitlements.py) using per-test `CUTCTX_RBAC_DB_PATH`.

### Newly unskipped USEARCH regressions fixed

- [cutctx/memory/factory.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/memory/factory.py)
  - `UsearchMemoryBackend` is now initialized before returning from the factory.
- [tests/test_usearch_backend.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_usearch_backend.py)
  - Added regression coverage proving `create_memory_system()` returns a USEARCH backend that can index immediately.
- [cutctx/memory/core.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/memory/core.py)
  - `HierarchicalMemory.close()` now tolerates both sync and async `close()` implementations.
- [tests/test_memory/test_close_lifecycle.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_memory/test_close_lifecycle.py)
  - Added regression coverage for sync-only vector-index cleanup.
- [tests/test_memory/test_factory.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_memory/test_factory.py)
  - Updated AUTO backend expectations to allow USEARCH when installed.

### Playwright flake reduced

- [tests/test_dashboard_cache_ttl_playwright.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_dashboard_cache_ttl_playwright.py)
  - Switched `page.goto(..., wait_until="load")` to `wait_until="commit"` to avoid suite-time navigation timeout flake.

### OpenAI responses stats regression fixed

- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)
  - Restored `requests.by_provider` in one `/stats` payload shape used by OpenAI responses integration tests.

## Verified Passing Slices

These were rerun successfully after the fixes above:

- `tests/test_management_api_entitlements.py`
- `tests/test_dsr_cascade_e2e.py`
- `tests/test_usearch_backend.py`
- `tests/test_memory/test_core_operations.py`
- `tests/test_memory/test_factory.py`
- `tests/test_dashboard_cache_ttl_playwright.py`
- `tests/test_proxy_openai_responses_integration.py`

Also verified with the OpenAI key mapped:

- targeted previously skipped batch: `226 passed, 45 skipped`

Remaining skips in that batch were legitimate external prerequisites:

- `GOOGLE_API_KEY` missing
- AWS / Bedrock credentials missing
- Ollama daemon not running

## Current Full-Suite Status

The full suite with only `OPENAI_API_KEY` injected was repeatedly moved forward with `--maxfail=1`.

Most recently, the run progressed past:

- dashboard Playwright
- management API entitlements
- memory core / factory / USEARCH slices
- proxy OpenAI responses integration

The last explicitly fixed full-suite failure was the missing `requests.by_provider` key in `/stats`.

After that fix, the single targeted test passed:

- `tests/test_proxy_openai_responses_integration.py::TestOpenAIResponsesStats::test_stats_track_openai_provider`

## Remaining Work For Next Agent

1. Run the full suite again from the current tree with only `OPENAI_API_KEY` injected.

   Command:

   ```bash
   OPENAI_API_KEY="$(
     /opt/homebrew/opt/python@3.11/bin/python3.11 - <<'PY'
   from pathlib import Path
   vals = {}
   for raw in Path('.env.local').read_text().splitlines():
       line = raw.strip()
       if not line or line.startswith('#') or '=' not in line:
           continue
       k, v = line.split('=', 1)
       vals[k.strip()] = v.strip()
   print(vals.get('CUTCTX_UPSTREAM_OPENAI_API_KEY', ''))
   PY
   )" /opt/homebrew/opt/python@3.11/bin/python3.11 -m pytest -q --maxfail=1
   ```

2. Fix the next real failure, if any, with the same discipline:

- one file
- one behavior
- one regression test
- immediate parse/test rerun

3. After the suite is stable under OpenAI-enabled conditions, decide whether to unskip more external-provider tests by adding:

- `GOOGLE_API_KEY`
- AWS / Bedrock credentials
- local Ollama runtime

Do that only if you intend to own the resulting live-test fallout.

## Constraints For Next Agent

- Do not revert unrelated modified files already present in the worktree.
- Keep using `apply_patch` for edits.
- Prefer Python 3.11 explicitly:
  - `/opt/homebrew/opt/python@3.11/bin/python3.11 -m pytest`
  - `/opt/homebrew/opt/python@3.11/bin/python3.11 -m pip`
- Do not source `.env.local` globally.
- Assume more regressions may appear only because optional dependencies are now present; treat those as genuine behavior bugs, not as test noise, unless proven flaky in isolation.
