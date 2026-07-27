# Meta-Harness Orchestrator Parity Design

**Date:** 2026-07-28  
**Status:** Draft — design + gap analysis only (no production code in this pass)  
**Reference:** [Meta-Harness | Designing Multi-Agent AI Systems](https://www.youtube.com/watch?v=HRUBDPdvaHU) (The Carbon Layer)  
**Branch:** `feat/aie-commercial-capability-integration`  
**Related:** `2026-07-13-universal-orchestration-implementation-plan.md`, `2026-07-27-aie-commercial-capability-integration-design.md`

---

## 1. Executive summary

Cutctx already ships a **deterministic model-routing control plane** with durable DAG workflows, role bindings, contracts, receipts, and a static harness compatibility manifest. Carbon Layer’s meta-harness targets a **different primary layer**: versioned agent packages, heterogeneous harness execution (Carbon SDK, Codex CLI, ACP), credential-isolated sandboxes, provenance-graph artifact storage, and a live event/control plane.

**Honest verdict:** **Partial parity only** without becoming a different product. Cutctx can realistically own the **context + policy + evidence substrate** under each worker and extend workflows to invoke harness adapters — but should not compete with Omnigent/Carbon on collaboration UI, OS sandboxing, or full harness runtimes.

**Recommended path:** **Option B** — a thin meta-harness coordination layer on top of existing `cutctx/orchestration/` plus Cutctx’s compression, memory, and receipt stack.

---

## 2. What Cutctx has today

### 2.1 Architecture (as implemented)

```text
Request (proxy / admin API)
  → Layered config (global → project)
  → Workload contracts (draft → shadow → canary → active)
  → Deterministic routing engine (roles, selectors, capabilities)
  → Provider adapters (LiteLLM-backed model transport)
  → Execution telemetry + outcome signals + receipt audit chain
  → Optional durable workflow DAG (task leases, approval/verification gates)
```

**Primary code:** `cutctx/orchestration/` (engine, workflow, service, contracts, policy_bundle, harnesses, scheduler, audit, credentials, telemetry).  
**Surfaces:** `cutctx/proxy/routes/orchestration.py`, dashboard `Orchestrator.jsx` + `OrchestrationStudio.jsx`, docs `orchestration-platform.mdx`.

### 2.2 Component inventory

| Concern | Today | Maturity |
|---|---|---|
| **Workflow engine** | `WorkflowRunner` + `WorkflowStateStore` — acyclic DAG, bounded concurrency, leases, retries, approval/verification gates | Foundation; executes **LLM calls** via `OrchestrationService.execute`, not harness subprocesses |
| **Role binding** | Data-defined roles + selector precedence (`agent`, `workflow`, `skill`, `repository`, …) | Production |
| **Lifecycle** | Contract lifecycle (draft/shadow/canary/active/paused/retired); workflow task state machine | Production for contracts; workflow gates partial |
| **Adapters** | **Provider** adapters (OpenAI, Anthropic, … via LiteLLM); **harness** manifest is static compatibility metadata only | Model transport strong; harness execution absent |
| **Artifact store** | `TaskArtifact` schema (patch/test/review refs, provenance dict); no blob store or provenance graph | Schema only |
| **Event plane** | Append-only execution/outcome JSONL; receipt audit chain; no live session/control WebSocket for multi-agent ops | Telemetry, not control |
| **Policy binder** | Policy bundles (Ed25519), routing constraints, enterprise firewall/audit (EE) | Strong for **model** policy; weak for **tool/action** policy |
| **Credentials** | Fernet-encrypted local store + `ExternalSecretResolver` protocol | Account-scoped model keys; no per-worker env isolation |
| **Worker lifecycle** | Per-task `max_attempts`, `timeout_seconds`, contract `ReliabilityBudget`; scheduler is **recommendation_only** | Model-attempt budgets; no workflow cost ceiling enforcement |
| **Agent packages** | None — roles/bindings are routing config, not versioned agent definitions | Missing |

### 2.3 Explicit non-goals already documented

From `universal-orchestration-implementation-plan.md` and AIE commercial design:

- No replacement editor or universal agent UI
- No permission OS / full security suite
- No graph memory as core product
- No unbounded autonomous multi-agent execution
- Temporal integration only behind a future `WorkflowRuntime` boundary

---

## 3. Carbon Layer meta-harness target (verified)

Source: Carbon Layer talk + Omnigent/Databricks public architecture (runner + server + policies).

| # | Component | Carbon target behavior |
|---|---|---|
| 1 | **Agent Package Registry** | Versioned, reproducible worker configs (prompt, tools, model prefs, policies); pin exact package hash per workflow run |
| 2 | **Harness Adapter Layer** | Uniform worker contract over Carbon SDK, Codex CLI, ACP/HTTP; capability descriptors (stream, cancel, resume, artifact emit) |
| 3 | **Role & Policy Binder** | Least-privilege per role: allowed tools, paths, network, credentials |
| 4 | **Workflow Engine** | Deterministic control flow in code — **not** a supervisor LLM carrying process state |
| 5 | **Worker Lifecycle Manager** | Max duration, attempts, **cost**, revision rounds; failure containment |
| 6 | **Execution Environment Manager** | Credential isolation (reviewer read-only, implementer no merge token); optional cloud sandbox |
| 7 | **State & Artifact Store** | Provenance graph linking commits, patches, tests, reviews; durable reuse after worker crash |
| 8 | **Event & Control Plane** | Cancel, pause, approve, inspect artifacts; human gates; live observability |

**Core thesis:** Meta-harness coordinates *who runs when* across heterogeneous harnesses. Context isolation is a **boundary** problem (pass artifacts, not transcripts). Supervisor-in-context designs fail at scale.

---

## 4. Gap analysis

| Component | Cutctx today | Carbon target | Gap severity | Build / Partner / Package |
|---|---|---|---|---|
| Agent Package Registry | Roles/bindings/contracts (routing intent) | Versioned agent packages with tools + policies | **High** | **Build** thin YAML registry; optionally **package** Omnigent agent YAML import |
| Harness Adapter Layer | Static `compatibility_manifest()` | Runnable adapters for Carbon/Codex/ACP | **Critical** | **Build** adapter interface + 2 adapters; **partner** Omnigent runner for advanced cases |
| Role & Policy Binder | Model routing + EE firewall | Per-worker tool/path/credential policy | **High** | **Build** extend `TaskArtifact` + contract requirements; **package** EE entitlements |
| Workflow Engine | DAG + gates; LLM-only execution | DAG driving real harness workers | **Medium** | **Build** plug `HarnessAdapter.run()` into `WorkflowRunner.execute` |
| Worker Lifecycle Manager | Task timeout/retries; contract budgets for model calls | Cost/duration/revision caps per worker | **Medium** | **Build** workflow-level budgets + savings ledger join |
| Execution Environment Manager | Encrypted credential store per account | Per-worker sandbox + cred brokering | **Critical** | **Partner** Modal/Daytona/Omnigent sandbox; **Build** minimal subprocess env isolation |
| State & Artifact Store | `TaskArtifact` refs; CCR/memory elsewhere | Provenance graph + blob store | **High** | **Build** artifact blob store + lineage edges; reuse CCR hashes |
| Event & Control Plane | Admin APIs + JSONL telemetry | Live cancel/approve/inspect | **High** | **Build** session registry MVP (see `audit/remote-agent-orchestration-exploration.md`); defer collab UI |

---

## 5. Options

### Option A — Extend orchestrator to full meta-harness parity (3–6 months)

Phased build of all eight components in-process: agent registry, harness runners, sandbox manager, provenance graph, control server, collaboration surfaces.

**Pros:** Single-vendor story; deepest integration with compression/receipts.  
**Cons:** Becomes Omnigent/Carbon competitor; violates AIE scope discipline; high build + ops burden (sandboxes, session server, multi-harness semantics).

### Option B — Thin meta-harness layer on Cutctx orchestration + context plane (recommended)

Add a **`HarnessRuntime`** boundary above `WorkflowRunner` that:

1. Resolves agent packages → harness adapter + role policy
2. Invokes workers with isolated env + explicit artifact handoffs
3. Compresses/stores handoffs via CCR + artifact store
4. Emits decision receipts + execution events to control plane
5. Keeps model routing in existing `DeterministicRoutingEngine`

**Pros:** Preserves Cutctx identity (context control plane); reuses 70% of orchestration code; dual-path friendly (local JSON store + optional Redis/EE).  
**Cons:** Partial parity on sandbox/collaboration unless partnered.

### Option C — Partner / integrate Carbon or Omnigent; Cutctx stays substrate

Cutctx provides: proxy, compression, memory, receipts, buyer report, model routing. Partner provides: harness runners, sandbox, collaboration, agent YAML.

**Pros:** Fastest to “as good as” for harness composition; lowest product risk.  
**Cons:** Not a differentiated orchestrator SKU; dependency on partner roadmap/licensing.

### Recommendation: **Option B**, with **Option C** for sandbox + collaboration

**Rationale:**

- Cutctx’s moat is **context efficiency + attributable governance**, not agent UX or OS sandboxing.
- Existing orchestration already implements Carbon’s **deterministic workflow + role routing** thesis for the **model plane**.
- Building Omnigent-class collaboration is a different product (see `orchestration-platform.mdx` — Paperclip/Omnigent as external work plane).
- Option B delivers buyer-visible meta-harness **coordination** while Option C fills **execution environment** gaps without a rewrite.

---

## 6. Phased milestones

### P0 — Adapter seam + artifact handoffs (weeks 1–4)

**Goal:** Workflows can run at least one non-LLM harness worker with explicit artifacts.

| Deliverable | Notes |
|---|---|
| `HarnessAdapter` protocol | `capabilities()`, `run(ctx) -> ArtifactRef`, `cancel()`, `health()` |
| Agent package schema v1 | `.cutctx/agents/<id>.yaml` — harness, role, tools, policy refs, package hash |
| Package registry API | `GET/PUT /v1/orchestration/agent-packages` |
| Codex CLI adapter (POC) | Subprocess + `cutctx wrap` env; emit patch/test refs |
| Workflow integration | `WorkflowRunner.execute` dispatches by `task.payload.harness` |
| Artifact blob store | Content-addressed files under `CUTCTX_ORCHESTRATION_DIR/artifacts/` |
| CCR at boundaries | Compress artifact payloads; store `ccr_hash` in provenance |

**Success criteria:**

- Planner → implementer (Codex) → reviewer (LLM) workflow completes with no hidden session sharing
- Every handoff has artifact refs + receipt linkage
- Solo dev: single-host file store works out of the box

**Dual-path:** Local YAML packages + file artifacts; enterprise uses same APIs with Redis store + EE audit export.

### P1 — Lifecycle, control plane, policy (weeks 5–10)

| Deliverable | Notes |
|---|---|
| Worker lifecycle budgets | `max_cost_usd`, `max_duration_seconds`, `max_revision_rounds` on `TaskSpec` |
| Cost enforcement | Join workflow spend to `spend_ledger` / savings tracker |
| Event plane MVP | Extend proxy session registry → `cutctx sessions` + WS events |
| Human gates in dashboard | Approve/verify workflow tasks from Orchestration Studio |
| Role policy binder v1 | Map contract `ContractRequirements` → per-task `allowed_tools` + path prefixes |
| Claude Code / OpenCode adapters | Second and third harness adapters |
| Provenance graph (relational) | `artifact_id → parent_artifacts[]`, `worker_id`, `commit_ref` |

**Success criteria:**

- Operator can cancel in-flight worker from CLI/dashboard
- Workflow stops when cost budget exceeded (fail-closed)
- Audit export explains why each worker was permitted

### P2 — Enterprise hardening + partner slots (weeks 11–18)

| Deliverable | Notes |
|---|---|
| `ExecutionEnvironment` backend trait | Local subprocess / partner sandbox (Modal, Daytona, Omnigent) |
| ACP adapter | HTTP worker for Zed-style agents |
| Temporal `WorkflowRuntime` adapter (optional) | Behind interface; does not own routing |
| Package signing | Ed25519 witness on agent packages (mirror policy bundles) |
| Multi-host workflow backend | Production Redis/Postgres store |
| Omnigent integration path | Document + optional sidecar mode |

**Success criteria:**

- Enterprise runs reviewer in read-only sandbox with distinct credentials
- Same workflow definition runs on laptop (local) and k8s (shared store)
- Partner sandbox plug-in without fork

---

## 7. What NOT to build

| Do not build | Why |
|---|---|
| Omnigent-class real-time collaboration UI | Different product; partner or ignore |
| Full OS sandbox / egress proxy | Security team surface; partner with Omnigent or cloud sandbox |
| Supervisor-LLM workflow planner | Violates Carbon thesis; workflows stay code/YAML |
| General agent marketplace | Agent package registry is project-scoped, not npm-for-agents |
| GraphRAG / knowledge graph core | AIE design defers to partners |
| Replacement harnesses (Carbon-from-scratch) | Cutctx under harnesses, not competing with Carbon SDK |
| Eval platform (Arize/Langfuse class) | Thin compression/skill evals only |

---

## 8. Success criteria (overall)

1. **Functional:** Versioned multi-agent SDLC workflow (plan → implement → review) runs across ≥2 harness types with deterministic recovery after worker crash.
2. **Governance:** Every worker execution has routing receipt + artifact provenance + attributable cost.
3. **Context:** Handoff payload token count measurably lower than raw transcript relay; CCR retrieval works for reviewer.
4. **Dual-path:** Solo dev uses local files + `cutctx wrap`; enterprise enables Redis, EE audit, external secrets without separate product fork.
5. **Honest scope:** Documentation positions Cutctx as **meta-harness coordination + context plane**, not full Omnigent replacement.

---

## 9. Quick wins (≤2 weeks each)

| # | Win | Effort | Impact |
|---|---|---|---|
| 1 | **Agent package YAML + hash** — parse `.cutctx/agents/*.yaml`, expose in `/v1/orchestration/agent-packages` | 3–5d | Registry foundation |
| 2 | **Workflow task budgets** — add `max_cost_usd` / `max_duration_seconds` to `TaskSpec` with fail-closed check | 3–4d | Lifecycle parity signal |
| 3 | **Artifact blob store** — implement refs in `TaskArtifact.patch_ref` etc. | 4–5d | Handoff credibility |
| 4 | **Session control MVP** — proxy `SessionRegistry` + `cutctx session kill` (from July exploration doc) | 5–8d | Event/control plane seed |
| 5 | **Receipt → workflow UI** — show decision receipts on workflow task rows in Orchestration Studio | 2–3d | Observability without new backend |

---

## 10. What you give up vs what you add

### Give up (if pursuing parity)

- Claiming Cutctx is a **complete** meta-harness out of the box
- Competing on **live multi-user session collaboration**
- Owning **hardware/OS-grade sandbox** without partners

### Add (to get close)

- Harness adapter runtime (not just model adapters)
- Content-addressed artifact store + lineage
- Workflow-level cost/duration enforcement
- Live session control (cancel/pause) at proxy boundary
- Agent package versioning (thin YAML, not full IDE)

### Keep (differentiation)

- Reversible compression at worker boundaries
- Cross-agent memory + CCR retrieval
- Deterministic model routing with signed policy bundles
- Buyer-report-grade cost attribution
- Local-first solo path

---

## 11. Positioning sentence

> **Meta-harness coordinates who runs and when. Cutctx governs what each worker reads, what it costs, and what evidence it produced — with deterministic policy and retrievable context at every handoff.**

---

## 12. Open decisions

1. **First harness adapter:** Codex CLI vs Claude Agent SDK vs Omnigent sidecar?
2. **Sandbox default:** Local subprocess only in P0, or require partner from day one for enterprise?
3. **Workflow store:** Promote Redis backend to supported single-host default before multi-host?
4. **ACP priority:** P1 or P2 based on design-partner demand?

---

## 13. References

- Carbon Layer talk: https://www.youtube.com/watch?v=HRUBDPdvaHU
- Omnigent architecture: https://www.databricks.com/blog/introducing-omnigent-meta-harness-combine-control-and-share-your-agents
- Cutctx orchestration docs: `docs/content/docs/orchestration-platform.mdx`
- Universal orchestration plan: `docs/superpowers/specs/2026-07-13-universal-orchestration-implementation-plan.md`
- Remote session control exploration: `audit/remote-agent-orchestration-exploration.md`
