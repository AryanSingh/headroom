---
id: CH-14
kind: chapter
title: Playwright and Visual Testing Engineering Audit
purpose: Build and assess browser automation that proves critical user journeys, visible states, accessibility boundaries, and release evidence deterministically.
audience: [frontend engineers, QA engineers, security engineers, accessibility specialists, SREs, engineering leaders]
scope: Local and deployed browser flows, test isolation, visual-state assertions, accessibility evidence, sensitive-data handling, artifacts, retries, and release gating.
applicability: Dashboards, customer portals, desktop webviews, administration consoles, checkout flows, embedded integrations, and AI-assisted user interfaces.
owners: [Frontend owner, QA owner, accessibility owner, security owner, release owner]
inputs: [journey inventory, state matrix, test accounts, fixture policy, browser configuration, accessibility acceptance criteria, release risks]
outputs: [browser test evidence, visual-state findings, accessibility exceptions, release gate decision, and remediation plan]
dependencies: [OWASP-WSTG-4.2, W3C-WCAG-2.2, NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
standards: [OWASP-WSTG-4.2, W3C-WCAG-2.2, NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
---

# Playwright and Visual Testing Engineering Audit

## Purpose, audience, scope, and applicability

Browser tests are release evidence, not a decorative screenshot. Audit whether
they exercise critical outcomes through stable, accessible interfaces; isolate
state; make failures diagnosable; and prevent test artifacts from disclosing
secrets or customer data. Apply this chapter wherever a browser or webview can
change a business, security, or operational outcome.

## Concepts and engineering principles

Prefer semantic locators that express user intent over brittle CSS paths. Test
the state transition and its decision boundary—not implementation internals.
Use deterministic fixtures for known cases, explicit test data for integrations,
and a separate visual baseline review for meaningful appearance changes. A
passing test without an attributable build, browser version, input, and artifact
is weak evidence.

## Roles and accountability

The frontend owner maintains journey contracts. QA owns coverage, failure
triage, and fixture hygiene. Accessibility reviews keyboard, focus, name, role,
value, and contrast acceptance evidence. Security reviews privileged flows,
tenant boundaries, and artifact redaction. The release owner decides whether
coverage, failures, and approved exceptions meet the promotion gate.

## Prerequisites and required inputs

Collect a journey inventory, state matrix, threat model, supported viewport and
browser policy, deterministic fixture plan, test-account lifecycle, release
criteria, artifact retention policy, and an accessibility acceptance statement.
Classify any route that changes money, identity, tenant scope, approval state,
or external communication as critical.

## Standard operating procedure

1. Map each critical journey to a business outcome, owner, risk, expected state, and evidence type.
2. Create fixtures that return declared success, loading, empty, denied, expired, and recoverable-error states.
3. Use user-facing roles, names, and labels; require keyboard completion for interactive controls.
4. Run browser tests with isolated state, bounded timeouts, one worker for shared fixtures, and no production credentials.
5. Capture traces, screenshots, console output, and browser version only on failure unless a release rule requires a baseline artifact.
6. Review visual changes against an approved baseline at relevant viewport widths and color modes.
7. Gate promotion on critical-path outcomes, accessibility findings, known flake rate, approved exceptions, and remediation ownership.

## Worked example

[Product Atlas local visual recovery fixture](../examples/playwright/README.md)
starts a loopback-only static page, uses real headless Chromium, exposes an
accessible evidence-service failure, and proves the retry action is visible
without showing a token. It is deliberately small enough to reproduce offline.

## Automation examples

```shell
cd engineering-handbook/examples/playwright
CI=true npm test

# Run the handbook's offline package-contract check.
python3 ../../automation/check_examples.py ../..
```

```javascript
await page.getByRole("button", { name: "Simulate unavailable evidence" }).click();
await expect(page.getByRole("alert")).toContainText("temporarily unavailable");
```

## Audit prompts

Use [Opus](../prompts/opus/ch14-journey-risk-synthesis.md) to map systemic
journey risk, [Sonnet](../prompts/sonnet/ch14-browser-evidence-review.md) to
review one trace and artifact set, and [Haiku](../prompts/haiku/ch14-ui-test-inventory.md)
to normalize suite inventory.

## Workflow checklist

Run [CL-PLAYWRIGHT-01](../checklists/playwright-testing.md) before changing a
critical browser flow, browser-test platform, fixture, visual baseline, or
release gate.

## Evidence requirements and retention guidance

Retain the source revision, package lock or dependency-resolution evidence,
browser version, command, fixture IDs, test result, timestamp, failure trace,
sanitized screenshot, and approved exception. Do not retain session cookies,
access tokens, production PII, full network payloads, or unredacted browser
storage. Reproduce the failure from a declared fixture before closing a finding.

## Example findings with severity and remediation

**High — UI-ATLAS-14.** The transfer-review error banner was visible but its
retry control could not receive keyboard focus, and a screenshot included a
support token in a hidden details pane. Remediation: use a semantic button,
assert focus order and accessible name, remove token rendering from every state,
and rerun the local fixture plus the affected integration journey.

## KPIs and domain scorecard

The [Playwright KPI catalog](../scorecards/playwright-kpis.md) measures
critical-journey evidence freshness and flaky-result exposure. Do not reward
test count alone: a green noncritical suite cannot offset an untested critical
state or a result that cannot be reproduced.

## Common failure patterns and diagnostic guidance

- Selectors target generated classes, duplicate text, or incidental layout rather than a stable accessible contract.
- Tests share accounts or queued work and pass or fail according to timing instead of declared inputs.
- Retry logic masks a deterministic product defect and reports a green attempt without retaining the first failure.
- Visual baselines change automatically without review of empty, error, denial, narrow-screen, dark-mode, or localized states.
- Browser artifacts contain credentials, customer content, or URLs with authority-bearing query parameters.

## Exit criteria

Exit when each critical journey has an accountable owner, deterministic test
data or a controlled integration environment, stable user-facing assertions,
evidence of required states and keyboard interaction, bounded flake policy,
sanitized artifacts, and an approved release decision.

## Related runbooks, controls, examples, and templates

Use the Playwright checklist, verification-plan template, finding template,
release-decision template, threat-model template, and incident-review template.
Escalate browser test failures that expose cross-tenant content, unintended
authority, or security-sensitive state through the incident response runbook.
