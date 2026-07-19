# Spec: Compression Evaluation Dashboard (+ Cost Attribution)

**Status:** Draft for implementation
**Priority:** P1 (Phase 1 — mostly wiring of existing data)
**Date:** 2026-07-19
**Origin:** `docs/specs/features-from-youtube-research.md` §8, pulling forward parts of §14 (Cost Attribution) because the infra (`spend_ledger.db`, `spend_emitter.rs`, `savings_tracker.py`, `savings-sources.js`) already exists.
**Depends on:** nothing for v1 (existing metrics). The Evals page's quality panels depend on `spec-multi-signal-eval.md`; ship the page with those panels behind a "no data yet" state.

---

## 1. Problem

Cutctx's savings are invisible unless users go digging. The React dashboard (`dashboard/`, Vite 8 + React 19, served by the Python proxy at `/dashboard`) already has Overview/Savings/Memory/etc. pages polling `/stats`, `/stats-history`, `/health` — but there is **no per-strategy, per-agent, per-session evaluation view**, no compression-quality surface, and cost attribution stops at global lifetime totals. Enterprise ROI conversations need: which agents save what, which strategies are safe, what would this month have cost without Cutctx — exportable.

## 2. Goals

- A new **Evals** page in `dashboard/src/pages/` with four panels: Savings breakdown (per strategy / content-type / agent), Quality (scorecard signals), Strategy distribution, and Session drill-down.
- Extend the **Savings** page with cost attribution by tenancy (org → workspace → project → agent), month-to-date and historical.
- New JSON API endpoints on the Python proxy (`cutctx/proxy/server.py`) that serve both the dashboard and external tooling (CLI, CSV export) — "output as CLI/API for integration with external dashboards" per the research doc.
- A `cutctx report evals` CLI subcommand rendering the same data as text/CSV/JSON.
- No new databases: read from what exists — `proxy_savings.json` (SavingsTracker), spend ledger (`/v1/spend/*` EE API), Prometheus (Rust proxy `/metrics`), scorecards.db (when present).

## 3. Non-goals (v1)

- Editing anything (flags, policies) from the dashboard — read-only.
- Chargeback invoicing/exports to finance systems (CSV export is the v1 answer; full chargeback = research doc §14 remainder).
- Real-time streaming updates (keep the existing polling model in `use-dashboard-data.js`; interval 15s).
- Grafana dashboards (Prometheus metrics already exist for that; we ship JSON API + our UI).

## 4. Current state (ground truth)

**Frontend** — `dashboard/`: pages Overview, Savings, Capabilities, Docs, Firewall, Governance, Memory, Orchestrator, Playground, Replay (`dashboard/src/pages/`). Data layer: `src/lib/api.js` (`getProxyBaseUrl()` from `VITE_CUTCTX_PROXY_URL`), `use-dashboard-data.js` + `dashboard-context.jsx` (central polling of `/stats`, `/health`, `/stats-history`), `fetch-with-timeout.js`, `admin-auth.js`, `format.js`, `period-stats.js`. Savings model: `src/lib/savings-sources.js` — 11 savings sources split CREATED vs OBSERVED, helpers `sumSavingsUsd`, `getCreatedObservedSavingsUsd`, `getAttributionCoverage`, `getCreatedSavingsRate`. Build lands in `cutctx/dashboard/assets/` and is served by FastAPI (`server.py:4267–4284`), admin-key gated (`server.py:4989`).

**Data sources:**
- `SavingsTracker` (`cutctx/proxy/savings_tracker.py`) — authoritative lifetime/session savings, file `proxy_savings.json` (`CUTCTX_SAVINGS_PATH`), per-source USD fields matching `savings-sources.js`, `_estimate_compression_savings_usd(model, tokens_saved)` at :430, `snapshot()` feeds `/stats` (`server.py:3634`, `_build_policy_summary` :5392).
- Spend ledger — Rust proxy emits `SpendEvent {ts, org_id, workspace_id, project_id, agent_id, model, provider, auth_mode, input_tokens, output_tokens, tokens_saved, est_cost_usd: None, est_cost_saved_usd: None, request_id}` (`observability/spend_emitter.rs`) batched to `POST {ledger_url}/v1/spend/events`; receiver `cutctx/proxy/routes/spend.py` mounts EE `cutctx_ee.ledger.api.router`, store at `CUTCTX_SPEND_DB_URL` (default `sqlite:///spend_ledger.db`), gated `require_admin_auth` + `require_rbac_permission("spend.read")`. **Schema lives in closed `cutctx_ee`** — dashboard must consume the EE HTTP API, not the DB file.
- Rust Prometheus `/metrics`: `proxy_compression_ratio_by_strategy{strategy,content_type}`, `proxy_cache_hit_rate_per_session{provider}`, rejected/passthrough counters, rate-limit gauges (`observability/metric_names.rs`).
- Python `/stats`, `/stats-history` (`server.py:3634/3793`), `/v1/sessions` + `/{id}/replay` + `/{id}/state` (:3642–3709), `/transformations/traces|feed` (:3895/3922), `/v1/retrieve/stats` (:4189).
- Scorecards (future, from `spec-multi-signal-eval.md`): SQLite `~/.cutctx/scorecards.db`, aggregate contract `StrategyReport`.
- Known caveat: multi-worker `/stats` instability (server.py:4675–4688 — each poll can hit a different worker's partial totals). New endpoints must not inherit this (see §5.5).

**CLI:** `cutctx savings` (`cutctx/cli/savings.py`) reads `proxy_savings.json`; `cutctx report` exists as a subcommand group (`cutctx/cli/main.py`).

## 5. API design (Python proxy — new router `cutctx/proxy/routes/evals.py`)

All endpoints admin-key gated like `/stats` (server.py:4989 pattern), RBAC permission `evals.read` (follow `spend.read` precedent), mounted in `server.py` next to the EE routers (:4452+). All support `?from=<unix>&to=<unix>` (default: last 7 days) and `?format=json|csv`.

### 5.1 `GET /v1/evals/savings`

Per-dimension savings rollup. Query param `group_by` ∈ `strategy | content_type | agent | project | workspace | org | model | flag_arm` (repeatable, max 2).

```json
{
  "window": {"from": 0, "to": 0},
  "rows": [
    {"key": {"strategy": "smart_crusher"}, "requests": 1204,
     "tokens_before": 91827364, "tokens_after": 12873645, "tokens_saved": 78953719,
     "est_usd_saved": 512.33, "mean_compression_ratio": 0.14}
  ],
  "totals": {"tokens_saved": 0, "est_usd_saved": 0.0},
  "attribution_coverage_percent": 97.2
}
```

Sources: spend-ledger EE API for tenancy dimensions (`agent/project/workspace/org/model` — the ledger has these fields); `SavingsTracker` per-source totals for `strategy`-level USD; strategy/content_type token detail from scorecards.db when present, else from the Rust Prometheus histogram sums (scrape-and-cache, §5.5). USD conversion: reuse `_estimate_compression_savings_usd` — single source of truth for rates; do NOT duplicate rate tables in JS.

### 5.2 `GET /v1/evals/strategies`

Strategy distribution + quality. One row per (strategy, content_type):
`{requests, share_percent, tokens_saved, mean_ratio, quality: {s1_mean, s1_p10, s4_violation_rate, n, confidence} | null}` — quality block null until scorecards.db exists (dashboard renders "enable --eval-scorecards" hint).

### 5.3 `GET /v1/evals/summary`

The scorecard aggregate contract (multi-signal spec §6.5 `StrategyReport`) + headline numbers for the page header: lifetime + window tokens/USD saved (from SavingsTracker snapshot), integrity violations in window, retrieval rate (`/v1/retrieve/stats` join — retrievals / markers created).

### 5.4 `GET /v1/evals/sessions/{session_key}`

Session drill-down: per-request rows `{ts, request_id, strategy, rationale, tokens_before, tokens_after, s1_score?, flag_arm?}`. Source: scorecards.db when present; else degrade to `/v1/sessions/{id}/state` data (fewer columns). Links to the existing Replay page for full trace (`/v1/sessions/{id}/replay` already exists — reuse, don't rebuild).

### 5.5 Aggregation service

New `cutctx/proxy/eval_aggregator.py`:
- Owns read access to: SavingsTracker snapshot, scorecards.db (read-only SQLite conn), EE spend API (loopback HTTP with admin creds), Rust `/metrics` scrape (optional, `CUTCTX_RUST_PROXY_METRICS_URL`).
- Caches responses 10s (dashboard polls at 15s) — avoids hammering SQLite and the EE API.
- **Multi-worker correctness:** aggregator reads only *persisted* stores (files/DBs/HTTP), never in-process counters — this sidesteps the `/stats` per-worker instability by construction. Document this in the module docstring.

## 6. Frontend design

### 6.1 New page `dashboard/src/pages/Evals.jsx`

Route `/evals` in `App.jsx`, nav icon `Gauge` (lucide-react). Follows existing page conventions (theme tokens, error boundary, `fetch-with-timeout`). Layout, top to bottom:

1. **Header strip** — window picker (24h / 7d / 30d / custom), headline tiles: Tokens saved, $ saved (created vs observed split — reuse `getCreatedObservedSavingsUsd` from `savings-sources.js`), Quality p10, Integrity violations (red if >0), Retrieval rate.
2. **Savings breakdown panel** — grouped bar/table toggle over `/v1/evals/savings?group_by=`; dimension switcher (strategy / content-type / agent / model / flag arm). CSV export button = same endpoint with `format=csv`.
3. **Strategy panel** — table from `/v1/evals/strategies`: share %, mean ratio, tokens saved, quality columns (s1 mean, s1 p10, violation rate) with threshold coloring (p10 < 0.85 amber, violations > 0 red). Null-quality state renders setup hint.
4. **Sessions panel** — top sessions by tokens saved; row click → drill-down drawer from `/v1/evals/sessions/{key}` with "open in Replay" link.

New lib module `dashboard/src/lib/evals-api.js` (mirror `routing-studio/api.js` pattern: page-scoped API module rather than growing the global context). Poll only while page is visible (`document.visibilityState`), 15s.

### 6.2 Savings page extension

`pages/Savings.jsx` gains an **Attribution** section: tenancy treemap/table (org → workspace → project → agent) from `/v1/evals/savings?group_by=org,agent`, MTD and window views, plus `attribution_coverage_percent` displayed via existing `getAttributionCoverage`. Requests lacking tenancy headers roll into `unattributed` (matching `savings-sources.js` `legacy_unattributed` semantics).

### 6.3 Empty/degraded states (explicit, required)

- No spend ledger configured → attribution panels show setup instructions (`CUTCTX_SPEND_DB_URL`, `--spend-ledger-url`).
- No scorecards → quality columns show "—" + hint chip.
- Rust proxy metrics URL unset → strategy token detail falls back to SavingsTracker-only granularity with an info banner.
Never render zeros that could be mistaken for "no savings" when the truth is "no data source" — this is the UI version of the no-silent-fallbacks rule.

## 7. CLI

`cutctx report evals` (new file `cutctx/cli/report_evals.py`, registered under the existing `report` group):

```
cutctx report evals [--from ... --to ...] [--group-by strategy|agent|...]
                    [--format table|json|csv] [--proxy-url ...]
```

Thin client over `/v1/evals/*` (auth via existing admin-key envs). Exit code 2 if integrity violations > 0 in window — makes it CI-usable as a release gate.

## 8. Observability & security

- Endpoints emit standard FastAPI access logs; add counter in Python Prometheus (`cutctx/proxy/prometheus_metrics.py`) `evals_api_requests_total{endpoint, status}`.
- RBAC: `evals.read` permission; session drill-down additionally requires `sessions.read` if that permission exists in EE RBAC, else `evals.read` suffices — check `cutctx_ee` RBAC registry at implementation time and record the decision in the router docstring.
- CSV export caps at 100k rows, streaming response.
- No message content ever appears in these APIs — token counts, scores, and identifiers only (content stays in CCR/replay behind their own gates).

## 9. Testing

- **API unit:** each endpoint against fixture stores (seeded scorecards.db, canned SavingsTracker JSON, stub EE spend API via `respx`): grouping, windowing, CSV shape, RBAC 403s, null-quality degradation.
- **Aggregator:** cache behavior; multi-worker simulation (two processes writing SavingsTracker files — assert aggregator reads persisted state consistently).
- **Frontend:** extend the existing Playwright e2e (`dashboard/e2e/`): page renders all four panels against a seeded proxy; empty-state variants; CSV download; drill-down → Replay navigation.
- **Contract test:** JSON schema snapshots for all four endpoints checked into `tests/fixtures/evals_api/` — the Rust-side `aggregate.rs` (multi-signal spec) validates its output against the same `/v1/evals/summary` schema.
- **Numbers reconciliation test:** for a scripted session, `tokens_saved` must agree across: Outcome sums (Rust), SpendEvents in the ledger, SavingsTracker snapshot, and `/v1/evals/savings` totals — one test, four assertions; catches double-counting.

## 10. Acceptance criteria

1. Evals page renders with real data end-to-end in the docker-compose dev stack; all panels degrade cleanly with any data source absent.
2. Reconciliation test passes: no double counting across the four savings surfaces.
3. `cutctx report evals --format csv` output loads in a spreadsheet with documented columns.
4. p95 API latency < 200ms against 1M-row scorecards.db (indexes proved by `EXPLAIN QUERY PLAN` test).
5. Unauthorized access to every new endpoint returns 401/403.

## 11. Implementation plan

1. `eval_aggregator.py` + `/v1/evals/savings` + `/v1/evals/summary` from SavingsTracker + spend API only (no scorecards). (~2 days)
2. `/v1/evals/strategies` + `/v1/evals/sessions/{key}` with scorecards.db integration + degraded paths. (~1.5 days)
3. `Evals.jsx` + `evals-api.js` + nav/route + empty states. (~2 days)
4. Savings page Attribution section. (~1 day)
5. CLI `report evals` + CSV. (~0.5 day)
6. Playwright + contract + reconciliation tests. (~1.5 days)

## 12. Open questions

1. Should the Rust proxy grow its own minimal `/v1/evals/summary` (reading scorecards.db directly) for deployments that don't run the Python proxy? Lean yes, post-v1 — the contract test already pins the schema both sides.
2. Dollar rates: `_estimate_compression_savings_usd` model-rate table freshness — out of scope here, but flag: the reconciliation test will surface any rate drift between surfaces. A shared rates file is a candidate refactor.
3. `flag_arm` grouping requires the flags spec's SpendEvent fields; until then the dimension returns 400 with a clear message ("requires flags feature") rather than an empty result.
