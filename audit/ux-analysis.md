# UX Analysis — Cutctx Project

**Date:** 2026-07-10
**Auditor:** @designer
**Codebase:** `/Users/aryansingh/Documents/Claude/Projects/headroom`

---

## Overall UX Rating: 🟡 (Yellow — Functional, Not Delightful)

The project has strong technical capabilities but suffers from **command bloat, inconsistent entry points, and a learning cliff** that undermines the "60-second" onboarding promise. The good news: every issue has a clear path to resolution.

---

## Key Strengths

1. **`cutctx setup` is genuinely good** — 5-step wizard with `[1/5]...[5/5]` progress, agent detection, MCP registration, and health check. This is the right onboarding pattern.
2. **`cutctx wrap <agent>` is magic** — one command does everything. The proxy + context-tool + launch flow is a real differentiator.
3. **`config-check` command exists** — validates ports, env vars, provider keys, SSO, CORS, security settings before proxy starts. This is a model diagnostic command.
4. **Lazy CLI loading** — `LazyCLIGroup` in `cutctx/cli/main.py:123` loads command modules only when invoked. Fast startup even with 38+ commands.
5. **Dashboard has solid empty states** — Memory page shows "No memories recorded yet" + loading states. Savings page has skeleton cards during load.
6. **Exception hierarchy is clean** — `CutctxError` → `ConfigurationError`, `ValidationError`, `TransformError`, `CacheError` with structured `details` dicts.
7. **Proxy startup banner** — comprehensive status output (mode, extensions, telemetry, Langfuse, code-aware status). Information-rich.

---

## Critical Issues

### 🔴 Issue 1: First-Run Experience is a Wall of Commands

**File:** `cutctx/cli/main.py:141-159`

Running `cutctx` with no args outputs the help text, which lists **38+ commands** organized alphabetically, not by user phase:

```
Usage: cutctx [OPTIONS] COMMAND [ARGS]...

  Cutctx - Context optimization layer for LLM applications.
  Manage memories, run the optimization proxy, and analyze metrics.

Examples:
  cutctx setup            Unified setup with agent detection
  cutctx proxy            Start the optimization proxy
  cutctx memory list      List stored memories
  cutctx orgs list        List organizations
  cutctx audit list       List audit events
  cutctx rbac list        List role assignments
  cutctx config-check     Validate configuration
  cutctx sso-test         Test SSO configuration
```

**Problem:** A new user sees enterprise commands (orgs, rbac, sso-test) before they've even installed. The help text assumes you already know what "MCP" and "proxy" mean.

**Fix:** Group commands by phase in help output:
```
🚀 Quick Start
  cutctx setup              Set up everything (recommended first step)
  cutctx wrap <agent>       One-command agent integration
  cutctx proxy              Start the optimization proxy

📊 Monitor & Analyze
  cutctx perf               Show token savings
  cutctx savings            Detailed savings breakdown
  cutctx capabilities       List compression algorithms

🔧 Configuration
  cutctx config-check       Validate your setup
  cutctx memory             Manage cross-agent memory
  cutctx policies           Compression policies

🏢 Enterprise
  cutctx orgs               Organization management
  cutctx rbac               Role-based access control
  cutctx sso-test           Test SSO configuration
  cutctx billing            Billing & usage
```

---

### 🔴 Issue 2: `CutctxClient` Has No Factory Method

**File:** `cutctx/client.py:1-1048`

The client class is 1048 lines. Looking at the constructor pattern, users must manually:

1. Create a `CutctxConfig` object (707 lines of config model)
2. Instantiate a provider
3. Optionally set up cache optimizer, semantic cache layer, storage
4. Pass all of this to `CutctxClient(...)`

There is **no `CutctxClient.from_env()`** or `CutctxClient.easy()` factory. The README says `from cutctx import compress` but the actual SDK entry point requires deep configuration knowledge.

**Fix:** Add a `from_env()` class method:

```python
@classmethod
def from_env(cls, mode: CutctxMode = CutctxMode.OPTIMIZE, **overrides) -> CutctxClient:
    """Create a client from environment variables with sensible defaults.

    Reads CUTCTX_* env vars and creates a working client with zero config.
    """
    config = CutctxConfig(mode=mode, **overrides)
    return cls(config=config)
```

This is the single biggest DX improvement possible.

---

### 🔴 Issue 3: 707-Line Config Model is Intimidating

**File:** `cutctx/config.py:1-707`

The config model contains:
- `CacheAlignerConfig` (20+ fields)
- `SmartCrusherConfig`
- `CodeCompressorConfig`
- `ContentRouterConfig`
- `CutctxConfig` (the main config — 40+ fields)
- `RequestMetrics` (40+ fields for observability)
- Various enums and dataclasses

A new user looking at this file sees an ocean of options. Most fields have good defaults, but the file doesn't communicate "you only need to set 2-3 things."

**Fix:** Add a "Quick Start" section at the top of the file:

```python
"""Configuration models for Cutctx SDK.

QUICK START — Most users only need:
    from cutctx.config import CutctxConfig, CutctxMode
    config = CutctxConfig(mode=CutctxMode.OPTIMIZE)

    That's it. All 40+ settings have sensible defaults.
    Override only what you need: config.smart_crusher.enabled = False
"""
```

Also, consider a `CutctxConfig.easy()` or `CutctxConfig.for_agent(agent_name)` factory that pre-configures for common use cases.

---

## Detailed Analysis

### 1. CLI Experience

| Aspect | Status | Details |
|--------|--------|---------|
| First-run (no args) | 🔴 | Shows firehose of 38+ commands, no guidance |
| Help organization | 🔴 | Alphabetical, not by user phase |
| Progress indicators | 🟢 | `setup` shows `[1/5]...[5/5]` |
| Error messages | 🟡 | Some actionable, some just tracebacks |
| Welcome screen | 🔴 | No welcome/branding on first run |
| `--version` | 🟢 | Works (`-v` flag) |
| Lazy loading | 🟢 | Fast startup despite 38+ commands |

**File references:**
- `cutctx/cli/main.py:141-159` — main help output
- `cutctx/cli/main.py:123-138` — `LazyCLIGroup` (good)
- `cutctx/cli/setup.py:108-190` — `setup` command (excellent UX pattern)
- `cutctx/cli/wrap.py:1-1343` — wrap command (complex but functional)
- `cutctx/cli/__init__.py:12-38` — lazy submodule loading

**Quick Win:** Add a `cutctx welcome` or show a branded first-run message when `cutctx` is invoked with no args and no prior setup detected:

```
✂️  Cutctx — Context compression for AI agents

It looks like this is your first time! Let's get you set up:

  cutctx setup              # 60-second guided setup
  cutctx wrap claude        # Or jump straight to wrapping an agent

Learn more: https://cutctx.com/docs
```

---

### 2. SDK / DX Experience

| Aspect | Status | Details |
|--------|--------|---------|
| `from_env()` factory | 🔴 | Missing — manual config required |
| First compression steps | 🟡 | 3-4 steps minimum |
| API intuitiveness | 🟡 | OpenAI-compatible wrapper is good, but init is heavy |
| Error messages | 🟡 | `details` dict is helpful, but not always surfaced |
| Backward compat | 🟢 | Alias at `cutctx/client.py:1048` — `CutctxClient = CutctxClient` |

**File references:**
- `cutctx/client.py:38-45` — `ChatCompletions` wrapper (OpenAI-style)
- `cutctx/client.py:1047-1048` — backward-compat alias
- `cutctx/exceptions.py:1-196` — clean exception hierarchy

**Ideal first-compression flow (current):**
```python
from cutctx.config import CutctxConfig, CutctxMode
from cutctx.client import CutctxClient

config = CutctxConfig(mode=CutctxMode.OPTIMIZE)
client = CutctxClient(config=config)
response = client.chat.completions.create(
    model="claude-3-5-sonnet",
    messages=[...]
)
# 4 lines, but requires knowing CutctxConfig exists
```

**Ideal first-compression flow (with `from_env()`):**
```python
from cutctx import CutctxClient

client = CutctxClient.from_env()
response = client.chat.completions.create(...)
# 2 lines, matches OpenAI SDK familiarity
```

---

### 3. Configuration Experience

| Aspect | Status | Details |
|--------|--------|---------|
| Config model size | 🔴 | 707 lines, 40+ fields in main config |
| Sensible defaults | 🟢 | Yes — most fields have working defaults |
| `config doctor` | 🟢 | `cutctx config-check` exists and is thorough |
| Env var support | 🟢 | Good — `CUTCTX_*` prefix convention |
| Config file support | 🟡 | `.env` supported, but unclear if YAML/TOML config exists |
| Validation | 🟡 | `config-check` validates env vars but not config object fields |

**File references:**
- `cutctx/config.py:26-210` — `CacheAlignerConfig` (20+ fields)
- `cutctx/config.py:210-500` — `CutctxConfig` (main config, 40+ fields)
- `cutctx/config.py:500-707` — `RequestMetrics` and backward-compat aliases
- `cutctx/cli/config_check.py:1-131` — config-check command (good)

**The paradox:** The config model is *technically* well-designed (sensible defaults, good typing), but its *file length* is psychologically intimidating. A user opening `config.py` to understand what's possible sees 707 lines and assumes complexity that doesn't actually exist.

---

### 4. Onboarding Flow

| Aspect | Status | Details |
|--------|--------|---------|
| README first 20 lines | 🟢 | ASCII art + clear value prop + badges |
| "60 seconds" section | 🟢 | Shows install + 3 commands |
| Interactive setup | 🟢 | `cutctx setup` is a guided wizard |
| `cutctx init` | 🟡 | Durable installation (1158 lines) — more than first-run |
| Getting-started docs | 🟡 | `docs/content/docs/` exists but unclear structure |
| Error recovery | 🔴 | If `setup` fails mid-way, no clear recovery path |

**File references:**
- `README.md:1-50` — branding + value prop (good)
- `README.md:92-109` — "Get started (60 seconds)" section (good)
- `cutctx/cli/setup.py:108-190` — `setup` command output (excellent)
- `cutctx/cli/init.py:1-1158` — durable installation (complex)

**The gap:** `cutctx setup` is great for first-run, but `cutctx init` (1158 lines) is a different, more complex system for durable installation. Users may confuse these. The README doesn't clarify when to use `setup` vs `init`.

---

### 5. Dashboard UX

| Aspect | Status | Details |
|--------|--------|---------|
| First-load state | 🟢 | Skeleton cards, "Loading..." messages |
| Empty state | 🟢 | "No memories recorded yet" with clear messaging |
| Error state | 🟡 | Generic error messages, no retry button |
| Information hierarchy | 🟡 | Good panel structure, but dense |
| Enterprise gating | 🟢 | Clear "Enterprise feature" gate with feature list |

**File references:**
- `dashboard/src/pages/Memory.jsx:1-204` — memory page with empty state
- `dashboard/src/pages/Savings.jsx:1-580` — savings with skeleton cards
- `dashboard/src/pages/Overview.jsx` — overview (compressed, ~1500 lines)

**Dashboard strengths:**
- `Memory.jsx:143-148` — clean empty state: `{loading ? 'Loading memories…' : 'No memories recorded yet.'}`
- `Memory.jsx:104-120` — enterprise gate shows feature list before blocking
- `Savings.jsx:42-60` — `SkeletonCard` component for loading states

**Dashboard issues:**
- No retry button on error states
- No "Connect your proxy" call-to-action when dashboard can't reach the proxy
- Overview page is ~1500 lines — could benefit from component extraction

---

### 6. Error Handling UX

| Aspect | Status | Details |
|--------|--------|---------|
| Exception hierarchy | 🟢 | Clean: `CutctxError` → specific subclasses |
| Error messages | 🟡 | Some actionable, some just "X failed" |
| Traceback suppression | 🟡 | CLI catches some, but proxy can still show raw tracebacks |
| Telemetry | 🟡 | `is_telemetry_enabled()` exists but unclear if errors are reported |
| Recovery guidance | 🔴 | Most errors don't tell users what to do next |

**File references:**
- `cutctx/exceptions.py:24-196` — exception classes with `details` dicts
- `cutctx/exceptions.py:37-45` — base `CutctxError` with structured details
- `cutctx/cli/proxy.py:1325-1371` — startup banner (information-rich)

**Example of a good error message** (from `exceptions.py`):
```python
ConfigurationError(
    "API key not found",
    details={"provider": "anthropic", "env_var": "ANTHROPIC_API_KEY"}
)
```

**Example of a bad error message** (hypothetical from proxy):
```
ERROR: Failed to start proxy
```
→ Doesn't say *why* or *what to do*.

**Quick Win:** Add a "What to do" section to common errors:
```
ERROR: Port 8787 is already in use

What happened: Another process is using port 8787
Why: The proxy needs this port to accept LLM requests
What to do:
  1. Find the process: lsof -i :8787
  2. Kill it, or use a different port: cutctx proxy --port 8788
```

---

## Quick Wins (Prioritized)

| # | Fix | Effort | Impact | Files |
|---|-----|--------|--------|-------|
| 1 | Add `CutctxClient.from_env()` factory | Low | 🔴 High | `cutctx/client.py` |
| 2 | Add "Quick Start" comment at top of `config.py` | Low | 🟡 Medium | `cutctx/config.py` |
| 3 | Group CLI help by user phase | Medium | 🔴 High | `cutctx/cli/main.py` |
| 4 | Add first-run welcome message | Low | 🟡 Medium | `cutctx/cli/main.py` |
| 5 | Add "What to do" to common errors | Medium | 🔴 High | `cutctx/cli/proxy.py`, `cutctx/exceptions.py` |
| 6 | Add retry button to dashboard error states | Low | 🟡 Medium | `dashboard/src/pages/*.jsx` |
| 7 | Clarify `setup` vs `init` in README | Low | 🟡 Medium | `README.md` |
| 8 | Add `CutctxConfig.for_agent(agent_name)` factory | Medium | 🟡 Medium | `cutctx/config.py` |

---

## Verdict

The project has **solid foundations** — the `setup` wizard, `wrap` command, lazy CLI loading, and exception hierarchy are all well-designed. The issues are primarily about **discoverability and first impressions**: too many commands visible at once, no `from_env()` factory, and error messages that explain *what* but not *what to do*.

With the 8 quick wins above, the UX would move from 🟡 to 🟢. The hardest fix (grouping CLI help) is also the highest-impact — it's the first thing a new user sees.
