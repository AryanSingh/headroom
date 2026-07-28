# Deepwork: Meta-Harness P0

## Goal

Ship P0 meta-harness adapter seam: `HarnessAdapter` protocol, agent package YAML registry, Codex CLI adapter POC, content-addressed artifact blob store, and CCR at workflow handoffs — enabling planner → Codex implementer → LLM reviewer workflows without hidden session sharing.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| P0 | Adapter seam + artifact handoffs (weeks 1–4) | **In progress** — Batch A+B+C+D partial (Tasks 1–8) |
| P1 | Lifecycle, control plane, policy (weeks 5–10) | Not started |
| P2 | Enterprise hardening + partner slots (weeks 11–18) | Not started |

## References

- **Design spec:** `docs/superpowers/specs/2026-07-28-meta-harness-orchestrator-parity-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-07-28-meta-harness-p0.md`
- **Branch:** `feat/meta-harness-p0`
- **Worktree:** `.worktrees/meta-harness-p0`

## P0 deliverables checklist

- [x] `HarnessAdapter` protocol (`capabilities`, `run`, `cancel`, `health`)
- [x] Agent package schema v1 + `.cutctx/agents/*.yaml` registry
- [x] `GET/PUT /v1/orchestration/agent-packages` API
- [x] Codex CLI adapter POC
- [ ] Workflow dispatch by `task.payload.harness`
- [x] Content-addressed artifact blob store
- [x] CCR compression at workflow handoffs
- [ ] E2E: planner → Codex implementer → LLM reviewer

## Constraints

- Local subprocess only in P0 (no cloud sandbox)
- Option B: thin layer on `cutctx/orchestration/`, not full Carbon parity
- Use `rtk`-prefixed commands for all shell work

## Batch A progress (Tasks 1–2)

| Task | Commit | Status |
|---|---|---|
| 1 — HarnessAdapter protocol + ArtifactRef types | `79853b8` | Done |
| 2 — Content-addressed artifact blob store | `0c90e23` | Done |

**Tests:** `tests/test_harness_adapter_types.py` (4 passed), `tests/test_artifact_store.py` (3 passed)

## Batch B progress (Tasks 3–4)

| Task | Commit | Status |
|---|---|---|
| 3 — Agent package YAML schema + canonical hash | `e94c963` | Done |
| 4 — File-backed AgentPackageRegistry | `b5cb574` | Done |

**Tests:** `tests/test_agent_packages.py` (6 passed)

## Batch C progress (Tasks 5–6)

| Task | Commit | Status |
|---|---|---|
| 5 — Agent package REST API | `e674bed` | Done |
| 6 — CCR compression at workflow handoffs | `8ccf159` | Done |

**Tests:** `tests/test_orchestration_agent_packages_api.py` (1 passed), `tests/test_handoff_ccr.py` (2 passed)

**Batch A–C combined:** 16 passed (`test_harness_adapter_types`, `test_artifact_store`, `test_agent_packages`, `test_orchestration_agent_packages_api`, `test_handoff_ccr`)

## Batch D progress (Tasks 7–8)

| Task | Commit | Status |
|---|---|---|
| 7 — Codex CLI harness adapter POC | `a538d05` | Done |
| 8 — HarnessRuntime dispatcher | (pending) | Done |

**Tests:** `tests/test_codex_cli_adapter.py` (1 passed), `tests/test_harness_runtime.py` (1 passed)
