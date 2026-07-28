# UI/UX Review — AIE Commercial Capability Integration

**Date:** 2026-07-27  
**Branch:** `feat/aie-commercial-capability-integration` (9 commits vs `main`)  
**Worktree:** `.worktrees/aie-commercial-capability-integration`  
**Reviewer lens:** UI/UX reviewer skill (navigation, hierarchy, flows, accessibility, competitive clarity)  
**Scope:** User-facing copy and surfaces changed in this branch — website, README, value proposition, docs, Cutctx skill, buyer report CLI output. No code changes were made as part of this review.

---

## Executive summary

The branch makes a coherent strategic shift: from “token saver” headlines toward **context control plane**, **harness substrate**, **skill-aware compression**, and **attributed ROI**. The honesty work in `cutctx report buyer` and the README eligible-payload caveat are the strongest UX wins — they reduce buyer distrust and align public claims with measurable output.

Gaps are mostly **information architecture and messaging polish**: the new website section reuses layout patterns well but introduces brand inconsistency and sits without a visual anchor; `skills.mdx` is technically clear but hard to discover; buyer-report metrics are correct but still easy to misread because “Combined savings” leads the page; and several surfaces use insider vocabulary (“AIE”, “claws”, “eligible”) without a shared glossary.

**Overall rating:** 🟡 **Good direction, needs IA and copy tightening before commercial launch**

---

## UX Report

### 1. Strategic messaging shift

| Surface | Old emphasis | New emphasis | Clarity |
|--------|--------------|--------------|---------|
| `artifacts/value-proposition.md` | Benefit-led pillars (cost, context, privacy, retrieval, team) | AIE-aligned pillars (systems of context, harness substrate, skills+MCP, attributed ROI, governance) | Strong for sales enablement; weaker for first-time readers |
| `website/index.html` | Hero = “context efficiency + routing” | New mid-page block = “context control plane under your agents” | Aligns with value prop; hero still leads with older framing |
| `README.md` | Savings table without inline caveat | Eligible-payload caveat + pointer to `cutctx report buyer` | Excellent trust move |
| `plugins/.../SKILL.md` | “Good Use” examples | “Do Not” guardrails + buyer-report honesty | Better agent safety; loses positive examples |

The narrative is **internally consistent** on the core line: *“local-first context control plane under your agent harnesses.”* That phrase appears in value-proposition, global-routing docs, and the new website section.

### 2. User flow — Developer discovering skill preserve

**Intended path**

```
Install / wrap agent → proxy enables CUTCTX_SKILL_PRESERVE → skills discovered from disk → instruction bodies protected → tool outputs still compressed
```

**What works**

- `docs/content/docs/skills.mdx` explains the mechanism in plain technical language: what is protected, what stays compressible, and which env vars matter.
- `SKILL.md` tells agents not to compress skill bodies or invent savings — the right behavioral guardrails for MCP hosts.
- `meta.json` places `skills` under **Integrations**, which is reasonable.

**Friction points**

| Step | Issue | Severity |
|------|-------|------------|
| Discovery | No cross-links from `quickstart`, `global-routing`, `mcp.mdx`, or `wrap` docs to `skills.mdx` | Medium |
| Verification | Page describes behavior but not **how to confirm** preservation (e.g. decision receipt field, eval command, sample log line) | Medium |
| Agent path vs human path | Developers may never read `skills.mdx`; they rely on wrap defaults. No “you’re already protected” callout in onboarding docs | Medium |
| Naming | “Skill preserve” vs “skill-aware compression” vs `CUTCTX_SKILL_PRESERVE` — three labels for one feature | Low |

**Recommended ideal flow (not yet implemented)**

1. Quickstart or wrap doc: one sentence — “Wrap enables skill-aware compression automatically.”
2. Link to `/docs/skills`.
3. Optional: `cutctx doctor` or `cutctx wrap --dry-run` line showing discovered skill count (product gap, not in this branch).

### 3. User flow — Buyer / finance reading ROI report

**Intended path**

```
Run workload → cutctx report buyer [--fmt markdown|text|json] → separate created vs observed → share with CFO
```

**What works**

- `_BUYER_CAVEAT` and eligible vs all-traffic rates directly address the README honesty problem.
- Separating **Created (Cutctx) tokens** from **Observed provider cache tokens** matches value-proposition “Attributed ROI” and objection handling.
- Markdown uses a blockquote for the caveat — good visual precedence for human readers.
- JSON embeds `caveat`, `eligible_compression_rate`, `all_traffic_compression_rate` — good for dashboards and scripts.
- Tests in `test_buyer_report_honesty.py` pin the math contract.

**Friction points**

| Issue | Why it hurts | Severity |
|-------|--------------|----------|
| **“Combined savings” still leads** the report before honesty metrics | Skimmers see headline totals first; caveat is easy to miss in plain-text output | High |
| **“Eligible” is undefined** in the report body | CFOs and PMs may not know eligible = total minus bypassed-small | High |
| Text format `compressed/bypassed/total` | Compact for engineers; opaque for finance stakeholders | Medium |
| No worked example or doc link in output | Reader must infer interpretation from field names alone | Medium |
| `total_tokens_saved` sums all sources | Correct per attribution note, but can be confused with “Cutctx-created” savings | Medium |

**Stripe-style benchmark:** Stripe puts the **most decision-relevant number first** with a plain label (“Net volume”, “Fees”) and footnotes ambiguity. This report is honest but still orders like a engineering dump, not a buyer brief.

### 4. User flow — Commercial evaluator landing on website

**Path:** Homepage → new `#context-plane` section → Global routing or Wrap CTA → docs.

**What works**

- Section placement (after compatibility chips, before “how it works”) correctly reframes the product before the seven-step loop.
- `aria-labelledby="context-plane-heading"` and semantic `<section>` — accessible structure.
- CTAs point to the right next steps (`/docs/global-routing`, `/docs/#quick-start`).
- Reuses `.section`, `.section-heading`, `.hero-actions` — consistent with existing site patterns (per prior launch audit).

**Friction points**

- Hero still says “context efficiency + intelligent routing”; new section says “context control plane.” A visitor gets **two positioning frames** in the first two scrolls.
- No anchor in primary nav for the new narrative block (only `#platform` exists elsewhere).
- OpenCode is named in copy but not in the compatibility chip row (Claude Code, Codex, Cursor, Cline, Aider are).

### 5. Accessibility — docs and copy structure

| Surface | Structure | Notes |
|---------|-----------|-------|
| `skills.mdx` | H1 → H2 → H3 → table | Good hierarchy; table has header row |
| `global-routing.mdx` | “Why this matters” before install steps | Good progressive disclosure |
| `proxy.mdx` AIE table | Two-column mapping table | Readable; “AIE language” column assumes context |
| `SKILL.md` | Short description + numbered sections | Fits progressive-disclosure intent for agent catalogs |
| Buyer report (markdown) | H1, blockquote caveat, H2 sections | Screen-reader friendly; plain text lacks heading structure for caveat |

**Gaps**

- `skills.mdx` env table has no `<caption>` equivalent in MDX (minor; title row suffices for most readers).
- Buyer report text format: caveat is plain paragraph, not visually distinguished beyond position.
- No glossary entry for “eligible payload”, “created vs observed”, or “decision receipt” linked from docs changed in this branch.

### 6. Competitive positioning clarity (vs Stripe / Linear)

| Criterion | Stripe / Linear bar | This branch | Gap |
|-----------|---------------------|-------------|-----|
| One-line value prop | Single crisp sentence above the fold | Two frames on homepage (efficiency/routing vs control plane) | Medium |
| Benefit-led headers | “Increase revenue” not “PaymentIntents API” | Value-prop pillars use taxonomy labels (“Systems of context”, “Harness substrate”) | Medium |
| Trust through transparency | Metrics labeled in plain English | Buyer report is truthful but jargon-heavy | Medium |
| Progressive disclosure | Simple surface, depth on demand | `SKILL.md` and skills doc do this well | Low gap |
| CTA clarity | One primary action per viewport | New section uses two secondary buttons; hero primary remains “Start free” | Low |

**Standout positive:** Attributed ROI and explicit non-netting of provider cache vs Cutctx compression is **more honest than most infra vendors** and closer to Stripe’s receipt mentality than to typical “90% savings” landing pages.

---

## UI Report (website)

**File reviewed:** `website/index.html` (new `#context-plane` section, lines 83–93)

### Visual hierarchy

- **Eyebrow → H2 → body → actions** matches existing sections (`#how-it-works`, `#platform`). Hierarchy is correct.
- Unlike neighboring sections, this block has **no grid, cards, diagram, or chips** — it is copy-only between a chip row and a dense 7-step process grid. Visually it may feel like a **pause or downgrade** in information density.
- Both CTAs use `button-secondary`. That is consistent with mid-page doc links but does not signal a **new primary story** the way a single primary CTA or illustrative mini-diagram would.

### Component and brand consistency

- **Brand casing:** New copy uses `Cutctx`; rest of page and title use `CutCtx` (e.g. hero, footer, `<title>`). Visible inconsistency on a marketing surface.
- **Terminology:** “harnesses” on website vs “claws” in internal value-proposition — website choice is correct for public UX.
- **Class reuse:** `hero-actions` inside a non-hero section is an established pattern on this page (evidence section uses it too) — acceptable.

### CTA assessment

| CTA | Target | Fit |
|-----|--------|-----|
| Global routing | `/docs/global-routing` | Strong for macOS harness users |
| Wrap an agent | `/docs/#quick-start` | Strong for evaluators |
| Missing | `/docs/skills` or security/receipts story | Opportunity — skills are a differentiator not surfaced on homepage |

Neither CTA is tracked with `data-cta` attributes unlike header/hero/evidence CTAs — analytics gap for measuring interest in the new narrative.

### Mobile / responsive

- No new CSS was added in this branch; section relies on existing `site.css` (referenced as `/assets/site.css?v=20260721-platform`).
- Prior launch audit verified responsive behavior for the same layout primitives (`hero-actions`, `section`, mobile nav).
- **Risk:** Text-only section with two side-by-side buttons should wrap cleanly; no new overflow vectors expected.
- **Recommendation:** Re-run `tests/website/test_static_site.py` and a quick mobile snapshot after merge — not re-verified in this review.

### Accessibility (website)

- Section has `aria-labelledby` pointing to unique `id="context-plane-heading"` — good.
- No new interactive elements beyond links — keyboard path unchanged.
- Skip link and nav landmarks unchanged — no regression expected.

---

## Gap Analysis

### Messaging consistency gaps

| Gap | Locations | Impact |
|-----|-----------|--------|
| Dual homepage positioning | Hero vs `#context-plane` | Evaluators unsure what category CutCtx is in |
| `Cutctx` vs `CutCtx` | New website paragraph vs site-wide brand | Looks unintentional; hurts polish |
| AIE vocabulary on developer docs | `proxy.mdx` “AIE buyer mapping” | Developers without AIE context may ignore or misread |
| Pillar titles vs outcomes | `value-proposition.md` | Sales deck clarity ↓ vs old benefit headers |
| Positive skill examples removed | `SKILL.md` “Good Use” → “Do Not” only | Agents may under-use compression when appropriate |

### Information architecture gaps

| Gap | Impact |
|-----|--------|
| `skills.mdx` not linked from onboarding/integration pages | Feature discovery |
| Buyer report interpretation not documented | Finance misreads totals |
| `#context-plane` not in nav or footer | Narrative section is scroll-only |
| OpenCode in copy but not compatibility chips | Minor trust/recognition gap |

### UX vs competitor gaps

| Area | Competitors / category norm | CutCtx after this branch |
|------|----------------------------|---------------------------|
| Savings claims | Often inflated single % | Honest eligible vs fleet — **ahead of category** |
| Agent harness story | Cursor/Codex docs are harness-specific | Shared substrate story is differentiated but under-visualized |
| CFO-ready export | Stripe-style PDF/summary | Markdown/text/json only; no executive summary template |
| Skill/instruction protection | Rarely marketed | Strong technical story; weak discoverability |

### Design quality gaps

| Gap | Severity |
|-----|----------|
| New website section lacks visual support (diagram, harness stack) | Medium |
| Buyer report text UI is engineer-oriented | Medium |
| No dashboard UI changes for skill preserve or buyer honesty fields | Low (out of branch scope) |

---

## Prioritized recommendations

### P0 — Before commercial / AIE-facing launch

1. **Unify homepage positioning in the hero** (or add a subhead) so the first screen and `#context-plane` tell one story — e.g. lead with “context control plane” and subordinate “routing” as a capability.
2. **Fix `Cutctx` → `CutCtx`** in the new website paragraph (and audit other changed copy for casing).
3. **Reorder buyer report sections:** put caveat + eligible/created vs observed **above** “Combined savings”, or rename “Combined savings” to “All sources (see attribution)” with a one-line definition of eligible.
4. **Add a plain-language glossary line** to buyer report output:  
   *Eligible requests = total requests minus those bypassed as too small to compress.*

### P1 — High value, low effort

5. **Cross-link `skills.mdx`** from `global-routing.mdx`, `mcp.mdx`, and quickstart/wrap docs with one sentence on wrap enabling preservation by default.
6. **Add `data-cta` attributes** to the two new homepage buttons (`context-plane-routing`, `context-plane-wrap`) for conversion tracking parity.
7. **Rename or reframe `proxy.mdx` table** from “AIE buyer mapping” to “Commercial concepts → product surfaces” (or move to a sales/enterprise doc) to reduce developer confusion.
8. **Restore one short “When to compress” bullet block** in `SKILL.md` (keep “Do Not” as the final section) so agents retain positive examples without weakening guardrails.
9. **Add OpenCode** to compatibility chips if it remains in harness copy.

### P2 — Polish and competitive lift

10. **Visual for `#context-plane`:** simple three-layer stack (Harnesses → CutCtx plane → Providers) matching Stripe’s diagram clarity — static SVG consistent with `product-flow`.
11. **Docs page: “Reading the buyer report”** with a sample markdown snippet and CFO FAQ (eligible rate, created vs observed, why totals sum sources).
12. **Value-proposition pillar subtitles:** keep AIE taxonomy as eyebrow, add benefit subline (Linear-style): e.g. “Harness substrate — keep context infra when you switch agents.”
13. **skills.mdx verification section:** document receipt metadata or `cutctx.evals.skill_survival` as a confidence check for operators.
14. **Executive export:** optional `--fmt executive` one-pager (even a static template) for Team/Enterprise buyers.

---

## Surface-by-surface scorecard

| Surface | Hierarchy | Clarity | CTA / next step | A11y structure | Consistency | Score |
|---------|-----------|---------|-----------------|----------------|-------------|-------|
| `website/index.html` (#context-plane) | Good | Good | Good links; no primary emphasis | Good | Brand casing ⚠️ | 🟡 |
| `README.md` proof section | Good | Excellent | Points to buyer report | Good | Aligns with report | 🟢 |
| `artifacts/value-proposition.md` | Good | Medium (insider terms) | N/A (internal) | Good | Strong internal alignment | 🟡 |
| `docs/content/docs/skills.mdx` | Good | Good | Weak discovery | Good | Needs cross-links | 🟡 |
| `docs/content/docs/global-routing.mdx` | Good | Good | Install CTAs unchanged | Good | Matches website line | 🟢 |
| `docs/content/docs/proxy.mdx` (AIE table) | Good | Medium | N/A | Good table | Jargon on dev surface | 🟡 |
| `plugins/.../SKILL.md` | Good | Good | Agent-oriented | Good | Improved honesty | 🟢 |
| `cutctx/cli/report.py` (buyer output) | Fair | Good with caveats | No doc link | Text fmt weak | Honest metrics | 🟡 |

---

## Test and verification suggestions (for implementers)

- Re-run website static tests after copy/brand fixes.
- Add a snapshot or golden-file test for buyer report markdown section **order** once P0 reorder lands.
- Manual check: mobile width on `#context-plane` with two buttons wrapped.
- Smoke: `cutctx report buyer --fmt markdown` on empty/small-traffic data to ensure caveat still reads well when rates are 0%.

---

## Conclusion

This branch improves **trust and commercial credibility** more than it improves **visual storytelling**. The product narrative is ready for AIE-aligned conversations; the user-facing layer needs tighter homepage unity, discoverable skills documentation, and buyer-report information design that leads with honesty fields instead of burying them under combined totals. Addressing the P0 items would move the release from “technically honest” to “buyer-clear” in the Stripe/Linear sense — without changing the underlying attribution model, which is already sound.
