# Headroom — Moat Program (Overview & Strategy Memo)

**Date:** 2026-06-16
**Owner:** aryan
**Status:** Proposed
**Audience:** founders + engineering; specs are written to be handed directly to coding agents.

---

## 0. TL;DR

The four things our docs currently call "moats" — CCR reversibility, 6 algorithms, content routing, cross-agent memory — are **features, not moats**. They are Apache-2.0 licensed and the best model is on HuggingFace, so a competent team clones them in weeks. We have a good product with near-zero defensibility today.

There are exactly four things that can become durable. This program specs three of them as buildable engineering workstreams plus one as a positioning/roadmap constraint:

| # | Workstream | Moat type | Why not replicable | Build now? | Spec |
|---|------------|-----------|--------------------|-----------|------|
| A | Compression-quality **data flywheel** | Learning / data network effect | Competitors can copy the code, not the accumulated labeled corpus our traffic generates | Long game (start now) | [`01-data-flywheel.md`](01-data-flywheel.md) |
| B | **Switching costs** via co-created team memory | Switching costs | The team's accumulated, curated, value-scored memory lives in our intelligence layer and isn't portable | **Yes, first** | [`02-memory-switching-costs.md`](02-memory-switching-costs.md) |
| C | **Control plane of record** (spend/policy/audit + real licensing) | Switching costs + workflow embedding | Once finance trusts our numbers and compliance pulls audit from us, ripping out means losing history + re-instrumenting + re-certifying | Parallel (unlocks revenue) | [`03-control-plane-of-record.md`](03-control-plane-of-record.md) |
| D | **Counter-positioning** vs providers | Counter-positioning | Providers structurally won't build a cross-provider spend-reducer that helps customers leave them | Positioning today | [`04-counter-positioning.md`](04-counter-positioning.md) |

**Sequence:** Build **B now** (cheap, builds on `headroom/memory` + `headroom/learn`, no new infra). Stand up **C in parallel** (it unlocks revenue and is the server B and A both need). Commit to **A as the long game** (it forces the two hard decisions below). Adopt **D as positioning immediately** (mostly roadmap priority, not new code).

---

## 1. Why the current "moats" are not moats

> A moat is a structural reason a competitor *cannot* catch up even if they copy you. A feature is something they copy in a sprint.

- **CCR (reversible compression).** Our own `PRODUCT_ANALYSIS.md` calls this "the single most defensible differentiator." It is an afternoon of engineering: hash the original, store it (`headroom/ccr/batch_store.py`), expose a `headroom_retrieve` tool (`headroom/ccr/mcp_server.py`). Worse, it is partly self-defeating — every retrieval re-injects the tokens we just saved. Good feature; zero defensibility.
- **6 algorithms + ContentRouter.** Heuristics in `crates/headroom-core/src/transforms/`. Copyable. No data advantage behind them.
- **Kompress-v2-base.** Published on HuggingFace under Apache-2.0. It is *literally already copied* — anyone can pull the weights.
- **Cross-agent memory / coverage.** A vector store + dedup, and an integration treadmill. `lean-ctx` already supports 22+ agents. Coverage erodes (provider APIs change) and is matched by effort.

None of these compound with scale or create lock-in. That is the definition of "replicable."

---

## 2. The two decisions this program forces

Both moats A and the durable half of B/C require reversing a default. Make these calls deliberately:

### Decision 1 — Open-source boundary
Open source is our adoption engine and we should keep it. But **features can never be moats while everything is open**. Draw the line:

| Keep open (adoption) | Make proprietary / compounding (moat) |
|----------------------|----------------------------------------|
| Proxy, SDK, CLI, MCP server, `kompress-v2-base` (base model), CCR mechanism, integrations | Agent-tuned models (`kompress-agent-*`), the labeled training corpus, the team-memory **intelligence layer** (value model, dedup graph, curation state), the control plane (license/spend/policy/audit) |

The base model and client stay free and win the category. The *fine-tuned-on-your-traffic* models and the *server of record* are the things that get better with scale and can't leave with the customer.

### Decision 2 — Local-first vs. the data loop
Our value-prop pillar 3 is "your prompts never leave." That directly conflicts with a central training corpus. Reconcile it explicitly (specced in `01`):

- **Default:** nothing leaves. On-device episode capture + on-device aggregation.
- **Opt-in telemetry:** only **patterns** leave (hashes, distributions, keep/drop masks over offsets) — never values — with **differential privacy** noise and **k-anonymity** thresholds. This is an extension of the existing `headroom/telemetry/` design, which is already pattern-only.
- **Design-partner tier:** contractual opt-in to share raw payloads for the highest-quality corpus, in exchange for discount/priority models.
- **Federated option (air-gap / regulated):** ship gradient/stat updates, not data (`toin.import_patterns` is the seed of this).

If we refuse both decisions, we are building a great product that the providers or a fast-follower will capture the value from. Refusing is a valid choice — but then stop calling anything a moat and compete on execution and brand.

---

## 3. The mechanism of each moat (why it compounds)

- **A — data flywheel.** We sit in the one place where *ground-truth labels for compression quality are generated for free*: a `headroom_retrieve` call means "we dropped something the agent needed"; no retrieval + task success means "that compression was safe." More traffic → more labels → a better keep/drop model → fewer bad compressions → more adoption → more traffic. A new entrant starts at zero labels. **The corpus is the moat, not the code.**
- **B — switching costs.** `headroom learn` + memory accumulate a team's corrections and institutional knowledge. If that memory is (a) team-shared, (b) value-scored against real outcomes, and (c) load-bearing (agents measurably do worse without it), then leaving means abandoning an asset the customer co-created and can't re-import elsewhere.
- **C — embedding.** When the spend ledger is the number finance budgets against, and the audit log is what compliance exports for SOC2, Headroom stops being a tool and becomes infrastructure. Removal cost is organizational, not technical.
- **D — counter-positioning.** Anthropic/OpenAI native caching is free and improving — our biggest threat. But they will never ship a great *cross-provider* tool that helps you spend less with them and switch away; it cannibalizes their lock-in. Rooting our identity there is durable because it's grounded in *their* incentives, not our cleverness.

---

## 4. How to execute this with agents

These specs follow the repo's existing conventions (`REALIGNMENT/*`, `AGENT_TASKS.md`): each unit of work is a **PR on its own branch in its own worktree**, with explicit **files to add/modify/delete**, **schemas**, **acceptance criteria**, **tests**, and **blocked-by/blocks** edges.

**Operating rules for the implementing agent(s):**

1. **One PR = one branch = one worktree.** Branch names are given per PR (`moat-A1-…`). Never mix workstreams in a branch.
2. **Respect the dependency graph** at the top of each spec file. Parallelize anything not on a dependency edge.
3. **Every PR ends green:** `make ci-precheck`, `cargo test -p <crate>`, and `pytest` for touched packages. Rust changes must keep byte-faithful passthrough guarantees from `REALIGNMENT/03-phase-A-lockdown.md`.
4. **No request-path nondeterminism.** Per the TOIN observation-only contract (`headroom/telemetry/toin.py`), learning/telemetry must never mutate a live compression decision in-request. Models are loaded at startup from a versioned artifact; labels are written async/offline.
5. **Privacy is a test, not a comment.** Every egress path ships with a test asserting no raw values leave (see `01` PR-A4). A failing privacy test blocks merge.
6. **Eval-gate every model.** No model artifact is promoted unless it beats the incumbent on `headroom/evals/suite_runner.py` *and* lowers retrieval rate on shadow traffic (`01` PR-A6).
7. **Flag-default-off.** Every new collection/sync/egress feature ships behind a config flag defaulting to off, with an explicit opt-in (`headroom/config.py`).

**Suggested agent assignment**
- Agent 1 → Workstream B (independent, fastest to value).
- Agent 2 → Workstream C C1–C3 (license hardening; unblocks revenue and is a dependency for A/B servers).
- Agent 3 → Workstream A A1–A2 (local episode capture; no server needed yet).
- Converge on C4–C7 (shared control-plane service) once C1–C3 land.

---

## 5. Risks & kill-criteria

- **A is expensive and slow.** Kill if, after a labeled corpus from ≥10 active orgs, the agent-tuned model can't beat `kompress-v2-base` by a meaningful margin on held-out eval AND reduce live retrieval rate. If the signal isn't there, A is not a moat — fall back to B+C+D.
- **B can become a junk drawer.** Kill the "more memory" instinct; the metric that matters is *measured outcome lift from injected memory* (`02` PR-B3). If memory doesn't lift success/cost, it isn't load-bearing and isn't a moat.
- **C is a build-vs-buy trap.** Don't rebuild Stripe/SSO/SOC2 plumbing from scratch where vendors exist (`billing/stripe_webhook.py` already integrates Stripe). The moat is the *spend/policy/audit ledger*, not the auth.
- **Privacy backlash.** If the opt-in telemetry is perceived as "they read our prompts," the local-first brand dies. Over-invest in the verifiable no-egress proof (`04`) and make opt-in genuinely opt-in.

---

## 6. File index

- [`01-data-flywheel.md`](01-data-flywheel.md) — Workstream A: closed compression-quality learning loop + proprietary agent-tuned model.
- [`02-memory-switching-costs.md`](02-memory-switching-costs.md) — Workstream B: team memory as a co-created, value-scored, load-bearing asset.
- [`03-control-plane-of-record.md`](03-control-plane-of-record.md) — Workstream C: real licensing + spend/policy/audit system of record.
- [`04-counter-positioning.md`](04-counter-positioning.md) — Workstream D: cross-provider/local-first roadmap that providers can't follow.
