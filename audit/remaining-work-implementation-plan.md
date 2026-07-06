# Remaining work: implementation plan for Workstreams A, B, C, and final verification

Status as of 2026-07-06. Tasks #1 and #2 (auth regression, `/health` config leak, CLI
`--stats-only` bug) are done and verified — see "Task #1/#2 closeout" below. This
document specifies the remaining work (#3-#6) at the level of exact files, exact
diffs, acceptance criteria, and verification commands, so it can be handed to an
agent and executed/checked without further design decisions.

All line numbers were re-verified against the current tree on 2026-07-06 (not
copied from the original audit spec, which had drifted). Re-check line numbers with
`grep -n` before editing if this document is used after further changes land.

---

## Task #1/#2 closeout (already done, record for the log)

- `conftest.py` TestClient admin-key injection scoped to only fire when
  `CUTCTX_ADMIN_API_KEY` still equals the suite default — fixes 10 previously-broken
  auth-rejection tests.
- `/dashboard` reverted to unauthenticated (shell-only, SPA does its own auth) in both
  `create_app` and the dead `_create_app_legacy` in `cutctx/proxy/server.py`.
  `tests/test_runtime_app_admin_auth.py` updated to drop `/dashboard` from its
  parametrize list (superseded by `tests/test_proxy_dashboard_html_auth_bypass.py`,
  the more recent QA-audited test).
- `tests/test_proxy/test_transformations_feed.py` was failing with 401 because it
  uses a raw `httpx.AsyncClient` + `ASGITransport` (not `starlette.testclient.TestClient`,
  so the conftest.py injection doesn't apply) against `/transformations/feed`, which
  legitimately requires admin auth (gated in `c4953df3`, well after the test was
  written in `0aae886f`). Fixed by adding an explicit `x-cutctx-admin-key` header to
  all three requests in that file, matching `CUTCTX_ADMIN_API_KEY`.
- `/health` no longer leaks `config`; new `GET /health/config` (admin-gated) added
  in both server.py app-factory copies.
- `cutctx/cli/savings.py` now prefers the live proxy store
  (`~/.cutctx/proxy_savings.json` via `SavingsTracker.get_summary_stats()`) over the
  legacy SQLite/JSONL backend, fixing the "No sessions recorded" bug.

Verification: `CUTCTX_ADMIN_API_KEY=test-admin-key-for-ci uv run pytest -q
tests/test_proxy/test_transformations_feed.py tests/test_runtime_app_admin_auth.py
tests/test_proxy_dashboard_html_auth_bypass.py tests/test_proxy_healthchecks.py
tests/test_route_modules.py tests/test_proxy_ccr.py tests/test_dsr_endpoints.py
tests/test_management_api_entitlements.py` → 85 passed, 0 failed (confirmed
2026-07-06). A full-suite baseline run is in flight; read its result before starting
Task #3 so new work starts from a known-good count rather than layering on top of
undiagnosed failures elsewhere.

Mark #1 and #2 `completed` once the full-suite baseline confirms no other
auth/health/CLI regressions remain.

---

## Ground truth correction vs. the original spec

The original `audit/best-in-class-implementation-spec.md` assumed `memoizer.py`,
`output_optimizer.py`, and `batch_router.py` were dead/unwired code and recommended
cutting their dashboard rows. That assumption is **wrong** — re-verified 2026-07-06:

- **Memoization** (`cutctx/proxy/memoizer.py` + `memoize_interceptor.py`): fully
  wired. `server.py` constructs `ToolMemoizer(MemoizeConfig(enabled=config.memoization))`
  and `MemoizeInterceptor`, attaches it to `ccr_response_handler`, and
  `handlers/anthropic.py:1078-1080` / `handlers/openai/chat.py:478-480` call
  `record_tool_results_from_messages`. Config flag `models.py:181
  memoization: bool = False` (off by default).
- **Output optimization** (`cutctx/proxy/output_optimizer.py`): fully wired.
  `server.py:444` constructs `OutputOptimizer(OutputOptimizeConfig(enabled=config.output_optimization))`;
  `handlers/anthropic.py:1988-1989` calls `output_optimizer.optimize(...)` and gets
  back an `OutputOptimizeDecision` with `estimated_tokens_saved`. Config flag
  `models.py:178 output_optimization: bool = False` (off by default).
- **Batch routing** (`cutctx/proxy/batch_router.py`): fully wired. `server.py:440-441`
  constructs `BatchRouter(BatchRouterConfig(enabled=config.batch_routing))`;
  `handlers/anthropic.py:605` calls `batch_router.route(...)`. `DEFAULT_BATCH_DISCOUNT
  = 0.50` already defined. Config flag `models.py:175 batch_routing: bool = False`.

**What's actually broken**: none of these three decisions ever reach
`RequestOutcome` / `_build_savings_breakdown` / `SavingsTracker`. The `SavingsSource`
enum (`cutctx/savings/types.py:10-24`) has no `MEMOIZATION`, `OUTPUT_OPTIMIZATION`,
or `BATCH_ROUTING` members, so even if a handler tried to attribute savings from
these paths there's nowhere typed to put it. This is why the 27 tests in
`tests/test_savings_types_{batch_routing,memoization,output_optimization}.py` fail,
and why these features contribute zero to dashboard/CLI savings figures despite
running in production when their flags are on.

**Revised scope for Task #5 (Workstream C)**: this is now an attribution-wiring
task, not a "build the feature or cut the row" task — much smaller than the
original spec implied, and squarely inside "don't remove features, wire them
properly."

---

## Task #3 — Workstream A: central USD attribution

### A0. Reuse existing pricing infra (don't build a new pricing table)

`cutctx/proxy/cost.py:930-960` already has `_get_list_price(model)` and
`_get_cache_prices(model)`, both built on `cutctx/pricing/litellm_pricing.py:resolve_litellm_model`
and `litellm.model_cost`. Do **not** create a new hardcoded pricing table. Instead:

**File**: `cutctx/proxy/savings_pricing.py` (new file, thin wrapper)

```python
"""Model-price lookups shared by cost tracking and savings attribution."""
from __future__ import annotations

from cutctx.pricing.litellm_pricing import resolve_litellm_model


def _get_litellm_module():
    import litellm
    return litellm


def value_tokens_usd(model: str, tokens: int, *, rate_per_million: float | None = None) -> float:
    """USD value of `tokens` input tokens for `model`, at list price by default.

    Pass `rate_per_million` to price at a different rate (e.g. 0.5x for batch
    routing, or a cache-read rate). Returns 0.0 if tokens <= 0 or pricing is
    unavailable (never raises — attribution is best-effort).
    """
    if tokens <= 0:
        return 0.0
    if rate_per_million is not None:
        return (rate_per_million / 1_000_000) * tokens
    try:
        litellm = _get_litellm_module()
        resolved = resolve_litellm_model(model)
        info = litellm.model_cost.get(resolved, {})
        cost_per_token = info.get("input_cost_per_token")
        return cost_per_token * tokens if cost_per_token else 0.0
    except Exception:
        return 0.0
```

Acceptance: `value_tokens_usd("claude-sonnet-4-5", 1000)` returns a positive float
matching `1000 * cost.py._get_list_price("claude-sonnet-4-5") / 1_000_000` (within
float tolerance) for any model already priced in `cost.py`. Add
`tests/test_savings_pricing.py` asserting this equivalence for 2-3 models, plus a
`rate_per_million=0.5` case, plus a graceful `0.0` for an unknown model string.

Then refactor `cost.py:_get_list_price` to call `value_tokens_usd` internally (or
leave it as-is and just have both use the same underlying `resolve_litellm_model` +
`model_cost` lookup) — whichever requires the smaller diff; do not change
`cost.py`'s public behavior/signature.

### A1. Unify compression USD attribution in `_build_savings_breakdown`

**File**: `cutctx/proxy/outcome.py:377` (`_build_savings_breakdown`)

Read the full function body first (`sed -n '377,470p' cutctx/proxy/outcome.py`) — it
already computes a `tokens_by_source` dict and a `_savings_by_source_usd` dict for
`tool_schema_compaction` and `api_surface_slimming` (confirmed populated, flows into
`record_request` at outcome.py:722-723 and `prometheus_metrics.py:581-582` — **not
orphaned**, contrary to the earlier note in this doc's predecessor; re-verify with
`grep -n "tool_schema_compaction\|api_surface_slimming" cutctx/proxy/outcome.py`
before assuming otherwise). Confirm `cutctx_compression` (the main compression
savings source) gets a USD figure the same way the others do — if it's currently
token-only, add a `value_tokens_usd(model, compression_tokens_saved)` call and put
it in `_savings_by_source_usd["cutctx_compression"]`.

Acceptance: every key present in the by-source *tokens* dict has a corresponding key
in the by-source *USD* dict after this function returns, for a synthetic
`RequestOutcome` exercising compression, semantic cache, self-hosted prefix cache,
and model routing simultaneously. Add this as a new test in
`tests/test_savings_orchestration.py` or a new `tests/test_savings_breakdown_usd_parity.py`.

### A2. Forward memoization/output_optimization/batch_routing USD once A3's enum lands

Deferred to Task #5 (Workstream C) since it depends on the new enum members — do
not duplicate; Task #5 covers this.

### A3. Schema version bump + migration marker

**File**: `cutctx/proxy/savings_tracker.py:29`

```python
SCHEMA_VERSION = 4
```

Add a one-time migration note. There is currently no migration function in this
file (`grep -n "migrate" cutctx/proxy/savings_tracker.py` returns nothing) — state
is read fresh via `_default_state`/`snapshot`, so a "migration" here just means: old
files on disk with `schema_version: 3` should not crash the loader, and the loader
should stamp a `attribution_note` field the first time it upgrades a v3 file to v4
in memory, e.g. in the function that loads state from disk (find it via `grep -n
"json.load\|_load_state\|def __init__" cutctx/proxy/savings_tracker.py`):

```python
if loaded.get("schema_version", 0) < 4:
    loaded["attribution_note"] = (
        "created_usd/observed_usd split introduced in schema v4; "
        "historical rows before this version report observed_usd only"
    )
    loaded["schema_version"] = SCHEMA_VERSION
```

Acceptance: loading a v3 fixture file (write one to
`tests/fixtures/proxy_savings_v3.json` using the current schema's actual shape —
copy a real `snapshot()` output and hand-edit `schema_version` to `3`) results in an
in-memory snapshot with `schema_version == 4` and `attribution_note` present.
New test: `tests/test_savings_tracker_schema_migration.py`.

### A4. Created vs. observed USD split

This is the largest sub-task. "Created" = USD value of tokens/requests avoided
regardless of whether the customer's bill reflects it (e.g., provider prompt cache
savings are real but the provider already discounts cache reads, so "observed" on
the invoice may differ from list-price "created" value). Concretely:

**File**: `cutctx/proxy/savings_tracker.py` — in the method that accumulates
`lifetime` counters (`record_request` — grep for `def record_request` in this
file), split each `*_savings_usd` field into two: keep the existing field name as
`created` (list-price value, what A0-A2 compute) and add a parallel
`*_observed_usd` field that mirrors it only when the discount is real cash-avoided
(e.g. compression, model routing) versus theoretical (e.g. a cache tier the
provider bills at a reduced rate anyway — subtract the provider's own list discount
first). Concretely:

```python
lifetime["compression_savings_usd"] += created_usd          # existing field, keep name
lifetime["compression_savings_observed_usd"] += observed_usd  # new field
```

Do this per-source for every `*_savings_usd` field currently in `lifetime` (listed
in this doc's "Key Technical Concepts" carryover: `compression_savings_usd`,
`cache_savings_usd`, `semantic_cache_savings_usd`,
`self_hosted_prefix_cache_savings_usd`, `model_routing_savings_usd`,
`tool_schema_compaction_savings_usd`, `api_surface_slimming_savings_usd`). Where
"observed" and "created" are identical (no separate provider discount to net out),
it is acceptable for `observed_usd == created_usd` — don't invent a discount that
doesn't exist.

**Dashboard**: `dashboard/src/pages/Savings.jsx` and `dashboard/src/pages/Overview.jsx`
— find where they render `*_savings_usd` fields (`grep -n "savings_usd" dashboard/src/pages/Savings.jsx dashboard/src/pages/Overview.jsx`)
and add a secondary label/column for the observed figure, e.g. "$X created · $Y
observed on your bill". After editing JSX, **rebuild the dashboard bundle** (check
`dashboard/package.json` for the build script, likely `npm run build` from
`dashboard/`, then confirm `cutctx/proxy/dashboard_assets/` or wherever
`get_dashboard_html`/static assets are served from picks up the new bundle — grep
`get_dashboard_html` in server.py to find the asset path it serves).

Acceptance: `GET /stats` (admin-authed) response includes both `*_savings_usd` and
`*_savings_observed_usd` keys for every source; dashboard renders both without a
build error (`npm run build` exits 0); a manual load of `/dashboard` in a browser
shows the new figure (do this check — don't just trust the build).

### A5/A6. Tests + e2e checklist

- Unit: `tests/test_savings_pricing.py` (A0), `tests/test_savings_breakdown_usd_parity.py`
  (A1), `tests/test_savings_tracker_schema_migration.py` (A3), extend
  `tests/test_proxy_savings_history.py` or similar for the created/observed split (A4).
- E2E manual checklist (run once all of A0-A4 land):
  1. Start proxy with a real (or mock) upstream key, send 5-10 varied requests
     (some with cacheable prefixes, some with tool calls) through it.
  2. `rtk gain` or `curl -H "x-cutctx-admin-key: $KEY" localhost:<port>/stats` and
     confirm every populated savings source has both a token figure and a
     created/observed USD figure, and totals reconcile
     (`sum(by_source USD) ~= total_savings_usd`, within rounding).
  3. Load `/dashboard` in a browser, open Savings and Overview pages, visually
     confirm the created/observed split renders and numbers match the `/stats` API.
  4. `cat ~/.cutctx/proxy_savings.json | python3 -m json.tool | grep -A2 schema_version`
     → confirm `4` and `attribution_note` absent (fresh file) or present (migrated
     file).

---

## Task #4 — Workstream B: semantic cache streaming, decline telemetry, tool-surface, routing presets

### B1. Semantic cache: streaming support + normalization

**File**: `cutctx/proxy/models.py:91-99` (`CacheEntry` dataclass) — add two fields:

```python
@dataclass
class CacheEntry:
    response_body: bytes
    response_headers: dict[str, str]
    created_at: datetime
    ttl_seconds: int
    hit_count: int = 0
    tokens_saved_per_hit: int = 0
    is_streaming: bool = False
    output_tokens: int = 0
```

Find the semantic cache module (`grep -rln "class SemanticCache\|semantic_cache" cutctx/proxy/*.py`
— likely `semantic_cache.py`, confirm exact filename first) and:
1. Where a cache entry is currently written on a cache-store path, detect if the
   original response was an SSE stream (check `response_headers.get("content-type", "").startswith("text/event-stream")`
   or however the handler already detects streaming — grep `text/event-stream` in
   `handlers/anthropic.py`/`handlers/openai/chat.py` for the existing pattern) and
   set `is_streaming=True`, buffering the full concatenated SSE body into
   `response_body` rather than skipping caching for streams (confirm current
   behavior first — `grep -n "stream" <semantic_cache_file>` to see if streams are
   currently excluded from caching entirely; if so, that's the gap to close).
2. On a cache hit for a streaming original request, replay `response_body` as a
   synthetic SSE stream (chunk it back out with the same event framing) instead of
   returning it as a flat body — the client expects an SSE stream if it requested
   `stream: true`.
3. Normalization: before hashing the request for cache-key lookup, strip
   per-call-only fields (request id, timestamp, `metadata.user_id`, etc.) using the
   same helper pattern named `_strip_per_call_annotations` in the spec — check if
   this helper already exists (`grep -rn "_strip_per_call_annotations" cutctx/`); if
   not, add it as a small function in the semantic cache module that pops known
   volatile keys before hashing.

Acceptance: new test `tests/test_semantic_cache_streaming.py` — (a) a streaming
request gets cached and a subsequent identical streaming request gets a
cache-hit replayed as SSE chunks (assert `content-type: text/event-stream` and
multiple `data:` lines in the replayed body, not one flat blob); (b) two requests
differing only in a volatile per-call field (e.g. a timestamp in metadata) hit the
same cache key.

### B2. Compression decline telemetry + Prometheus counter

**File**: `cutctx/proxy/compression_decision.py` — the field is named
`passthrough_reason: str | None` (on the `CompressionDecision` dataclass starting
line 38), not `decline_reason` — the original spec's naming was stale, use the
actual field. Values assigned around lines 125-142 in `decide()`:
`"bypass_header"`, `"compression_disabled"`, `"no_messages"`, `"license_denied"`, or
`None`. Currently only logged (`handlers/anthropic.py:1193`,
`handlers/gemini.py:468/836/1119`), no metric increment exists.

Add a Prometheus counter in `cutctx/proxy/prometheus_metrics.py` (find where other
counters are declared, e.g. near the `record_request` definition at line 546 —
`grep -n "Counter(" cutctx/proxy/prometheus_metrics.py` for the existing pattern to
match):

```python
compression_declined_total = Counter(
    "cutctx_compression_declined_total",
    "Requests where compression was not applied, by reason",
    ["reason"],
)
```

Then in each of the three call sites currently only logging the reason, also call
`prometheus_metrics.compression_declined_total.labels(reason=decision.passthrough_reason or "unknown").inc()`
(match whatever the existing metrics-access pattern is in those handlers — likely
via a shared `metrics` object rather than importing the module-level counter
directly; check how other counters are incremented in `handlers/anthropic.py` first).

Also fix the AUDIT→OPTIMIZE default-mode issue for the proxy path: find where
compression mode defaults to `AUDIT` (grep `"AUDIT"` or `CompressionMode.AUDIT` in
`compression_decision.py` and `models.py`/config) and confirm the proxy's default
config uses `OPTIMIZE` unless a test or CLI flag explicitly requests audit-only
mode. This was flagged as a bug in the original spec — verify it's still live
before changing anything (`grep -n "CompressionMode.AUDIT\|default.*audit" cutctx/proxy/models.py cutctx/proxy/compression_decision.py`).

Acceptance: `tests/test_compression_decline_telemetry.py` — trigger each of the 4
decline reasons via a crafted request, assert the Prometheus counter with the
matching `reason` label increments (scrape `/metrics` or inspect the counter object
directly via `prometheus_client.REGISTRY`).

### B3. Tool-surface slimming default

**File**: `cutctx/proxy/tool_surface.py:66-70` — already defaults to enabled
(`tool_surface_slimming_enabled()` returns `True` unless an env var explicitly
disables it). The original spec assumed this needed a new `bool = True` config
field — **re-verify this is actually still a gap** before doing anything:
`grep -rn "tool_surface_slimming_enabled\|ENABLE_ENV" cutctx/proxy/tool_surface.py cutctx/proxy/models.py`.
If a proper `ProxyConfig.tool_surface_slimming_enabled: bool = True` field does not
exist alongside the env-var check (i.e. it's env-var-only, not exposed as a typed
config field or CLI flag), add one to `cutctx/proxy/models.py` next to the other
`bool = False`/`True` feature flags (near line 175-181), wire it into
`tool_surface_slimming_enabled()` so config takes precedence over the env var, and
add an allowlist safety test confirming a tool named in a
"never slim" allowlist (if one exists — grep for `allowlist` in `tool_surface.py`)
is never modified regardless of this flag.

Acceptance: `tests/test_tool_surface_config_flag.py` — config flag `True`/`False`
both override the env var; allowlisted tools are untouched either way.

### B4. Named model-routing presets

**File**: `cutctx/proxy/model_router.py` — currently a flat `ModelRouterConfig.routes`
list (lines 131-146) with 4 hardcoded downgrade pairs and threshold-based
classification (`TaskComplexity` enum at line 53, `RoutingDecision` at line 180).
No preset concept exists yet.

Add two named presets as alternate `ModelRouterConfig` factory constructors, off by
default, opt-in via config/CLI flag:

```python
@classmethod
def economy_preset(cls) -> "ModelRouterConfig":
    """Aggressive downgrade: routes any eligible request to the cheapest
    capable model. Opt-in only — changes response quality tradeoffs."""
    return cls(routes=[...])  # broader set of downgrade pairs than the default

@classmethod
def subrequest_haiku_preset(cls) -> "ModelRouterConfig":
    """Routes only sub-agent/tool-loop internal requests (not the top-level
    user-facing turn) to Haiku-tier models."""
    return cls(routes=[...], ...)  # scope routes to a marker the caller sets,
    # e.g. only apply when a request carries an internal "subrequest" tag/header
```

Wire selection via a new config field, e.g. `models.py:
model_routing_preset: str | None = None` (values: `None`, `"economy"`,
`"subrequest-haiku"`), and in `server.py` wherever `ModelRouterConfig()` is
currently constructed, branch on this field to pick the preset factory instead of
the bare default. Off by default (`None` → current bare-default behavior,
unchanged).

Acceptance: `tests/test_model_router_presets.py` — with no preset configured,
routing behavior is byte-identical to today's default; with `"economy"` configured,
more request shapes get downgraded than the default; with `"subrequest-haiku"`
configured, only requests carrying the internal subrequest marker get routed,
top-level user turns do not.

---

## Task #5 — Workstream C: wire memoization/output_optimization/batch_routing attribution (revised scope, see "Ground truth correction" above)

### C1. Add the three missing `SavingsSource` enum members

**File**: `cutctx/savings/types.py:10-24`

```python
class SavingsSource(str, Enum):
    PROVIDER_PROMPT_CACHE = "provider_prompt_cache"
    CUTCTX_COMPRESSION = "cutctx_compression"
    TOOL_SCHEMA_COMPACTION = "tool_schema_compaction"
    API_SURFACE_SLIMMING = "api_surface_slimming"
    SEMANTIC_CACHE = "semantic_cache"
    PREFIX_CACHE_SELF_HOSTED = "prefix_cache_self_hosted"
    MODEL_ROUTING = "model_routing"
    MEMOIZATION = "memoization"                # new
    OUTPUT_OPTIMIZATION = "output_optimization"  # new
    BATCH_ROUTING = "batch_routing"              # new
    NORMALIZATION = "normalization"
```

This alone should fix most of the 27 failing tests in
`tests/test_savings_types_{batch_routing,memoization,output_optimization}.py` —
run them first after this one-line-per-member change to see how many pass before
doing anything else:
`uv run pytest -q tests/test_savings_types_batch_routing.py tests/test_savings_types_memoization.py tests/test_savings_types_output_optimization.py`

### C2. Add typed `RequestOutcome` fields and wire real handler call sites

**File**: `cutctx/proxy/outcome.py` — `RequestOutcome` currently has no
memoization/output_optimization/batch_routing fields (confirmed via
`grep -n "memoiz\|output_optim\|batch_rout" cutctx/proxy/outcome.py` → no matches).
Add, following the existing pattern used for `model_routing_tokens_saved` /
`model_routing_usd_saved`:

```python
memoization_hits: int = 0
memoization_tokens_saved: int = 0
output_optimization_tokens_saved: int = 0
batch_routing_tokens_saved: int = 0
batch_routing_usd_saved: float = 0.0
```

Wire the setters at the real call sites:
- **Memoization**: `handlers/anthropic.py:1078-1080` and
  `handlers/openai/chat.py:478-480` call `record_tool_results_from_messages` on the
  interceptor — check its return value (does it report how many tool calls were
  served from cache, and the token cost of what was skipped? If not, extend
  `MemoizeInterceptor.intercept_tool_calls`/`record_tool_results_from_messages` in
  `memoize_interceptor.py` to return a hit count + estimated tokens, mirroring how
  `output_optimizer.optimize()` returns `estimated_tokens_saved`). Set
  `outcome.memoization_hits`/`memoization_tokens_saved` from that return value at
  each handler call site.
- **Output optimization**: `handlers/anthropic.py:1988-1989` already gets an
  `OutputOptimizeDecision` with `estimated_tokens_saved` (output_optimizer.py:140)
  back from `output_optimizer.optimize(...)` — just assign
  `outcome.output_optimization_tokens_saved = opt_decision.estimated_tokens_saved`
  right after that call, it's not currently stored anywhere on the outcome.
- **Batch routing**: `handlers/anthropic.py:605` calls `batch_router.route(...)` —
  check the returned `BatchRouterDecision` (batch_router.py:92) for whether it
  carries token/cost info; if it only carries an allow/deny + queue decision, compute
  `batch_routing_usd_saved = value_tokens_usd(model, input_tokens, rate_per_million=list_rate * (1 - DEFAULT_BATCH_DISCOUNT))`
  (i.e. 0.5x list cost per the existing `DEFAULT_BATCH_DISCOUNT = 0.50` constant)
  at the handler call site when the decision routes to batch, using `value_tokens_usd`
  from A0.

### C3. Fold the three new sources into `_build_savings_breakdown`

**File**: `cutctx/proxy/outcome.py:377`, inside `_build_savings_breakdown` — add three
more `if outcome.X: tokens_by_source[SavingsSource.Y] = ...` blocks following the
exact pattern already used for `semantic_tokens`/`self_hosted_tokens`/`model_routing_tokens`
near the top of the function (lines ~400-410). Make sure both the tokens dict and
the USD dict get entries (USD via `value_tokens_usd` from A0 for memoization/output
optimization; batch routing USD comes pre-computed from C2).

### C4. Dashboard display

Per the governing instruction ("wire properly, don't remove"), these three sources
must appear on the dashboard, not be hidden. Find where `by_source` savings are
rendered (`grep -n "by_source\|SavingsSource" dashboard/src/pages/Savings.jsx`) and
confirm the rendering is already generic over whatever keys are present in the API
response (likely — since it's presumably iterating the by_source dict rather than
hardcoding source names). If it iterates generically, no JSX change is needed —
just confirm via a manual `/dashboard` load once C1-C3 land and a
memoization/output-optimization/batch-routing event has actually fired in a test
session (flip the relevant config flags on temporarily, send a few requests through
a local proxy instance, then check the dashboard row appears).

Acceptance:
- All 27 tests in `tests/test_savings_types_{batch_routing,memoization,output_optimization}.py`
  pass.
- New test `tests/test_outcome_memoization_output_optimization_batch_routing_attribution.py`:
  construct synthetic `RequestOutcome`s with each of the three new fields set,
  call `_build_savings_breakdown`, assert the corresponding `SavingsSource` key
  appears in both the tokens and USD dicts with the expected values.
- Manual dashboard check per C4.

---

## Task #6 — final verification pass

Run in this order once #3-#5 land:

1. `uv run pytest -q` (full suite, no filters) — capture to a file, `grep -c "^FAILED"`
   must match the reported failed count exactly (past sessions hit truncated-output
   bugs piping through `tail`; don't pipe through `tail` when counting).
2. Diff the failure count against the Task #1/#2 closeout baseline — every new
   failure must trace to something touched in #3-#5; zero tolerance for unexplained
   new failures.
3. Targeted spec tests: `uv run pytest -q tests/test_savings_types_batch_routing.py
   tests/test_savings_types_memoization.py tests/test_savings_types_output_optimization.py
   tests/test_savings_pricing.py tests/test_savings_breakdown_usd_parity.py
   tests/test_savings_tracker_schema_migration.py tests/test_semantic_cache_streaming.py
   tests/test_compression_decline_telemetry.py tests/test_tool_surface_config_flag.py
   tests/test_model_router_presets.py tests/test_outcome_memoization_output_optimization_batch_routing_attribution.py`
   → all pass.
4. `cat ~/.cutctx/proxy_savings.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('schema_version'), 'created_usd' in str(d))"`
   against a freshly-generated file (delete/rename the old one first if reusing a
   dev machine, or point `CUTCTX_SAVINGS_PATH`/equivalent env var at a scratch path)
   → schema_version `>= 4`, created/observed split present.
5. `npm run build` inside `dashboard/` exits 0; manually load `/dashboard` in a
   browser against a locally running proxy that has processed a handful of varied
   requests (some compressed, some cached, some routed, some memoized/output-optimized
   if those flags are on) and visually confirm every savings source row renders with
   both token and USD (created + observed) figures, and that `/health` does not
   include a `config` key while `/health/config` (with the admin header) does.
6. Mark tasks #3-#6 `completed` only after steps 1-5 all pass with no unexplained
   regressions.
