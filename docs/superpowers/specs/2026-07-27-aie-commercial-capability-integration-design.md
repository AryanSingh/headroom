# AIE Commercial Capability Integration Design

**Date:** 2026-07-27  
**Source:** AI Engineer YouTube catalog (`@aiDotEngineer`, ~940 talks) mapped to Cutctx  
**Status:** Approved ranking (Approach 1 + Approach 3 filter)  
**Commercial rule:** Serve developer adoption and enterprise together; ship enterprise work only when it also helps (or does not hurt) the solo/dev path.

---

## 1. Outcome

Improve Cutctx’s commercial chances by integrating the **highest-fit** capabilities signaled by AI Engineer talks into:

1. **Product** — features that deepen the context control plane without becoming an eval/security/graph platform.
2. **GTM packaging** — language, proof, and surfaces that match what buyers already hear at AIE.

This is not a mandate to rebuild every conference theme. It is a ranked adoption map with hard out-of-scope cuts.

---

## 2. Constraints (Approach 3 filter)

Hard P0 blockers — themes that depend on these cannot ship as paid commercial claims until fixed/verified:

1. **Entitlement enforcement** — paid features (CCR, episodic memory, audit) must require a validated license/trial, not raw `CUTCTX_ENTITLEMENT_TIER`. Existing design/plan: `2026-07-22-licensing-enforcement-*`. Treat as verify-complete, not redesign.
2. **Honest savings claims** — public README/website numbers must match attributable buyer-report semantics (eligible payloads vs all traffic; provider cache separate from Cutctx-created savings).
3. **Dual-path rule** — no enterprise-only dark pattern that degrades free/local solo UX (Builder compression, wrap, MCP tools stay useful without a license).

---

## 3. Ranked themes (approved)

| Priority | Theme | Product role | GTM role |
|---|---|---|---|
| **P0** | Context control / systems of context / memory | Own category; polish reversible memory + protection of instruction context | Headline: “context control plane” |
| **P0** | Token/cost discipline + attributed ROI | Buyer report truth + eligible-payload framing | CFO proof + power-user proof |
| **P0** | Harness / wrap / “claw” runtime | Deepen wrap + global routing + doctor | Distribution: Cutctx sits under every harness |
| **P0/P1** | Skills / MCP as product surface | Skill-aware preservation + installable Cutctx skill | “Skills not agents” packaging |
| **P1** | Security / permissions / provenance / receipts | Package firewall + decision receipts; wire entitlements | “Agents need receipts” + local-first governance |
| **P1** | Evals / verifiers (thin slice) | Compression-integrity / skill-survival evals only | Trust story, not an eval platform |
| **P2** | Graph / ontology memory | Optional Neo4j/devcontainer path only | Partner language, do not own |
| **Out** | Voice, robotics, RL/training, vertical workflows | — | Ignore for roadmap |

---

## 4. Architecture (what we build vs reuse)

```text
AIE market signal
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Cutctx commercial integration layer                      │
│                                                          │
│  Reuse (already shipped / planned):                      │
│   · Proxy + ContentRouter + CCR + memory                 │
│   · Decision receipts (schema v1)                        │
│   · Licensing enforcement path                           │
│   · Global harness routing / wrap                        │
│   · MCP tools + plugins/cutctx-plugin skills             │
│   · cutctx report buyer + savings attribution            │
│                                                          │
│  Net-new in this program:                                │
│   · Skill/instruction preservation in compression        │
│   · Skill discovery on wrap (Claude/Codex skill dirs)    │
│   · Honest eligible-payload public claims + report copy  │
│   · Harness “claw” packaging (doctor + matrix + website) │
│   · Receipts/firewall commercial packaging               │
│   · Thin compression/skill-survival eval harness         │
└──────────────────────────────────────────────────────────┘
```

**Boundary rules**

- Do **not** build a general agent eval platform (Arize/Langfuse competitors).
- Do **not** build graph memory as a core product (Neo4j partners / optional stack only).
- Do **not** rebuild agent security suites (Snyk/Keycard); package local firewall + receipts + audit.
- Prefer packaging and thin seams over new subsystems.

---

## 5. Product design by theme

### 5.1 P0 — Context control plane

**Keep owning:** reversible compression, cross-agent memory, context budgeting, decision receipts.

**Add:**

- **Instruction / skill preservation** — detect skill bodies and critical instruction blocks; protect them from aggressive compression the same way system-prompt cache safety is protected today.
- **Memory GTM clarity** — document “systems of context” as: session compression + reversible CCR + cross-agent memory + receipts (reasoning traces), without claiming a full context graph.

### 5.2 P0 — Token/cost ROI

**Keep owning:** six-source savings attribution + `cutctx report buyer`.

**Add:**

- Public copy that distinguishes **eligible long-context / tool-output workloads** from **all-traffic averages**.
- Buyer-report banner fields: sample size, % requests compressed, % bypassed as too small, created vs observed savings.
- README/website claims must cite the same schema as the buyer report.

### 5.3 P0 — Harness / claw layer

**Keep owning:** `cutctx wrap`, `cutctx global`, agent compatibility matrix.

**Add:**

- One commercial narrative: Cutctx is the **context substrate under every harness** (“every harness becomes a claw” → Cutctx is the shared context plane those claws run through).
- `cutctx global doctor` / wrap status improvements only where they remove install friction (compatibility boundary already documented).
- Website/docs section that maps Claude Code / Codex / Cursor / OpenCode → one proxy.

### 5.4 P0/P1 — Skills + MCP

**Keep owning:** MCP server tools; `plugins/cutctx-plugin/skills/cutctx/SKILL.md`.

**Add:**

- `skill_preserve` compression mode (config flag, default on for wrap sessions when skill markers detected).
- Wrap-time discovery of `~/.claude/skills/` and Codex/Cursor skill dirs → preservation rules.
- Publish/version the Cutctx skill for progressive disclosure (name + one-liner first; full body on demand).
- Defer skill-token dashboard widgets to P1 if they require new dashboard routes.

### 5.5 P1 — Security / receipts

**Keep owning:** LLM firewall, audit log, decision receipts, RBAC/SSO (EE).

**Add:**

- Commercial packaging: “Agents need receipts” maps to decision receipts + buyer report.
- Ensure firewall/scan remains usable for Builder (local safety) while audit export stays entitled.
- No new permission OS; document provenance via receipt + CCR hash chain.

### 5.6 P1 — Thin evals

**Add only:**

- Eval that asserts skill/instruction blocks survive compression.
- Eval that asserts buyer-report attribution invariants (created vs observed).
- Optional hook to existing `cutctx evals` CLI — not a new SaaS.

---

## 6. GTM packaging (parallel to product)

| Asset | Change |
|---|---|
| `artifacts/value-proposition.md` | Align pillars to AIE language: systems of context, harness substrate, skills+MCP, receipts |
| `README.md` | Eligible-payload honesty; harness matrix as distribution story |
| `website/` | One section: “Context control plane under your agents” |
| `docs/content/docs/` | Skill preserve, receipts-for-buyers, harness claw narrative |
| Sales one-pager (optional artifact) | Map AIE buyer objections → Cutctx answer |

---

## 7. Success criteria

1. Solo/dev path: wrap + MCP + Builder compression unchanged or improved (skill preserve reduces quality regressions).
2. Enterprise path: paid features fail closed without license; buyer report is CFO-defensible.
3. Commercial narrative: one sentence a buyer who attended AIE recognizes — *Cutctx is the local-first context control plane under your agent harnesses.*
4. Scope discipline: no graph-core, no eval platform, no security suite rebuild in this program.

---

## 8. Non-goals

- Competing with Arize/Langfuse on evals.
- Competing with Neo4j on context graphs.
- Voice agents, robotics, RL/post-training.
- Replacing Claude/Codex/Cursor harnesses — Cutctx sits underneath them.

---

## 9. Related existing work

| Artifact | Role |
|---|---|
| `docs/superpowers/specs/2026-07-04-skills-mcp-context-graphs-adoption.md` | Prior AIE EU adoption analysis — execute skill parts, defer graph |
| `docs/superpowers/specs/2026-07-22-licensing-enforcement-design.md` | Commercial filter prerequisite |
| `docs/superpowers/specs/2026-07-17-context-decision-receipt-design.md` | Receipts foundation (largely shipped) |
| `artifacts/value-proposition.md` | Messaging baseline |

---

## 10. Delivery shape

Implement as **one phased plan** with independently shippable phases. If execution capacity is limited, split later into:

1. Plan A — Commercial honesty + skill preserve  
2. Plan B — Harness/claw packaging + skills GTM  
3. Plan C — Receipts/security packaging + thin evals  

Default: single master plan with phases A→C sequential, GTM tasks parallel inside each phase.
