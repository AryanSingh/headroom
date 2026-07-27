# Deepwork: Meta-Harness P0

## Goal

Ship P0 meta-harness adapter seam: `HarnessAdapter` protocol, agent package YAML registry, Codex CLI adapter POC, content-addressed artifact blob store, and CCR at workflow handoffs — enabling planner → Codex implementer → LLM reviewer workflows without hidden session sharing.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| P0 | Adapter seam + artifact handoffs (weeks 1–4) | **Planning complete** — ready for implementation |
| P1 | Lifecycle, control plane, policy (weeks 5–10) | Not started |
| P2 | Enterprise hardening + partner slots (weeks 11–18) | Not started |

## References

- **Design spec:** `docs/superpowers/specs/2026-07-28-meta-harness-orchestrator-parity-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-07-28-meta-harness-p0.md`
- **Branch:** `feat/meta-harness-p0`
- **Worktree:** `.worktrees/meta-harness-p0`

## P0 deliverables checklist

- [ ] `HarnessAdapter` protocol (`capabilities`, `run`, `cancel`, `health`)
- [ ] Agent package schema v1 + `.cutctx/agents/*.yaml` registry
- [ ] `GET/PUT /v1/orchestration/agent-packages` API
- [ ] Codex CLI adapter POC
- [ ] Workflow dispatch by `task.payload.harness`
- [ ] Content-addressed artifact blob store
- [ ] CCR compression at workflow handoffs
- [ ] E2E: planner → Codex implementer → LLM reviewer

## Constraints

- Local subprocess only in P0 (no cloud sandbox)
- Option B: thin layer on `cutctx/orchestration/`, not full Carbon parity
- Use `rtk`-prefixed commands for all shell work
