# Workstream B — Switching Costs via Co-Created Team Memory

**Moat type:** Switching costs (most realistic; buildable now with no new ML).
**Thesis:** `headroom learn` + cross-agent memory already accumulate a team's corrections and institutional knowledge. Today that knowledge is local, per-user, unscored, and removable without consequence — so it creates no lock-in. Make it **team-shared**, **value-scored against real outcomes**, and **load-bearing** (agents measurably do worse without it). Then leaving Headroom means abandoning an asset the team co-created over months that cannot be re-imported into a competitor. Keep raw memories exportable (trust); make the **intelligence layer** (value model, dedup graph, curation, cross-agent linkage) the thing that's lost on exit.

**What already exists (build on, don't rebuild):**
- `headroom/memory/store.py` — file-based episodic memory (`~/.headroom/memories/{project_hash}.md`), append-only, user-editable.
- `headroom/memory/models.py` — `Memory` with hierarchical scope (`USER/SESSION/AGENT/TURN`), supersession (`supersedes`/`superseded_by`/`promoted_from`), `importance`, `access_count`, `embedding`, `entity_refs`.
- `headroom/memory/{core.py,system.py,sync.py,storage_router.py,qdrant_env.py,extractor.py,traffic_learner.py,mcp_server.py}` — extraction, vector backends, sync scaffold.
- `headroom/proxy/{memory_injection.py,memory_ranker.py,memory_query.py,memory_decision.py}` — inject memory into live requests.
- `headroom/learn/{scanner.py,analyzer.py,writer.py}` — LLM mines sessions → recommendations → writes to `CLAUDE.md`/`AGENTS.md` between markers (`<!-- headroom:learn:start -->`).
- `headroom/org.py` — `Organization > Workspace > Project > Agent` SQLite hierarchy.
- `headroom/rbac.py`, `headroom/audit.py` — access control + audit primitives (Enterprise).

**The gap (what turns a junk drawer into a moat):**
1. Memory is **local/per-user** — no team server of record, no shared namespace, no conflict resolution.
2. **No provenance** (who/what/when created a memory) and **no value scoring** tied to outcomes — so memory quality decays into noise.
3. **Not load-bearing** — agents perform the same without it, so there is nothing to lose by leaving.
4. **Portability is symmetric** — markdown exports out cleanly (good for trust), but we expose nothing that makes the *intelligence layer* the sticky asset.
5. **No curation/governance workflow** — review, promote, deprecate, ownership.

---

## Dependency graph

```
B1 (team memory service) ──> B2 (provenance + value) ──> B3 (load-bearing injection + impact)
        │                          │                              │
        └──> B4 (curation/governance) <───────────────────────────┘
B2 ──> B5 (portability policy)      B3 ──> B6 (value dashboard)
```
B1 first (depends on control-plane C1 auth + C4 org/tenant tables). B2 after B1. B3 after B2. B4/B5/B6 after their edges.

---

## PR-B1 — Team Memory Service (server of record)

**Branch:** `moat-B1-team-memory-svc`
**Risk:** MEDIUM–HIGH (new multi-tenant server; sync correctness)
**Depends on:** control-plane C1 (license/auth) + C4 (org/tenant store)

### Scope
A multi-tenant memory store keyed by the existing `Organization > Workspace > Project` hierarchy, with a client↔server delta-sync protocol. Local store stays as the offline cache; the server is the shared source of truth across a team.

### Sync protocol
- Client maintains a per-scope **vector clock** / `updated_at` watermark.
- `POST /v1/memory/sync` with `{since_watermark, local_deltas[]}` → returns `{server_deltas[], new_watermark}`.
- Conflict resolution: reuse `Memory.supersedes`/`superseded_by`. Concurrent edits → both retained, newer marked current, older `superseded_by` newer (no destructive overwrite). Tombstones for deletes.
- Scope mapping: `Memory.user_id` → org pseudonym; `session_id`/`agent_id` preserved; new `workspace_id`/`project_id` fields added to `Memory`.

### Files
**Add:**
- `services/memory/` (FastAPI) — `app.py`, `models.py` (server-side `Memory` + tenant keys), `sync.py` (delta merge), `tests/`.
- `headroom/memory/tests/test_team_sync.py`.
**Modify:**
- `headroom/memory/models.py` — add `workspace_id`, `project_id`, `provenance` (see B2), `value_score` (see B2).
- `headroom/memory/sync.py` — implement client side of the protocol (push/pull deltas, watermark, offline queue).
- `headroom/memory/storage_router.py` — route reads/writes through the team service when configured, fall back to local.
- `artifacts/openapi-management.yaml` — add `/v1/memory/sync`, `/v1/memory/query`.
- `headroom/config.py` — `memory_team_sync_enabled: bool = False`, `memory_service_url`.

### Acceptance criteria
- Two clients in the same project converge after sync (integration test with two in-memory clients).
- Concurrent edits to the same memory produce a supersession chain, never a lost write.
- Tenant isolation: a client authed to org A cannot read org B memories (authz test).
- Default off → zero network calls (mock-transport test).

---

## PR-B2 — Provenance + outcome-linked value scoring

**Branch:** `moat-B2-memory-value`
**Risk:** MEDIUM (defines what makes memory "good")
**Depends on:** B1 (+ outcome signal from `01` PR-A2)

### Scope
Every memory carries provenance and a value score that rises when the memory is cited before successful turns and decays when unused or superseded. This is what keeps the asset high-signal and ties B to A's outcome signal.

### Data model (extend `Memory`)
```python
@dataclass
class Provenance:
    created_by_session: str | None
    created_by_agent: str | None
    source: str               # "learn" | "manual" | "extracted" | "imported"
    commit_sha: str | None    # if created during a coding session
    created_at: float

# added to Memory:
provenance: Provenance
value_score: float            # EWMA, 0..1
citations: list[str]          # episode_ids/turn_ids where this memory was injected
outcome_links: list[str]      # outcome_label ids correlated with those citations
last_value_update: float
```

### Value update rule
- On injection, record a citation linking memory → turn/episode.
- When that turn's `OutcomeLabel` (from `01`/A2) resolves: `value_score = EWMA(value_score, reward)`, where `reward = +1 success / 0 unknown / −0.5 fail`, decayed by recency.
- Periodic decay for memories never cited; auto-deprecate below a floor (move to `superseded`/archived, not deleted).

### Files
**Add:** `headroom/memory/value.py` (`ValueModel`: `on_injection()`, `on_outcome()`, `decay()`), `headroom/memory/tests/test_value.py`.
**Modify:** `headroom/memory/models.py` (`Provenance`, value fields), `headroom/learn/writer.py` (stamp provenance on learned memories), `headroom/memory/extractor.py` (stamp provenance on extracted memories).

### Acceptance criteria
- A memory cited before repeated successes rises toward 1.0; an uncited memory decays below the floor and is auto-archived.
- Provenance is stamped on every newly created memory (test for all four sources).
- Value updates are idempotent per outcome (no double-counting).

---

## PR-B3 — Load-bearing injection + measured impact

**Branch:** `moat-B3-memory-impact`
**Risk:** MEDIUM (touches live injection; must stay deterministic per TOIN contract)
**Depends on:** B2

### Scope
Rank injected memory by **value_score**, and **measure** the outcome/cost lift from injection so we can prove (and the customer can see) that memory is load-bearing. The measurement is the lock-in proof: if removing accumulated memory visibly raises cost and lowers success, the team won't remove it.

### Mechanics
- `headroom/proxy/memory_ranker.py` — rank by `value_score × relevance` (relevance already computed); cap by `memory/budget.py`.
- **Impact measurement (offline/shadow, never mutates a live decision):** periodically run matched-pair comparisons — same/similar sessions with vs without memory injection — and compute deltas in success rate and tokens. Reuse `headroom/evals/` for the harness; attribute `$ saved via memory`.
- Surface `memory_impact` metrics through `headroom/observability/` → dashboard (B6).

### Files
**Modify:** `headroom/proxy/memory_ranker.py`, `headroom/proxy/memory_injection.py` (emit citation events to B2), `headroom/evals/runners/` (add `memory_impact_runner.py`), `headroom/observability/` (new `memory_impact` metric).
**Add:** `headroom/memory/tests/test_impact.py`.

### Acceptance criteria
- Injection order is value-weighted and within budget (test).
- Impact runner produces a success-rate delta and token delta on a labeled fixture set.
- Injection remains deterministic for a fixed memory set + request (determinism test) — no in-request value mutation.

---

## PR-B4 — Team curation & governance

**Branch:** `moat-B4-curation`
**Risk:** LOW–MEDIUM
**Depends on:** B1, B3

### Scope
A review workflow that turns raw memories into curated org knowledge: promote/deprecate, ownership, review queue, full audit. Curated knowledge is the durable asset.

### Mechanics
- States: `proposed → approved → deprecated/archived` (extend supersession).
- New low-value or learn-generated memories enter `proposed`; reviewers (RBAC role `memory_curator`) approve/reject; approved memories get a value floor + are eligible for cross-project promotion.
- Every state change writes to `headroom/audit.py` (hash-chained per `03`/C6).

### Files
**Add:** `headroom/memory/curation.py`, endpoints in `services/memory/app.py` (`/v1/memory/{id}/review`), `headroom/memory/tests/test_curation.py`.
**Modify:** `headroom/rbac.py` (add `memory_curator` role + perms), `headroom/audit.py` (curation events).

### Acceptance criteria
- A non-curator cannot approve (authz test).
- Approve/deprecate transitions are audited (chain verifies).
- Promotion across projects within a workspace works and is scoped (no cross-org leakage).

---

## PR-B5 — Portability policy (deliberate asymmetry)

**Branch:** `moat-B5-portability`
**Risk:** LOW (mostly policy + export tooling)
**Depends on:** B2

### Scope
Make the trust/lock-in tradeoff explicit and shippable: **raw memories export freely** (markdown/JSON — preserves the "user-editable, no lock-in" promise); the **intelligence layer does not export** (value model, dedup/promotion graph edges, embeddings index, curation state, cross-agent linkage). Document this so it's an intentional product decision, not a hidden trap.

### Files
**Add:** `headroom/memory/export.py` (`export_raw()` → portable bundle; explicitly **excludes** `value_score`, graph edges, embeddings, curation history), `docs/memory-portability.md`, `headroom/memory/tests/test_export.py`.

### Acceptance criteria
- `export_raw()` round-trips memory **content + provenance** but omits intelligence-layer fields (test asserts exclusion).
- Docs state clearly what is and isn't portable.

---

## PR-B6 — Memory value dashboard

**Branch:** `moat-B6-value-dashboard`
**Risk:** LOW
**Depends on:** B3

### Scope
Make the accumulated asset **visible**: total memories, curated knowledge count, `$ saved attributable to memory`, success-rate lift, top memories by value, growth over time. Visibility raises switching cost both practically and psychologically.

### Files
**Modify:** `headroom/dashboard/` (new "Team Memory" view), `headroom/reporting/` (exportable memory-value report), consume `memory_impact` metric from B3.
**Add:** `headroom/dashboard/tests/test_memory_view.py`.

### Acceptance criteria
- Dashboard renders accumulated value, $-saved, and lift from real metrics (not placeholders).
- Report exports (CSV/PDF) for QBRs.

---

## Definition of done (Workstream B)
- A team's memory syncs across members through the service, scoped by org/workspace/project.
- Every memory has provenance + an outcome-linked value score; low-value memory auto-archives.
- The dashboard shows a **measured** success-rate lift and $-saved from injected memory (the load-bearing proof).
- Raw memories export freely; the intelligence layer stays server-side.
- **Kill check:** if the impact runner can't show a positive, stable lift from injected memory, memory is not load-bearing — stop adding memory features and treat memory as a convenience, not a moat.
