---
id: CL-CLI-01
kind: checklist
title: CLI engineering release checklist
chapter: CH-03
controls:
  - id: ENG-CLI-001
    requirement: Automated CLI invocations complete without an implicit prompt, browser launch, or environment selection.
    applicability: required for commands used by CI, scripts, agents, or operators
    procedure: Run each automation command with stdin closed and an empty temporary HOME under a bounded timeout.
    expected_result: The command exits with documented status and no interactive side effect.
    evidence: Captured stdout, stderr, exit status, timeout record, and source revision.
    automation: non-interactive CLI contract suite
    owner: CLI owner
    frequency: every CLI release
    failure_action: block release until explicit flags or safe failure behavior are added
    standards: [NIST-SSDF-1.1]
  - id: ENG-CLI-002
    requirement: Machine-readable CLI output is parseable and free of human diagnostics.
    applicability: required for commands that offer JSON or another machine format
    procedure: Parse stdout with the documented schema and assert diagnostics are emitted only to stderr.
    expected_result: Valid schema on success and actionable stderr on failure.
    evidence: Parser test report and representative error transcript.
    automation: JSON contract test
    owner: CLI owner
    frequency: every output-contract change
    failure_action: treat as a breaking contract regression
    standards: [NIST-SSDF-1.1]
---

# CLI engineering release checklist

- [ ] Help, version, invalid argument, and missing input have deterministic exit codes.
- [ ] Non-interactive commands are bounded by a timeout and never prompt implicitly.
- [ ] Configuration precedence is documented and tested with flags, environment, profile, and defaults.
- [ ] JSON output parses and diagnostics stay on stderr.
- [ ] Interrupted or retried state mutation has an idempotency or recovery path.
