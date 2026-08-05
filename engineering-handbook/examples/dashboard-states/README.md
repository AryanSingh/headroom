---
id: EX-CH05-DASHBOARD-STATES
kind: worked-example
chapter: CH-05
standards: [W3C-WCAG-2.2, NIST-SSDF-1.1]
preconditions: [Atlas Revenue route, deterministic API fixtures, analyst and expired-session roles]
placement: engineering-handbook/examples/dashboard-states
dependencies: [browser test runner, local fixture server, accessibility scanner]
invocation: Run the revenue route with delayed, empty, 401, and 503 fixture responses.
expected_output: Each state has named controls, correct status/copy, safe data clearing, and keyboard-operable recovery.
failure_output: Previous revenue total remains visible after 401 or retry cannot be reached by keyboard.
interpretation: Cached protected data or inaccessible recovery blocks release.
remediation: Clear cache on auth transition, correct state semantics, and add a deterministic regression test.
cleanup: Delete generated screenshots/traces containing fixture identifiers.
---

# Atlas Revenue dashboard state matrix

| Fixture | Expected user outcome |
| --- | --- |
| Delayed response | Named loading state; no stale sensitive total shown as current. |
| Empty data | Clear explanation and reachable next action. |
| 401 expired session | Cached total cleared; sign-in action receives focus. |
| 503 provider error | Retry action and status message are keyboard accessible. |
