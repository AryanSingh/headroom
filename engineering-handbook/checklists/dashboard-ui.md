---
id: CL-UI-01
kind: checklist
title: Dashboard UI release checklist
chapter: CH-05
controls:
  - id: ENG-UI-001
    requirement: Each critical dashboard journey has deterministic success, loading, empty, error, and authorization-boundary evidence.
    applicability: required for changed customer or operator routes
    procedure: Execute role-based fixture tests for each listed state and verify keyboard access to recovery actions.
    expected_result: Safe state-specific content, no protected stale data, and reachable recovery controls.
    evidence: Test report, trace, screenshot, accessibility output, and fixture revision.
    automation: browser state-matrix suite
    owner: Frontend owner
    frequency: every changed critical journey
    failure_action: block release until state behavior and evidence are corrected
    standards: [W3C-WCAG-2.2, NIST-SSDF-1.1]
---

# Dashboard UI release checklist

- [ ] Test all critical state transitions with deterministic API fixtures.
- [ ] Check role/permission boundaries and clear sensitive cache on sign-out.
- [ ] Verify keyboard, name/role, focus, zoom, and responsive behavior.
