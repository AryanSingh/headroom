# CutCtx Autonomous Release Execution Framework (v2)

## Mission

Deliver a **commercial-grade, production-ready release of CutCtx** with strict verification, no fake completion states, and enforced evidence-based auditing.

---

# CORE EXECUTION MODEL

Every task follows this loop:

```text
PLAN → IMPLEMENT → VERIFY → RE-TEST → RE-AUDIT → FINALIZE
```

A task is NOT complete until it passes ALL phases.

---

# STATUS MODEL (STRICT)

Every item MUST be one of:

- P0 CRITICAL (blocks release)
- P1 HIGH (must fix before GA)
- P2 MEDIUM (fix if time allows)
- P3 LOW (cleanup)

AND:

- NOT STARTED
- IN PROGRESS
- BLOCKED
- FIXED
- VERIFIED (only after evidence)

---

# EXIT CRITERIA (NO-GO / GO)

## GO CONDITIONS

- Zero P0 CRITICAL issues
- Zero unresolved P1 HIGH issues
- All enterprise flows pass E2E tests
- Security audit passes
- Billing + licensing fully working
- Token benchmark validated
- Branding fully cleaned (CutCtx only)
- Production build clean

## NO-GO CONDITIONS

Any failure in above.

---

# EVIDENCE ENFORCEMENT (MANDATORY)

No task can be marked VERIFIED without:

- logs
- screenshots
- test output
- API responses
- CLI output
- CI results

If no evidence → automatically NOT VERIFIED.

---

# LOOP CONTROL (AUTONOMOUS AGENT RULE)

For every FAILED task:

1. Diagnose root cause
2. Implement fix
3. Run unit/integration tests
4. Run E2E workflow
5. Run regression suite
6. Re-audit affected modules
7. Only then mark FIXED → VERIFIED

Loop until stable.

---

# SEVERITY MATRIX

## P0 CRITICAL
- Billing broken
- Licensing broken
- Security vulnerability
- Cannot login / auth failure
- App unusable

## P1 HIGH
- Broken enterprise flows
- Data corruption risk
- Missing core features
- Major UI flow broken

## P2 MEDIUM
- UI bugs
- minor API issues
- performance issues

## P3 LOW
- cleanup
- refactor
- documentation

---

# PLAYWRIGHT UI AUDIT (MANDATORY)

## Step

Run full UI crawl:

- open every page
- click every button
- fill all forms
- submit workflows

## Verify

- layout correctness
- responsiveness
- CSS issues
- broken modals
- navigation loops
- loading states

## Evidence

- screenshots per page
- console logs
- failed interactions list

---

# CI / AUTOMATION ENFORCEMENT

Before marking RELEASE READY:

- run CI pipeline
- run full test suite
- run lint + typecheck
- run build verification
- run security scan

If CI fails → BLOCKED automatically.

---

# BRANDING LOCK RULE

Search entire repo:

FORBIDDEN STRINGS:
- Headroom
- headroom
- HEADROOM

If found:

→ MUST be replaced with CutCtx
→ MUST re-run full build
→ MUST re-run tests

---

# TOKEN OPTIMIZATION VALIDATION

Measure:

- input tokens
- output tokens
- compression ratio
- savings vs baseline

Rule:

No marketing claim allowed without benchmark proof.

---

# BILLING + LICENSING FLOW (P0)

Must verify end-to-end:

1. user pays
2. webhook triggers
3. license created
4. license delivered
5. activation works
6. usage tracked

Failure at any step = P0

---

# FINAL RELEASE PIPELINE

## Step 1: Full repo scan
## Step 2: Dependency audit
## Step 3: Branding cleanup
## Step 4: Security audit
## Step 5: Billing audit
## Step 6: Licensing audit
## Step 7: UI Playwright audit
## Step 8: E2E workflows
## Step 9: Regression suite
## Step 10: Benchmark validation

---

# FINAL OUTPUT REQUIRED

Generate:

## 1. EXECUTIVE REPORT
- GO / NO-GO decision
- risk summary
- blocker list

## 2. VERIFIED MATRIX
- feature → status → evidence

## 3. ISSUE BACKLOG
- P0 / P1 / P2 / P3 sorted

## 4. FIX LOG
- every change made

## 5. TEST REPORTS
- unit
- integration
- E2E
- UI

---

# FINAL RULE

If evidence is missing → assume FAILURE.

If uncertainty exists → BLOCKED.

No optimistic marking allowed.
