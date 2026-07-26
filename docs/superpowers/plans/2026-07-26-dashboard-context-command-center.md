# Context Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a best-in-class Cutctx operator dashboard visual identity (Context Command Center) across all surfaces with TDD-pinned contracts.

**Architecture:** Replace design tokens, fonts, and shell chrome first; then unify shared panel/state primitives; then restyle command-center and control-plane pages without changing API contracts. Pin identity with node:test CSS contracts and Playwright shell/page assertions.

**Tech Stack:** Vite, React 19, React Router 7, Lucide, CSS variables in `dashboard/src/index.css`, Playwright, node:test.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-26-dashboard-context-command-center-design.md`
- Fonts: Sora (display), IBM Plex Sans (body), IBM Plex Mono (mono) — never Inter as `--font-body`
- Accent dark `#1FCBAA` / light `#0F766E`; surfaces per spec
- No glow stacks; `prefers-reduced-motion` required
- Preserve routes, admin auth, and existing e2e behaviors unless intentionally updated in the same task
- TDD: failing test before production change for every task
- Work only in `.worktrees/dashboard-visual-identity` on `feat/dashboard-visual-identity`

---

## File map

| File | Responsibility |
|---|---|
| `dashboard/index.html` | Font preconnect + stylesheet |
| `dashboard/src/index.css` | Tokens, shell, panels, motion, theme |
| `dashboard/src/App.jsx` | Shell markup / identity classes if needed |
| `dashboard/src/components/PageHeader.jsx` | Display title pattern |
| `dashboard/src/components/StatePanel.jsx` | Unified empty/error/info |
| `dashboard/src/pages/*.jsx` | Surface hierarchy / class alignment |
| `dashboard/tests/design-tokens.test.js` | Token/font contracts |
| `dashboard/e2e/visual-identity.spec.js` | Shell + theme + header identity |
| `audit/ui-review-report.md` | Final review + screenshots |

---

### Task 1: Design-token contracts (TDD)

**Files:**
- Create: `dashboard/tests/design-tokens.test.js`
- Modify: `dashboard/index.html`, `dashboard/src/index.css`

- [ ] **Step 1: Write failing test** asserting `--font-display` includes Sora, `--font-body` includes IBM Plex Sans, `--font-mono` includes IBM Plex Mono, dark `--accent` is `#1FCBAA`, `--surface-0` is `#090A0E`, styles contain `prefers-reduced-motion`, and `--font-body` does not include `Inter`.

- [ ] **Step 2: Run test — expect FAIL**
```bash
cd dashboard && npm test -- tests/design-tokens.test.js
```

- [ ] **Step 3: Update `index.html` fonts + `:root` / `.dark` / `.light` tokens in `index.css` to pass.**

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `test+feat: pin Context Command Center design tokens`

---

### Task 2: Shell chrome + Playwright identity

**Files:**
- Create: `dashboard/e2e/visual-identity.spec.js`
- Modify: `dashboard/src/index.css`, `dashboard/src/App.jsx` as needed

- [ ] **Step 1: Write failing e2e** that loads dashboard with mocked health/stats, asserts `html` or app shell uses Sora on `.topbar-title-row h2` (computed font-family contains Sora), body font contains IBM Plex Sans, theme toggle flips `.light`/`.dark`, mobile drawer Escape still works.

- [ ] **Step 2: Run e2e — expect FAIL** (fonts not loaded / not applied)

- [ ] **Step 3: Apply shell CSS (sidebar, topbar, auth) to new tokens; ensure title uses display font.**

- [ ] **Step 4: Run e2e — expect PASS** (and existing `e2e/ui.spec.js` still green)

- [ ] **Step 5: Commit** `feat: restyle dashboard shell for Context Command Center`

---

### Task 3: Shared PageHeader + StatePanel

**Files:**
- Modify: `PageHeader.jsx`, `StatePanel.jsx`, `index.css`
- Create/extend: `dashboard/tests/state-panel.test.js` (source contract) and/or e2e assertions

- [ ] Write failing source/CSS tests for `.page-header-title` display font class and `StatePanel` tone class map.
- [ ] Implement minimal markup/CSS.
- [ ] Verify tests green.
- [ ] Commit `feat: unify page header and state panels`

---

### Task 4: Overview + Savings

**Files:** `Overview.jsx`, `Savings.jsx`, `index.css`, related e2e

- [ ] Extend e2e/overview + savings assertions for hero hierarchy classes (`.savings-hero` or equivalent).
- [ ] Watch fail → implement hierarchy CSS/JSX → pass.
- [ ] Commit `feat: polish Overview and Savings command center`

---

### Task 5: Orchestrator + Governance + Security

**Files:** `Orchestrator.jsx`, `Governance.jsx`, `Firewall.jsx`, routing-studio CSS, e2e

- [ ] Fail tests for section headers / draft-live label / empty states.
- [ ] Implement → pass.
- [ ] Commit `feat: polish control-plane surfaces`

---

### Task 6: Remaining surfaces

**Files:** Memory, Replay, Playground, Docs, Capabilities

- [ ] Fail + pass identity/header/empty-state contracts per page.
- [ ] Commit `feat: align remaining dashboard surfaces to identity`

---

### Task 7: UI review report + screenshots

**Files:** `audit/ui-review-report.md`, `audit/screenshots/*`

- [ ] Capture desktop+mobile screenshots of key surfaces.
- [ ] Write review against WCAG refs; close gaps found.
- [ ] Commit `docs: dashboard UI review report for Context Command Center`

---

## Validation checklist

- [ ] `cd dashboard && npm test`
- [ ] `cd dashboard && npx playwright test` (or project script)
- [ ] Light + dark theme spot check
- [ ] Mobile 375×812 drawer + Overview readable
- [ ] No Inter as body; no purple glow aesthetic
