# Workstream A — Compression-Quality Data Flywheel

**Moat type:** Learning / data network effect (the only durable *technical* moat).
**Thesis:** We sit in the one place where ground-truth labels for compression quality are produced for free. A `headroom_retrieve` call is a label that says *"the compressor dropped something the agent needed."* Task success with no retrieval says *"that compression was safe."* Capture those labels, turn them into a training corpus, and continuously fine-tune a keep/drop model on **real agent content**. The code is copyable; the corpus our traffic generates is not. Quality compounds with usage; a new entrant starts at zero.

**What already exists (build on, don't rebuild):**
- `headroom/telemetry/toin.py` — Tool Output Intelligence Network. Observation-only. Records compression + retrieval events, aggregates by `(auth_mode, model_family, structure_hash)`, supports `import_patterns` (federated seed), emits `recommendations.toml` via `python -m headroom.cli.toin_publish`.
- `headroom/telemetry/models.py` — `FieldDistribution`, `FieldSemantics`, `ToolSignature`, `ToolPattern` — **patterns, never values**.
- `headroom/telemetry/{beacon.py,collector.py,reporter.py}` and `backends/{base.py,filesystem.py}` — collection plumbing, filesystem-only today.
- `headroom/ccr/{context_tracker.py,response_handler.py,batch_store.py}` — stores originals + records retrievals. **This is where the label is born.**
- `headroom/evals/{suite_runner.py,metrics.py,datasets.py,cost_tracker.py}` — eval harness for gating model quality.
- `crates/headroom-core/src/signals/{line_importance.rs,tiered.rs,keyword_detector.rs}` and `crates/headroom-core/src/relevance/{hybrid.rs,embedding.rs,bm25.rs}` — the **keep/drop scorer** that today uses static heuristics. This is exactly what the labels will train.
- `headroom/models/{ml_models.py,registry.py,config.py}` — model loading/registry.

**The gap (what turns observation into a moat):**
1. The retrieval signal is recorded but **never used as a training label**.
2. There is **no task-outcome signal** (did the run succeed?).
3. Aggregation is **filesystem-only** — no hosted corpus, no differential privacy, no k-anonymity gate.
4. There is **no training loop** that consumes labels → fine-tunes a keep/drop model on agent content.
5. There is **no model-rollout gate** (eval + shadow retrieval-rate) and **no per-slice specialization**.
6. The best model is **open on HF** — foreclosing the moat. We need a proprietary agent-tuned channel.

---

## Dependency graph

```
A1 (episode store) ─┬─> A2 (outcome signal) ─┬─> A3 (label builder) ──> A5 (training) ──> A6 (rollout gate)
                    │                         │                                              │
                    └─> A4 (DP egress) ───────┴─> A7 (hosted insight svc) ──────────────────┘
                                                  (A7 depends on C-control-plane auth)
A6 ──> A8 (Rust learned-scorer load path)
```
A1 first. A2/A4 parallel after A1. A3 after A2. A5 after A3. A6 after A5. A7 after A4 + control-plane C1. A8 after A6.

---

## PR-A1 — On-device Compression Episode store

**Branch:** `moat-A1-episode-store`
**Risk:** LOW (new module, additive, default-on but local-only)
**Depends on:** none

### Scope
Introduce a first-class, local, append-only record that links a compression decision to its later retrievals and outcome. This is the atomic training unit. **Local-only in this PR — nothing leaves the machine.**

### Data model
New `headroom/telemetry/episodes.py`:

```python
@dataclass
class CompressionEpisode:
    episode_id: str            # uuid4
    session_id: str | None     # ties to learn/memory session
    sig_hash: str              # tool/structure hash (reuse ToolSignature)
    auth_mode: str             # "payg" | "oauth" | "subscription" | "unknown"
    model_family: str          # "claude-3-5" | "gpt-4o" | ...
    strategy: str              # "smart_crusher" | "code" | "kompress" | ...
    original_tokens: int
    compressed_tokens: int
    # keep/drop decision as offset spans over the ORIGINAL text — NOT the text itself
    kept_spans: list[tuple[int, int]]
    dropped_spans: list[tuple[int, int]]
    content_fingerprint: str   # sha256 of original; key into CCR batch_store
    created_at: float

@dataclass
class RetrievalLabel:
    episode_id: str
    retrieved: bool
    retrieval_type: str | None      # "full" | "span" | "field"
    retrieved_span_ids: list[int]   # indices into dropped_spans that got pulled back
    seconds_to_retrieval: float | None
    created_at: float
```

Storage: SQLite at `~/.headroom/episodes.db` (WAL mode, mirrors `headroom/org.py` pattern). Tables `episodes`, `retrieval_labels`. Retention: configurable, default 30 days, pruned by `headroom/retention.py`.

### Files
**Add:**
- `headroom/telemetry/episodes.py` — dataclasses + `EpisodeStore` (`open()`, `record_episode()`, `record_retrieval()`, `iter_unlabeled(older_than)`, `prune()`).
- `headroom/telemetry/tests/test_episodes.py`.

**Modify:**
- `headroom/ccr/response_handler.py` — when a compression is emitted, call `EpisodeStore.record_episode(...)` with the keep/drop spans already computed there. **Span offsets only — never copy payload text into the episode.**
- `headroom/ccr/context_tracker.py` — when `headroom_retrieve` fires, resolve `content_fingerprint → episode_id` and call `record_retrieval(...)`.
- `headroom/config.py` — add `episodes_enabled: bool = True`, `episodes_db_path`, `episodes_retention_days: int = 30`.

### Acceptance criteria
- A compress→retrieve round trip produces exactly one `CompressionEpisode` and one `RetrievalLabel` linked by `episode_id`.
- A compress with no retrieval after the session closes produces an episode with no retrieval row.
- **No raw payload bytes are stored in `episodes.db`** — assert via a test that writes a known sentinel string into a payload and greps the DB file for it (must be absent).
- `pytest headroom/telemetry/tests/test_episodes.py` green; `make ci-precheck` green.

### Tests
- `test_episode_records_spans_not_text`
- `test_retrieval_links_to_episode`
- `test_no_retrieval_episode_persists`
- `test_db_contains_no_raw_payload` (sentinel grep)

---

## PR-A2 — Task-outcome signal

**Branch:** `moat-A2-outcome-signal`
**Risk:** LOW–MEDIUM (heuristic detectors; additive)
**Depends on:** A1

### Scope
Attach a coarse success/fail/unknown label to a session so episodes inherit an outcome. Without this the only label is "retrieved/not," which conflates "compressed badly" with "agent didn't need it anyway."

### Outcome sources (in priority order)
1. **Test/exit signal** — agent wrappers already shell out; capture process exit code + presence of a passing test run (`headroom/learn/scanner.py` already parses session events). Map exit 0 + tests-green → `success`.
2. **User-accept signal** — for coding agents, a diff accepted/committed within the session → `success`; reverted → `fail`.
3. **Agent-continue signal** — the agent proceeded N more turns without re-requesting the same tool output → weak `success`.
4. Default `unknown` (excluded from training labels but kept for analysis).

### Data model
New `headroom/telemetry/outcome.py`:
```python
@dataclass
class OutcomeLabel:
    session_id: str
    outcome: str          # "success" | "fail" | "unknown"
    source: str           # "test_exit" | "user_accept" | "agent_continue"
    confidence: float     # 0..1
    created_at: float
```
Stored in `episodes.db` table `outcome_labels`, joined to episodes by `session_id`.

### Files
**Add:** `headroom/telemetry/outcome.py`, `headroom/telemetry/tests/test_outcome.py`.
**Modify:**
- `headroom/learn/scanner.py` — expose parsed session terminal events to an `OutcomeDetector` callback (do not duplicate parsing).
- `headroom/telemetry/episodes.py` — `attach_outcome(session_id, OutcomeLabel)`; `iter_labeled_episodes()` now joins retrieval + outcome.

### Acceptance criteria
- A session ending in a green test run yields `OutcomeLabel(success, test_exit, ≥0.8)`.
- A reverted change yields `fail`.
- Sessions with no signal yield `unknown` and are excluded by `iter_labeled_episodes(min_confidence=…)`.
- Tests green; `make ci-precheck` green.

---

## PR-A3 — Label builder (episodes → training examples)

**Branch:** `moat-A3-label-builder`
**Risk:** MEDIUM (defines the learning target)
**Depends on:** A2

### Scope
Convert labeled episodes into supervised training examples for a **keep/drop span classifier** — the model that will replace static heuristics in `crates/headroom-core/src/signals/line_importance.rs`.

### Label semantics
For each dropped span `s` in an episode:
- `label(s) = SAFE_TO_DROP` if `s` was **not** retrieved AND session outcome ∈ {success, unknown-high} .
- `label(s) = SHOULD_KEEP` if `s` **was** retrieved (hard negative — we dropped something needed) OR outcome == fail and the agent retrieved.
Kept spans that correlate with success are positive "keep was correct" examples (weaker weight).

Training example schema (`headroom/training/schema.py`):
```python
@dataclass
class KeepDropExample:
    sig_hash: str
    auth_mode: str
    model_family: str
    span_features: list[dict]   # per-span: length, position, entropy, field_semantic, bm25_to_query, ...
    labels: list[int]           # 0=safe_to_drop, 1=should_keep, aligned to span_features
    weight: float               # from outcome confidence
```
Features are computed from the **original payload pulled from CCR `batch_store`** at build time (offline, on-device or in the insight service) — so the raw text is used transiently to compute features and is not persisted beyond the configured CCR retention.

### Files
**Add:** `headroom/training/__init__.py`, `headroom/training/schema.py`, `headroom/training/label_builder.py`, `headroom/training/tests/test_label_builder.py`.

### Acceptance criteria
- A retrieved dropped-span produces a `SHOULD_KEEP` example; a never-retrieved dropped-span under success produces `SAFE_TO_DROP`.
- Example weights track outcome confidence.
- Builder is deterministic given a fixed episode set (golden-file test).

---

## PR-A4 — Privacy-preserving egress (DP + k-anonymity), opt-in

**Branch:** `moat-A4-dp-egress`
**Risk:** HIGH (this is the local-first/brand boundary — privacy is a test)
**Depends on:** A1

### Scope
Allow **opt-in** export of *patterns and label statistics only* — never values — to a hosted aggregator, with differential privacy and k-anonymity. Default OFF.

### What may leave vs never
| May leave (opt-in) | Never leaves |
|--------------------|--------------|
| `sig_hash`, `auth_mode`, `model_family` | tool names, file paths, queries |
| span **features** (length, entropy bucket, position, field-semantic class) | span **text** / payload bytes |
| keep/drop label + outcome class + weight | user identifiers (replaced by salted org pseudonym) |
| aggregate counts per pattern | per-event raw timestamps (bucketed to day) |

### Mechanics
- New `headroom/telemetry/dp.py` — Laplace/Gaussian mechanism; per-org epsilon budget per period (default ε=1.0/week, configurable); clip + noise counts before egress.
- **k-anonymity gate:** the hosted service only *admits a pattern into the corpus* if it has been observed from `≥ k` distinct org pseudonyms (default k=5). Implemented server-side (A7) but the client tags contributions with a salted org pseudonym (HMAC(org_id, server_salt)).
- New `headroom/telemetry/backends/https_beacon.py` — batched, signed upload to the insight service; respects `Retry-After`; offline-safe queue; uses the control-plane license token (C1) for auth.
- Federated mode: when `HEADROOM_FEDERATED=1`, export only aggregated `ToolPattern` deltas (extend existing `toin.import_patterns`/export), never per-episode rows — for air-gapped/regulated orgs.

### Files
**Add:** `headroom/telemetry/dp.py`, `headroom/telemetry/backends/https_beacon.py`, `headroom/telemetry/tests/test_dp.py`, `headroom/telemetry/tests/test_egress_privacy.py`.
**Modify:** `headroom/telemetry/beacon.py` (wire opt-in + notice text already scaffolded via `format_telemetry_notice`), `headroom/config.py` (`telemetry_egress_enabled=False`, `dp_epsilon`, `k_anon_min`, `insight_url`).

### Acceptance criteria
- **Privacy test is blocking:** `test_egress_privacy` feeds payloads containing sentinel secrets and asserts the serialized upload contains none of them, no tool names, no paths, no raw query strings.
- DP noise is applied (count distributions shift within expected bounds; ε budget enforced and exhaustion halts egress).
- With `telemetry_egress_enabled=False` (default), `https_beacon` makes **zero** network calls (assert with a mock transport).
- Federated mode exports only aggregate deltas.

---

## PR-A5 — Training pipeline + agent-tuned model

**Branch:** `moat-A5-train-keepdrop`
**Risk:** MEDIUM–HIGH (ML; gated by eval in A6)
**Depends on:** A3 (+ corpus from A7 for the hosted variant)

### Scope
Train a per-slice keep/drop scorer (and, phase 2, a generative `kompress-agent` head) on the labeled corpus, export to ONNX (matches the existing weight-only int8 ONNX path for `kompress-v2-base`), and register it.

### Model
- **Phase 1 (highest ROI):** a lightweight span-classification head over existing relevance features (`crates/headroom-core/src/relevance/*`) — a learned replacement for `line_importance.rs` heuristics. Small, fast, CPU/ONNX, trainable from thousands of examples.
- **Phase 2:** fine-tune `kompress-v2-base` on agent content (tool outputs, logs, diffs) using the same labels as a reward/selection signal → `kompress-agent-base`. This is the proprietary artifact.
- Per-slice specialization: train separate heads per `(auth_mode, model_family)` where data volume supports it; fall back to a global head otherwise.

### Files
**Add:**
- `headroom/training/dataset.py` — `KeepDropExample` → tensors; train/val/test split by org pseudonym (no leakage across split).
- `headroom/training/train_keepdrop.py` — HF `Trainer` or torch loop; emits ONNX int8 + metadata card (`model_family`, `auth_mode`, `data_version`, metrics).
- `headroom/training/export_onnx.py`.
- `headroom/training/tests/test_train_smoke.py` (tiny synthetic set, 1 epoch, asserts artifact emitted).

### Acceptance criteria
- Smoke train on synthetic data produces a loadable ONNX artifact + metadata card.
- Train/val/test split is by org pseudonym (test asserts no pseudonym appears in two splits).
- Artifact is content-addressed and signed (key from C1).

---

## PR-A6 — Rollout gate (eval + shadow retrieval-rate) + model registry channel

**Branch:** `moat-A6-rollout-gate`
**Risk:** MEDIUM
**Depends on:** A5

### Scope
No model ships unless it (1) beats the incumbent on the offline eval suite and (2) lowers retrieval rate on **shadow** traffic with no quality regression. Add a proprietary, entitlement-gated model channel.

### Mechanics
- Extend `headroom/evals/suite_runner.py` with a `keepdrop_eval` that scores a candidate vs incumbent on held-out labeled episodes (precision of "safe_to_drop," recall of "should_keep," token-savings @ fixed retrieval budget).
- **Shadow mode:** candidate runs alongside production in the proxy, its keep/drop decisions logged but not applied; compare predicted retrieval rate vs actual incumbent retrieval rate. Promote only if shadow retrieval-rate ≤ incumbent AND token-savings ≥ incumbent.
- `headroom/models/registry.py` — add channel `agent-tuned`, signature verification (reject unsigned), and **entitlement gate**: `kompress-agent-*` requires Team+ license (ties to C1). `kompress-v2-base` stays open/ungated.

### Files
**Modify:** `headroom/evals/suite_runner.py`, `headroom/models/registry.py`, `headroom/models/config.py`.
**Add:** `headroom/evals/runners/keepdrop_eval.py`, `headroom/training/tests/test_rollout_gate.py`.

### Acceptance criteria
- A candidate that regresses recall-of-should-keep is **rejected** by the gate.
- An unsigned artifact is rejected by the registry.
- `kompress-agent-*` refuses to load without a valid Team+ entitlement; `kompress-v2-base` loads ungated.

---

## PR-A7 — Hosted Insight service (corpus + k-anonymity)

**Branch:** `moat-A7-insight-svc`
**Risk:** HIGH (new service; the data asset lives here)
**Depends on:** A4 + control-plane C1 (auth)

### Scope
The server that ingests DP-noised opt-in contributions, enforces k-anonymity, dedups, and assembles the versioned training corpus. **This is where the moat physically accrues.** Co-locate with the control plane (C7) for one auth surface.

### Endpoints (add to `artifacts/openapi-management.yaml`)
- `POST /v1/insight/contributions` — batched pattern/label stats; auth via license token; rejects anything failing the no-values schema; tags with salted org pseudonym.
- `GET /v1/insight/corpus/{version}` — internal, signed, for the training job.
- `GET /v1/insight/stats` — admin: pattern coverage, #orgs per pattern (k), ε spend per org.

### Mechanics
- Server-side **k-anonymity admission**: a pattern enters the trainable corpus only at `≥k` distinct pseudonyms.
- Dedup + aggregate into `ToolPattern` rollups (reuse the model from `headroom/telemetry/models.py`).
- Corpus is content-addressed + versioned; training (A5) pulls a pinned version.

### Files
**Add:** `services/insight/` (FastAPI app, models, k-anon admission, corpus builder), `services/insight/tests/`.
**Modify:** `artifacts/openapi-management.yaml` (add insight paths + schemas).

### Acceptance criteria
- A contribution failing the no-values schema is rejected with 422 (test).
- A pattern below k is excluded from `corpus/{version}` (test).
- ε budget per pseudonym enforced; over-budget contributions dropped + logged.

---

## PR-A8 — Rust learned-scorer load path

**Branch:** `moat-A8-rust-learned-scorer`
**Risk:** MEDIUM (touches hot path; must stay deterministic)
**Depends on:** A6

### Scope
Let the Rust core load the promoted keep/drop model at **startup** and use it in place of static heuristics, preserving determinism (no in-request learning, per the TOIN contract).

### Files
**Add:** `crates/headroom-core/src/signals/learned_scorer.rs` — loads ONNX artifact (path from registry/config), scores spans; falls back to `line_importance.rs` heuristics if absent.
**Modify:**
- `crates/headroom-core/src/signals/mod.rs` — dispatch to learned scorer when configured.
- `crates/headroom-core/src/signals/tiered.rs` — accept learned scores as a tier input.
- `crates/headroom-proxy/src/config.rs` — `--keepdrop-model <path>` / `HEADROOM_KEEPDROP_MODEL`.

### Acceptance criteria
- With no model configured, behavior is byte-identical to today (regression test vs golden fixtures).
- With a model configured, the same input always yields the same output (determinism test, 100 runs).
- `cargo test -p headroom-core` green; cache-safety SHA-256 passthrough tests from Phase A still green.

---

## Definition of done (Workstream A)
- A closed loop runs end to end on **one design partner**: episodes captured → labels built → corpus (k≥5) → `kompress-agent` trained → eval+shadow gate passed → promoted → Rust loads it.
- The agent-tuned model is **proprietary and entitlement-gated**; `kompress-v2-base` remains open.
- Every egress path has a green blocking privacy test.
- **Kill check:** if, across ≥10 active orgs, the agent-tuned model can't beat `kompress-v2-base` on held-out eval AND cut live retrieval rate, stop — A is not a moat for us; double down on B + C + D.
