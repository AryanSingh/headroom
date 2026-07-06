# Cutctx — Best-in-Class Savings & Commercial Readiness: Implementation Spec

**Date:** 2026-07-06
**Status:** Ready for implementation
**Companion doc:** `audit/go-no-go-assessment.md` (2026-07-05)
**Audience:** implementation agents. Every task has concrete file targets, step-by-step changes, acceptance criteria, and verification steps. Work top-to-bottom within a workstream; workstreams A–C are ordered by dependency, D can run in parallel.

---

## 0. Context — why this work exists

Live production data (`~/.cutctx/proxy_savings.json`, schema v3, 3 000 requests) shows:

| Signal | Value |
|---|---|
| `savings_by_source_tokens.provider_prompt_cache` | 203 016 679 tokens |
| `savings_by_source_tokens.cutctx_compression` | 1 492 523 tokens |
| All 9 other savings sources, lifetime USD | **$0.00** |
| `lifetime.compression_savings_usd` | $88.75 |
| `lifetime.savings_by_source_usd.cutctx_compression` | $0.019 (disagrees 4 500×) |
| `savings_by_source_usd` per history row | empty on every recent request |
| Compression fire rate (last 600 requests) | 20/600 (~3%) |
| Provider-cache credit rate (last 600 requests) | 588/600 (~98%) |

Root causes (verified in code):

1. **Provider prompt-cache savings are observed, not created.** Cutctx never injects `cache_control` (the only reference in the request path *strips* it for hashing — `cutctx/proxy/helpers.py:2900-2909`). Claude Code sets its own breakpoints. We currently headline savings that would exist without us. This is the same credibility failure mode the go/no-go audit flagged as "18× overstatement."
2. **Per-source USD is structurally zero.** `_build_savings_breakdown` (`cutctx/proxy/outcome.py:377-575`) only ever puts USD into `by_source_usd` for `model_routing`. Handlers attach token-only metadata (e.g. `{"tool_schema_compaction": {"tokens": N}}` at `cutctx/proxy/handlers/anthropic.py:1921`). Then `outcome.py:717-722` forwards USD deltas for only 5 of 7 sources — `tool_schema_compaction_usd_delta` and `api_surface_slimming_usd_delta` params exist on `SavingsTracker.record_request` (`savings_tracker.py:659-660`) but are **never passed**, so they default to 0 forever.
3. **Two compression-USD counters accumulate from different inputs.** `lifetime["compression_savings_usd"]` (`savings_tracker.py:803`) is fed by `delta_savings_usd`, which falls back to `_estimate_compression_savings_usd(model, tokens_saved)` (`savings_tracker.py:683-687`) — full list price × the *whole* `outcome.tokens_saved`. `savings_by_source_usd.cutctx_compression` (`savings_tracker.py:838-840`) only accumulates when a handler explicitly passes USD (almost never). $88.75 vs $0.019.
4. **Most features that would create non-cache savings are off, unhittable, or unwired:**
   - `semantic_cache` — on by default but keyed on exact SHA-256 of the *entire* messages array + model (`cutctx/proxy/semantic_cache.py:37-47`), non-streaming only. Agentic traffic never repeats an exact payload; hit rate is structurally ~0.
   - `model_routing` — route table empty by default (`model_router.py:187/250`).
   - `api_surface_slimming` — behind env `CUTCTX_TOOL_SURFACE_SLIMMING` + >24 tools (`tool_surface.py:66-88`).
   - `self_hosted_prefix_cache` — hard-coded 0, no producer.
   - `output_optimization`, `memoization`, `batch_routing` — code + tests exist, **no production caller**.
   - `normalization` — reserved slot, never emitted.
   - Compression itself fires on ~3% of requests, largely **by design**: `PrefixFreezeConfig` (`cutctx/config.py:~440`, enabled by default) freezes provider-cached prefixes so we don't trade a 90% cache-read discount for a 25% cache-write penalty. Correct behavior — but we have no telemetry distinguishing "correctly skipped" from "missed opportunity," and the SDK `CutctxConfig.default_mode` is `AUDIT` (`config.py:~466`).

**Strategy.** Provider caches will always dwarf per-request compression on agentic traffic — that is arithmetic (the cache discounts the entire re-sent prefix every turn; compression only touches new content). Best-in-class positioning is: (a) **ruthlessly honest attribution** that survives a customer's procurement audit, and (b) **savings that compose with the provider cache instead of competing with it** — suffix compression, cross-request dedup, tool-surface slimming, subrequest model routing. Those are dollars caching can't reach.

---

## Workstream A — Attribution integrity (P0, ~3–5 agent-days)

> Nothing in B or C is worth doing until the numbers are trustworthy. All A-tasks land together behind one schema bump.

### A1. Central per-source USD computation

**Problem:** USD is only ever attached for `model_routing`; everything else is token-only, so `by_source_usd` is empty and every `*_savings_usd` lifetime counter (except compression's estimated one) stays $0.

**Change:** compute USD for every source centrally in `_build_savings_breakdown` (`cutctx/proxy/outcome.py:377`), immediately after the by-source token dict is final (after the escape-hatch loop, before `return`). Do **not** ask handlers to attach USD — central valuation keeps pricing policy in one place.

Implementation steps:

1. Move `_estimate_compression_savings_usd` and `_estimate_input_cost_usd` out of `savings_tracker.py:229-292` into a new module `cutctx/proxy/savings_pricing.py` (savings_tracker keeps thin re-export aliases for backward compat — several tests import them). Add one new function:
   ```python
   def value_tokens_usd(model: str, tokens: int, *, rate: str = "input") -> float
   ```
   where `rate` is one of `"input"` (list input price), `"cache_read"` (uses litellm `cache_read_input_token_cost`, falling back to input price × 0.1 for Anthropic-prefixed models, else input price), `"cache_read_delta"` (input price − cache_read price, i.e. the *discount* value of a cached token). Reuse `_resolve_litellm_model` (`savings_tracker.py:184-226`) for model resolution. Return 0.0 on any lookup failure (match existing behavior).
2. In `_build_savings_breakdown`, after the by-source tokens dict is final, fill USD for every source that has tokens but no USD yet:

   | Source | Valuation rule |
   |---|---|
   | `provider_prompt_cache` | `value_tokens_usd(model, tokens, rate="cache_read_delta")` — the *discount* actually received, not list price |
   | `cutctx_compression` | `value_tokens_usd(model, tokens, rate="input")` — residual tokens were headed upstream at full price (prefix-freeze guarantees compressed tokens are uncached suffix) |
   | `semantic_cache` | avoided input tokens at `"input"` + avoided **output** tokens at output list price when the cached entry carries `output_tokens` (extend `CacheEntry` — see B1); until then input-only |
   | `prefix_cache_self_hosted` | `"input"` (self-hosted: avoided compute ≈ list price of the tokens) |
   | `model_routing` | keep the router's own `finalize_savings` USD (already correct); central rule only as fallback |
   | `tool_schema_compaction` | `"input"` |
   | `api_surface_slimming` | `"input"` |

   `_build_savings_breakdown` needs the model string — it already receives the full `RequestOutcome`; use `outcome.model`.
3. Escape-hatch metadata that already carries `usd > 0` wins over the central estimate (never overwrite a handler-provided exact figure with an estimate).

**Acceptance criteria:**
- A synthetic `RequestOutcome` with `cache_read_tokens=10_000, tokens_saved=12_000, model="claude-sonnet-5"` yields `by_source_usd` containing **both** `provider_prompt_cache` and `cutctx_compression` keys with values > 0, and `provider_prompt_cache` USD ≈ tokens × (input − cache_read) price.
- A `RequestOutcome` whose `savings_metadata` carries `{"tool_schema_compaction": {"tokens": 500}}` yields `by_source_usd["tool_schema_compaction"] > 0`.
- No source ever has USD > 0 with tokens == 0 unless a handler explicitly provided USD.

### A2. Forward the two orphaned USD deltas

**Problem:** `outcome.py:717-722` passes 5 named USD deltas + the dict; `tool_schema_compaction_usd_delta` / `api_surface_slimming_usd_delta` (already accepted by `record_request`, `savings_tracker.py:659-660`) are never passed, so `savings_tracker.py:702-711` coerces them to 0 forever.

**Change:** in the `handler.metrics.record_request(...)` call (`outcome.py:689-723`), add:
```python
tool_schema_compaction_usd_delta=_savings_by_source_usd.get("tool_schema_compaction"),
api_surface_slimming_usd_delta=_savings_by_source_usd.get("api_surface_slimming"),
```
Confirm `prometheus_metrics.py`'s `record_request` (`prometheus_metrics.py:546`) threads both through to `SavingsTracker.record_request` — add the two kwargs to its signature and pass-through if absent (check first; the by-source dict may already flow through, but named deltas are what the tracker's typed counters read).

**Acceptance:** run a request with tools through the proxy; `~/.cutctx/proxy_savings.json → lifetime.tool_schema_compaction_savings_usd` increases.

### A3. One source of truth for compression USD

**Problem:** the $88.75 vs $0.019 divergence (§0 item 3). Worse, the $88.75 is *inflated*: `_estimate_compression_savings_usd` values the whole `outcome.tokens_saved` at full list price, but a large share of those tokens overlaps content the provider cache would have discounted anyway.

**Change:**
1. In `outcome.py`, always pass `compression_savings_usd_delta=_savings_by_source_usd.get("cutctx_compression")` — after A1 this is never None on compressed requests, so the estimate fallback at `savings_tracker.py:683-687` becomes legacy-caller-only. Add a comment marking the fallback as legacy.
2. In `savings_tracker.record_request`, `delta_savings_usd` and `savings_by_source_usd["cutctx_compression"]` now derive from the same number. Add an assertion-grade debug log if they diverge by > $0.000001 on a single request.
3. **Migration:** bump `schema_version` to 4 in `savings_tracker.py` (`DEFAULT_SAVINGS_FILE` load path). On loading a v3 file: keep lifetime counters as-is (historical truth is unrecoverable), but write a one-time marker `"attribution_note": "counters before v4 use legacy estimated compression USD"` so the dashboard/report can badge pre-migration data. Do not attempt retroactive recompute.

**Acceptance:** after 50 fresh requests, `lifetime.compression_savings_usd` minus its pre-migration snapshot equals `lifetime.savings_by_source_usd.cutctx_compression` minus its snapshot, to the cent.

### A4. Honest headline: "created" vs "observed"

**Problem:** the dashboard's headline number blends cutctx-created savings with provider-cache savings the client created itself. Procurement will find this in one day of PoC; the audit already dinged marketing credibility.

**Change (backend):** add two derived fields to the tracker state and every `record_request` update:
- `created_savings_usd` = Σ by-source USD over {`cutctx_compression`, `semantic_cache`, `model_routing`, `tool_schema_compaction`, `api_surface_slimming`, `prefix_cache_self_hosted`, future wired sources}
- `observed_provider_savings_usd` = by-source USD for `provider_prompt_cache`

Persist both in `lifetime`, `display_session`, and each history row (as deltas). Expose in whatever endpoint feeds the dashboard (trace `dashboard/src/lib/api.js` → proxy route; likely `/dashboard` stats route in `cutctx/proxy/routes/`).

**Change (dashboard):** `dashboard/src/pages/Savings.jsx` and `Overview.jsx`:
- Headline card = **Created by cutctx** (USD). Secondary card = **Provider cache savings (observed)** with an info tooltip: "Prompt-cache discounts from your provider. Cutctx protects these (prefix-freeze) and reports them, but your client created them."
- By-source list: render only sources with nonzero lifetime value OR explicitly enabled; sources that are off/unwired get a collapsed "Available optimizations" section with an enable hint — never a $0.00 row. (Nine $0.00 rows in a demo reads as "product doesn't work.")
- Remove/repurpose the dead `parseRows('savings_by_source_tokens.model')` path flagged at `Savings.jsx:193-195`.
- Rebuild the bundled dashboard (`cutctx/dashboard/assets/`) after JSX changes — the built assets are checked in.

**Acceptance:** dashboard shows two distinct numbers; the created number reconciles with `created_savings_usd` in the JSON file; no $0.00 source rows render.

### A5. Tests for workstream A

Extend `tests/test_request_outcome.py` (exists, recently touched) and the savings-tracker cross-process tests (added in commit 7d3d9fe3):

- Unit: `_build_savings_breakdown` USD table — one test per row of the A1 valuation table, with litellm pricing mocked to fixed values (e.g. input=$3/M, cache_read=$0.30/M) so assertions are exact.
- Unit: A2 pass-through — spy on `SavingsTracker.record_request`, assert both orphaned deltas arrive non-None when metadata carries those sources.
- Unit: A3 equality — single funnel invocation, assert `delta_savings_usd == by_source_usd["cutctx_compression"]`.
- Migration: write a v3 fixture file, load, assert schema_version bumps to 4, counters preserved, note field present.
- Dashboard: extend `tests/test_dashboard_savings_period_and_metric_toggle.py` for the created/observed split.

**Run:** `uv run pytest tests/test_request_outcome.py tests/test_dashboard_savings_period_and_metric_toggle.py tests/test_proxy_client_model_savings.py -x -q`

### A6. End-to-end verification (workstream gate)

1. Start proxy against a mock upstream (existing test harness pattern; see the QA playbook) or run 20 real requests via Claude Code through the proxy.
2. `python3 - <<'EOF'` snippet: load `~/.cutctx/proxy_savings.json`, assert for the new rows: `savings_by_source_usd` non-empty whenever `savings_by_source_tokens` is; `cache_savings_usd` > 0 iff cache reads occurred; `created_savings_usd + observed_provider_savings_usd ≈ Σ by_source_usd` (±rounding).
3. `curl localhost:<port>/metrics | grep savings` — Prometheus gauges for the new fields present and consistent.
4. Open the dashboard, verify the split headline and absence of $0.00 rows (use the `webapp-testing`/Playwright harness; a regression test exists in `tests/test_dashboard_savings_period_and_metric_toggle.py` to extend).

---

## Workstream B — Make real features hit (P1, ~2 weeks)

### B1. Semantic cache that can actually hit

**Current:** exact SHA-256 over `{model, messages}` (`semantic_cache.py:37-47`), non-streaming only, wired at `handlers/anthropic.py:842/2630` and `openai/chat.py:313/1435`. Structurally ~0 hits on agentic traffic.

**Redesign — target the traffic that DOES repeat.** Agentic clients repeat: retry storms, title/topic-generation subrequests (Claude Code fires small haiku "summarize this conversation title" calls with near-identical shapes), `count_tokens` passthroughs, and identical tool-result → follow-up patterns across parallel subagents.

Steps:

1. **Normalized key.** Before hashing, run messages through `_strip_per_call_annotations` (`helpers.py:2909`) to drop `cache_control`, then additionally strip: `metadata.user_id`-style volatile fields, trailing whitespace, and any `<system-reminder>` blocks (they carry timestamps/injected state and defeat matching while being semantically inert for identical-response purposes). Add `SemanticCache._normalize(messages) -> list[dict]` with its own unit tests; hash the normalized form. Keep the model in the key.
2. **Streaming support.** Cache SSE responses: buffer the full event stream on the way out (only when total body ≤ configurable cap, default 256 KB), store raw bytes + content-type. On hit, replay the buffered SSE bytes verbatim with correct `text/event-stream` headers and per-event flush. Extend `CacheEntry` (`cutctx/proxy/models.py:~247`) with `is_streaming: bool` and `output_tokens: int` (parse from the buffered `message_delta`/`usage` events) so A1 can value output-token avoidance.
3. **Safety gates.** Only cache when: request has no `tools` with non-deterministic side effects implied (start conservative: allow tools — the response is replayed identically, which is correct for identical requests), `temperature` is absent or ≤ 0.3 (configurable), and response status is 200. Never cache error bodies. TTL default stays 3600 s; make `max_entries`/`ttl_seconds`/`max_body_bytes`/`temperature_ceiling` configurable via proxy config.
4. **Metrics.** Track hits AND misses (`ComponentStats` at `semantic_cache.py:139-147` has TODO placeholders for misses/evictions — fill them). Emit a Prometheus counter `cutctx_semantic_cache_{hits,misses,stores}_total`. On hit, set `outcome.semantic_cache_avoided_tokens` = full prompt tokens of the avoided request + record output tokens in metadata.
5. **Idempotency comment for reviewers:** a hit returns a previously-generated response for a byte-identical (post-normalization) request — same semantics the user would get from their own retry.

**Acceptance:** replay the same non-trivial request twice through the proxy (streaming on) → second response served from cache (assert `x-cutctx-semantic-cache: hit` response header — add it), `semantic_cache_savings_usd` increases, latency for the hit < 50 ms. Send two requests differing only in a `<system-reminder>` timestamp → still a hit. Two requests with different user text → miss.

**Tests:** new `tests/test_semantic_cache_normalization.py` (key normalization table-driven), streaming replay test (buffered SSE fidelity: byte-equal event stream), TTL expiry, temperature gate.

### B2. Compression decline telemetry + right default mode

**Current:** 3% fire rate with no visibility into why; SDK `CutctxConfig.default_mode = CutctxMode.AUDIT` (`config.py:~466`).

Steps:

1. In the pipeline decision path (`compression_decision.py`, `intelligence_pipeline.py`, prefix-freeze in `context_policy.py`/`cache/`), attach a `decline_reason` tag on every request that was eligible but not compressed: one of `{prefix_frozen, below_min_tokens, audit_mode, bypass_header, content_type_skip, license, error}`. `CompressionDecision.apply_to_tags` (`compression_decision.py:149`) already writes tags — extend the enum it writes.
2. Prometheus counter `cutctx_compression_decline_total{reason=...}` + surface in `cutctx perf` output.
3. Add a `savings_by_source_tokens.compression_declined_cached` style *diagnostic* (not a savings source): tokens skipped due to prefix-freeze, so the dashboard can show "X tokens protected from cache-busting" — this converts the 3% fire rate from an embarrassment into a feature ("we didn't torch your cache").
4. Verify what mode the proxy actually runs: if the proxy path inherits `default_mode=AUDIT` anywhere (trace `server.py` client construction), flip the proxy's effective default to `OPTIMIZE` and leave `AUDIT` for the SDK/first-run trial flow only. Gate with a config field, document in README.
5. **Suffix-aggressive policy:** with prefix-freeze protecting cached content, raise compression aggressiveness on the *unfrozen suffix* (tool results, file dumps): review `SmartCrusherConfig` thresholds so large tool results in the suffix always get considered (the workspace profiles in `~/.cutctx/profiles/` show recommended ratios ~0.85 being learned but rarely applied).

**Acceptance:** after 100 mixed requests, `curl /metrics` shows decline reasons summing to (eligible − compressed); dashboard/`cutctx perf` shows the protected-tokens figure; fire rate on suffix-heavy synthetic traffic (10 requests with 50 KB tool results beyond the cache breakpoint) ≥ 80%.

### B3. Tool-surface features on by default

1. `api_surface_slimming`: promote env `CUTCTX_TOOL_SURFACE_SLIMMING` (`tool_surface.py:66-88`) to a first-class config field `tool_surface_slimming_enabled: bool = True`, keep the >24-tools threshold configurable (`min_tools: int = 24`). Env var still overrides for kill-switch.
2. Both slimming and `tool_schema_compaction` USD attribution arrive via A1/A2 — nothing more needed for money to flow.
3. Safety: slimming must be allowlist-driven (never drop a tool the request's recent messages referenced). Verify existing logic; add a regression test where a message references a tool by name → that tool survives slimming.

**Acceptance:** MCP-heavy request (>24 tools) through the proxy → `api_surface_slimming_savings_usd` > 0 in the tracker; a referenced tool is never dropped.

### B4. Model-routing presets

**Current:** fully wired (`server.py:2040/4926`, finalization `outcome.py:606-656`) but the route table defaults empty, so it never fires.

1. Ship named presets in `model_router.py`: e.g. `economy` (`claude-opus-* → claude-sonnet-5` for requests < 2 000 input tokens and no tools — the title-generation/summary shape) and `subrequest-haiku` (small tool-free requests → `claude-haiku-4-5`). Preset = data, not code: a dict of `{source_pattern, target, max_input_tokens, require_no_tools}` rules.
2. CLI/config surface: `cutctx proxy --route-preset economy` and config field `model_routing.preset`. Off by default (routing changes model behavior — must be an explicit opt-in; that's the honest posture).
3. Docs: one page with measured quality caveats; never route when `tools` present or `max_tokens` > threshold, first iteration.

**Acceptance:** with preset on, a 500-token no-tools opus request is answered by sonnet, `model_routing_savings_usd` increases by the correct delta (verify against litellm pricing), and the response body still passes the client's schema. With preset off (default), zero routing occurs.

### B5. Self-hosted prefix cache: cut the slot (for now)

No producer exists (hard-coded 0 at `handlers/anthropic.py:882`, read only at `streaming.py:782-788`). Unless vLLM support is on the near-term roadmap, remove the source from dashboard display (A4 already hides $0 rows) and mark the code path `# reserved: vLLM APC` — do not delete plumbing. No new work.

---

## Workstream C — Wire or cut the dead features (P2, ~1 week)

Rule: a savings source appears in tracker/dashboard/marketing **only** if it has a production caller. Half-shipped categories cost more credibility than they signal ambition.

| Feature | Verdict | Action |
|---|---|---|
| `memoization` (`memoizer.py`, `memoize_interceptor.py`) | **Cut from surface, keep code** | After B1, the normalized semantic cache covers the realistic wins. Remove from `SAVINGS_SOURCES` display set; leave module + tests; revisit for deterministic tool-result memoization later. |
| `output_optimization` (`output_optimizer.py`, 22 K, tests only) | **Cut from surface** | Output shaping (injecting brevity instructions) changes model behavior — product-risky. Keep as experimental flag, no dashboard slot. |
| `batch_routing` (`batch_router.py`, needs `x-cutctx-batch: allow`) | **Wire minimally** | Real dollars: Anthropic/OpenAI batch APIs are −50%. Wire the header-gated path into `server.py` request routing so an SDK/CI caller can opt whole requests into batch. Attribute USD = 0.5 × input+output list cost, source `batch_routing`. If no wiring budget, cut from surface like the others. |
| `normalization` | **Fold** | It's not a user-meaningful source. Fold any future normalization tokens into `cutctx_compression` and delete the slot from display constants (`savings_tracker.py:42-63`, `savings/types.py:35`). Keep the enum member for on-disk backward compat. |

**Acceptance:** `grep`-level check that every member of the *displayed* source list has at least one production (non-test) call site that can attribute to it; dashboard shows no permanently-dead rows; `uv run pytest -q` green.

---

## Workstream D — Commercial hardening (parallel track)

The go/no-go audit (2026-07-05) is the source of truth; this consolidates it with the attribution work into one commercial plan. Sequence within D by the numbers.

### D1. Revenue path (CRITICAL, blocks any paying customer)
1. **Domain:** register/stand up `cutctx.com` (or chosen final brand) + static site from `docs/`; sweep all 30+ dead-URL references (`rg -l 'cutctx\.com|cutctx\.dev|pitchtoship\.com|github\.com/cutctx'`) and repoint. 1 week.
2. **Billing:** activate a real Stripe account; wire env vars for the existing (well-built) webhook handler; replace every `pitchtoship.com` checkout/portal URL in the CLI (`cutctx billing checkout/portal`) with Stripe-hosted checkout/customer-portal links; make dead-destination fallbacks **fail loud**, never fall back to a marketing page. 2–3 weeks.
3. **License activation:** point `license activate` at the new backend; **fix the canary bug** (SHA computed then discarded — watermark can't trace to license IDs). 1–2 weeks.
4. **Support:** working `support@<domain>` mailbox + a ticketing pipe (even a shared inbox + SLA labels); publish escalation path; add SLA-credit language to `SLA.md`. 2 days.
5. **Legal entity:** pick Payzli Inc. vs "Cutctx, Inc.", one consistency pass across DPA/LICENSING/TERMS; get TERMS.md out of draft with counsel. 1 day + counsel.

### D2. Trust & security (blocks enterprise pilots)
1. `/health` config leak — split into unauthenticated liveness (status only) + admin-gated `/health/config`. 1 day.
2. CCR retrieval routes `/v1/retrieve/*` — add admin-auth dependency (4 routes). 1 day.
3. Backup **restore** command + restore runbook + backup-failure alerting; extend backup set beyond 3/13 stores (at minimum: licenses, org, RBAC, billing state). 1 week.
4. SAML SSO (procurement blocker at Business/Enterprise tier). 2–3 weeks, schedule after pilots begin.
5. Load/concurrency test of the singleton pipeline (the audit flagged zero load testing): a locust/k6 script driving 50 concurrent streaming requests through the proxy for 10 min; record p95 overhead_ms; gate release on p95 added latency < 150 ms.

### D3. Credibility & positioning (what actually sells this)
1. **Kill every inflated number.** Sweep marketing copy for the "87% avg" claim (18× above production median). Replace with the defensible stat: *"78% compression at 0.999 F1 on real workloads"* + live created-vs-observed dashboard. The honest-attribution work in A4 becomes the demo: no competitor separates observed provider savings from created savings — make that THE differentiator ("numbers your CFO can audit").
2. **Procurement-grade savings report.** `cutctx report buyer` exists; extend it with the created/observed split, per-source USD, methodology appendix (pricing source = litellm tables, valuation rules from A1), and a signed/hash-stamped export. This is the artifact a champion forwards to finance.
3. **Fix the empty-analytics bug** — `savings --stats-only` returns "No sessions recorded" while `proxy_savings.json` holds 3 000 requests; the CLI is reading a different store (`session_stats.jsonl` is 0 bytes). Trace and unify on SavingsTracker. High demo-impact, ~1 day.
4. **Published benchmark harness.** `cutctx/evals/` exists — publish a reproducible public benchmark (fixed corpus, scripted run, F1 + ratio + $ table incl. cache interaction) so third parties can verify claims. Open-core credibility compounds.
5. **Time-to-value = 60 s for real.** `pip install 'cutctx[proxy]' && cutctx setup` must reach first-savings without manual proxy config; fold `cutctx mcp install` and client config into `setup`; measure and publish the honest number.
6. **Design-partner motion (audit Phase 3).** 3–5 concierge customers; instrument their created-savings numbers (with consent) into real case studies replacing the template ROI stories.
7. **Positioning line for the site/deck:** "Your provider's cache saves you X. Cutctx protects that cache *and* adds Y on top — compression, dedup, slimming, and routing that caching can't reach — with attribution your finance team can audit."

### D4. Suggested sequencing

| Sprint | Ship |
|---|---|
| 1 | A1–A6 (attribution) + D3.3 (stats bug) + D2.1/D2.2 (two 1-day security holes) |
| 2 | B1 (semantic cache) + B2 (decline telemetry/defaults) + D1.1 (domain) |
| 3 | B3/B4 (slimming default, routing presets) + C (wire-or-cut) + D1.2 billing start |
| 4 | D1.2–D1.5 finish, D2.3 restore, D3.1/D3.2 (honest marketing + buyer report) |
| 5–6 | D2.4 SAML, D2.5 load test, D3.4–D3.6 (benchmark, TTV, design partners) |

---

## Global verification checklist (run after each workstream)

```bash
# 1. Full test suite — must stay green (1344 passing baseline)
uv run pytest -q

# 2. Focused savings tests
uv run pytest tests/test_request_outcome.py tests/test_proxy_client_model_savings.py \
  tests/test_dashboard_savings_period_and_metric_toggle.py -x -q

# 3. Live-loop smoke: start proxy, drive 20 requests (Claude Code or scripted),
#    then assert on the tracker file:
python3 - <<'EOF'
import json, os
d = json.load(open(os.path.expanduser("~/.cutctx/proxy_savings.json")))
lt = d["lifetime"]
assert d["schema_version"] >= 4
row = d["history"][-1]
if row["savings_by_source_tokens"]:
    assert row["savings_by_source_usd"], "tokens attributed but USD empty"
created = lt.get("created_savings_usd", 0); observed = lt.get("observed_provider_savings_usd", 0)
print(f"created=${created:.4f} observed=${observed:.4f}")
EOF

# 4. Metrics endpoint consistency
curl -s localhost:8787/metrics | grep -E 'cutctx_(savings|semantic_cache|compression_decline)'

# 5. Dashboard visual check (Playwright / webapp-testing skill):
#    - created vs observed split rendered
#    - no $0.00 source rows
#    - by-source bars sum to the created total
```

**Definition of done for "best in class savings":** on a normal Claude Code workday routed through the proxy, the dashboard shows a nonzero **created** figure drawn from ≥3 distinct sources (compression, semantic cache, tool-surface), an **observed** provider-cache figure clearly separated, decline telemetry explaining every uncompressed request, and `cutctx report buyer` exports the same numbers with methodology — all backed by green tests and the load-test latency gate.
