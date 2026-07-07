# Cutctx UX Analysis

*Audit date: July 2026*
*Scope: CLI, SDK, configuration, error handling, onboarding, documentation*

---

## Executive Summary

Cutctx is a context compression layer for AI agents with a broad feature surface: proxy mode, SDK, MCP integration, memory, CCR (reversible compression), profiles, and enterprise features. The UX is competent and well-structured in places, but suffers from **configuration overload**, **fragmented onboarding**, and **error messages that explain what went wrong without guiding users toward what to do next**. The CLI is powerful; the first-time experience is not.

---

## 1. CLI Intuitiveness

**Strengths.** The `cutctx setup` command is well-designed: it detects installed agents, registers MCP, starts the proxy, and verifies health in a single 5-step flow. The `cutctx wrap` command is similarly strong — `cutctx wrap claude` is a clean one-liner that sets up everything. Lazy command loading means startup is fast even with 40+ subcommands.

**Friction points.** The command surface is large (40+ subcommands across `proxy`, `memory`, `perf`, `report`, `bench`, `audit`, `rbac`, `orgs`, `sso-test`, `config-check`, `install`, `setup`, `wrap`, `learn`, `tools`, `policies`, `capture`, `intercept`, `mcp`, `billing`, `license`, `integrations`, `stack-graph`, `agent-savings`, `evals`, `savings`, `profile`). New users face a wall of options without a clear path from "just get it running" to "explore advanced features." There is no `cutctx` (no subcommand) that shows a welcome screen, current status, or suggested next steps. The `--help` output lists every command equally, burying the essentials.

**Recommendation.** Add a top-level `cutctx` (no subcommand) experience that shows status: whether a proxy is running, which agents are detected, current savings, and a "next steps" suggestion. Group commands in help output by phase: Core (`setup`, `proxy`, `wrap`), Observe (`perf`, `savings`, `report`), Advanced (`memory`, `learn`, `policies`), Enterprise (`orgs`, `rbac`, `sso-test`, `billing`).

---

## 2. Configuration Complexity

**Strengths.** `cutctx/config.py` uses well-typed dataclasses with sensible defaults. The `CacheAlignerConfig` docstring is thorough, documenting detection capabilities and gotchas inline. Environment variable overrides follow a clear precedence chain (`explicit arg > env var > canonical root > default`), documented in `paths.py`.

**Friction points.** The configuration surface is deep. `CutctxConfig` spans 700+ lines with nested models (`CacheAlignerConfig`, `Block`, `WasteSignals`, `RequestMetrics`, `SimulationResult`). A new user looking at this has no idea what to change versus what to leave alone. The `CacheAlignerConfig` alone has `use_dynamic_detector`, `detection_tiers`, `extra_dynamic_labels`, `entropy_threshold`, `date_patterns`, `normalize_whitespace`, `collapse_blank_lines`, and `dynamic_tail_separator`. Most users will never touch these, but their presence creates cognitive overhead. The `paths.py` module exposes 25+ path helpers in `__all__`, each with its own env var — impressive for power users, overwhelming for everyone else.

**Recommendation.** Surface a curated `cutctx config show` or `cutctx config --explain` that shows only the settings most users should care about, with explanations. Hide advanced settings behind `--advanced` flag. Provide a `cutctx config doctor` that validates configuration and suggests improvements.

---

## 3. Error Message Quality

**Strengths.** The exception hierarchy is clean: `CutctxError` base with `ConfigurationError`, `AuthenticationError`, `AuthorizationError`, `EntitlementError`, `CacheError`, `ValidationError`, `TransformError`. Each has detailed docstrings with usage examples. The `details` dict pattern on exceptions is a good practice — it provides structured context for programmatic handling.

**Weakiction points.** Error messages in the CLI use `click.style(" FAILED", fg="red")` or `print_error(msg)` from `formatting.py`, which prints `[bold red]Error:[/bold red] msg`. The messages themselves are terse. When proxy startup fails, the user sees `"FAILED"` with no hint about why (port conflict? missing dependency? network issue?). The `setup.py` flow shows `"Start proxy manually: cutctx proxy"` but doesn't capture the error. The exception module's `__str__` method renders details as `(key=value, ...)` which is readable but doesn't suggest fixes.

**Recommendation.** Every error message should answer three questions: What happened? Why? What should the user do? The setup flow should capture and display the actual failure reason. Exception messages should include actionable hints (e.g., "Port 8787 in use. Try: cutctx proxy --port 8800").

---

## 4. SDK/API Ergonomics

**Strengths.** The `CutctxClient` follows the OpenAI SDK pattern closely (`client.chat.completions.create()`), making it immediately familiar to anyone who has used the OpenAI Python library. Cutctx-specific parameters (`cutctx_mode`, `cutctx_cache_prefix_tokens`, etc.) are cleanly prefixed with `cutctx_` and passed as kwargs, avoiding namespace pollution. The `ChatCompletions` wrapper is a thin layer that keeps the API surface stable.

**Friction points.** The SDK has a lot of imports required to get started (`from cutctx import CutctxClient`, then `CutctxConfig`, `CutctxMode`, etc.). There is no `cutctx.from_env()` or `CutctxClient.from_defaults()` that loads configuration from environment variables and standard paths. The `validate_setup()` method is a separate call that users must remember to invoke. The `CutctxConfig` dataclass has dozens of fields with no builder pattern or fluent API.

**Recommendation.** Add a `CutctxClient.from_env()` factory that loads from `CUTCTX_*` env vars and standard config paths. Provide a `CutctxConfig.simple()` or `CutctxConfig.for_tier(tier)` that gives reasonable defaults per use case (developer, team, enterprise).

---

## 5. Documentation Clarity

**Strengths.** The README is well-structured with a clear 60-second quickstart, proof section with benchmarks, agent compatibility matrix, and installation for both Python and npm. The PRODUCT_GUIDE.md is thorough — 20 sections covering architecture, pricing, competitive landscape, FAQ. The `llms.txt` and `llms-full.txt` files show awareness of AI-native consumption patterns.

**Friction points.** The quickstart in README requires 4 steps (install, configure API key, run proxy, configure agent) — reasonable but could be one command. The documentation is split across README.md, PRODUCT_GUIDE.md, docs/ directory (60+ files), and cutctx.com/docs — it's unclear which source is authoritative. There is no local `quickstart.md` in the docs/ directory. The QA-PLAYBOOK.md is 1400+ lines of internal process documentation that lives alongside user-facing docs. The LEAD_GEN_PLAYBOOK.md contains internal sales strategy mixed with product information.

**Recommendation.** Consolidate the quickstart into a single `cutctx setup` that does everything (it already exists — promote it harder). Move internal docs (QA, LEAD_GEN) to a separate `internal/` or `.internal/` directory. Add a clear README section that links "new user" docs vs. "contributor" vs. "internal."

---

## 6. Onboarding Friction

**Strengths.** The `cutctx setup` command with agent detection and MCP registration is a genuinely good onboarding experience. The `cutctx wrap` command is excellent for the "just get it working" moment.

**Friction points.** The first `cutctx` invocation after install shows nothing — no welcome, no guidance, no "here's what to do next." Users must know to run `cutctx setup` or `cutctx wrap claude`. There is no `cutctx init` that walks through configuration interactively (the `init.py` exists but appears to be a different flow). The trial/checkout flow is behind the commercial package (`cutctx_ee`), which means the free tier experience has no guided path to "see savings" or "try premium features." The `cutctx perf` command exists but users won't know to run it until after they've been using the proxy for a while.

**Recommendation.** Make the first-run experience explicit. Either: (a) `cutctx` with no arguments shows a welcome screen with detected agents, proxy status, and suggested next step; or (b) the first `cutctx setup` includes a "what's happening" narrative rather than just `[1/5] Checking installation...`. Add a `cutctx tour` or `cutctx welcome` command that walks through the product's capabilities.

---

## 7. Profile/Multi-Config UX

**Strengths.** The `CompressionProfile` system is clever — it learns from past sessions to improve future compression. The workspace-hash-based profile lookup is automatic and transparent. The `ProfileManager` singleton with caching is efficient.

**Friction points.** There is no way for users to see or manage their profiles. No `cutctx profile list`, `cutctx profile show`, or `cutctx profile reset`. The profile data (compression ratios, retrieval counts, effectiveness scores) is stored in a JSON file but never surfaced to the user. Users don't know the system is learning, and they can't see what it's learned. The profile is silently loaded via `CompressionProfile.load()` in the pipeline — it's invisible.

**Recommendation.** Add `cutctx profile show` that displays current compression profile per workspace. Show a summary: "This workspace has been compressed 47 times. Average ratio: 0.42. Most compressible content: tool outputs. Most retrieved: code snippets." Let users reset or lock profiles.

---

## Summary of Priority Fixes

| Priority | Issue | Impact |
|----------|-------|--------|
| **P0** | No first-run experience (silent `cutctx` invocation) | Users install and see nothing — no guidance, no status |
| **P0** | Error messages lack actionable guidance | Users hit failures and don't know how to recover |
| **P1** | Configuration surface is overwhelming | New users freeze when looking at 700-line config model |
| **P1** | No `CutctxClient.from_env()` | SDK requires manual config wiring every time |
| **P2** | Internal docs mixed with user docs | QA-PLAYBOOK and LEAD_GEN clutter the docs/ directory |
| **P2** | Profile learning is invisible | Users don't know the system adapts or how to see it |
| **P3** | CLI help doesn't group by phase | 40+ commands listed flat in `--help` output |

---

*Analysis conducted by UX audit — read from: cli.py (shim), cli/main.py, cli/setup.py, cli/wrap.py, cli/_utils/formatting.py, config.py, parser.py, exceptions.py, client.py, trial.py, checkout.py, paths.py, profiles.py, README.md, PRODUCT_GUIDE.md, docs/LEAD_GEN_PLAYBOOK.md, docs/QA-PLAYBOOK.md.*
