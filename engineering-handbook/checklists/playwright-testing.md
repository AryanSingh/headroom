---
id: CL-PLAYWRIGHT-01
kind: checklist
title: Playwright and visual testing release checklist
chapter: CH-14
standards: [NIST-SSDF-1.1, OWASP-WSTG-4.2, W3C-WCAG-2.2, OWASP-ASVS-5.0.0]
controls:
  - id: ENG-PLAYWRIGHT-001
    requirement: Every critical browser journey must use deterministic inputs, stable user-facing assertions, and recorded build/browser/fixture evidence before release.
    applicability: required for identity, tenant, payment, approval, destructive, administrative, and externally visible browser journeys
    procedure: Map critical journeys to owners and expected states; run them against isolated fixtures or controlled accounts; record source revision, browser version, command, result, and sanitized failure artifacts.
    expected_result: A reviewer can reproduce each release-critical result from declared inputs without production credentials or shared hidden state.
    evidence: journey inventory, fixture IDs, source revision, browser version, command output, result record, and sanitized trace or screenshot
    automation: critical browser journey gate
    owner: QA owner
    frequency: every release affecting a critical journey and quarterly fixture review
    failure_action: block the affected release, preserve sanitized evidence, remove nondeterministic state, repair the assertion or product behavior, and rerun the full critical-path suite
    standards: [NIST-SSDF-1.1, OWASP-WSTG-4.2]
  - id: ENG-PLAYWRIGHT-002
    requirement: Browser tests and retained visual artifacts must verify accessible recovery behavior and exclude secrets, authority-bearing data, and unnecessary customer content.
    applicability: required for all authenticated, error, support, administrative, and customer-data browser states
    procedure: Exercise success and failure states using semantic roles and keyboard interaction; scan fixtures, traces, screenshots, URLs, logs, and browser storage for sensitive detail before retention.
    expected_result: Required controls are operable and named, recovery instructions are available, and retained artifacts contain only approved sanitized evidence.
    evidence: accessibility assertions, keyboard result, artifact-redaction review, screenshot or trace reference, and exception approval where applicable
    automation: accessibility and artifact-sanitization gate
    owner: Frontend owner
    frequency: each critical-flow change, each visual baseline update, and before release
    failure_action: stop artifact publication and promotion, revoke exposed credentials if any, redact or delete unsafe evidence, remediate the UI, and rerun the browser suite
    standards: [W3C-WCAG-2.2, OWASP-ASVS-5.0.0]
---

# Playwright and visual testing release checklist

- [ ] Identify critical user journeys and their business, security, and accessibility outcome.
- [ ] Exercise declared success, loading, empty, denied, expired, and recoverable-error states.
- [ ] Use stable semantic locators and complete interactive flow by keyboard where required.
- [ ] Run with isolated data, bounded timeouts, and no production credentials.
- [ ] Retain attributable, sanitized failure evidence and review baseline changes deliberately.
- [ ] Block release for an untested critical state, unapproved flake rate, unsafe artifact, or unresolved accessibility finding.
