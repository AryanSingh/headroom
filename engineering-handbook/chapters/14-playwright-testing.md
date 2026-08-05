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

The audit applies to local fixture runs, deployed-environment journeys, and the
artifacts both produce. A critical journey is any route that changes money,
identity, tenant scope, approval state, or external communication: checkout,
transfer review, entitlement change, administrative approval, destructive
confirmation, and any AI-assisted flow whose output a user can act on. The audit
is triggered before every release that touches a critical journey and whenever
the browser-test platform, fixture policy, visual baseline, or release gate
changes, because a platform upgrade that changes rendering or timing invalidates
baseline evidence as surely as a product change does.

## Concepts and engineering principles

Prefer semantic locators that express user intent over brittle CSS paths. Test
the state transition and its decision boundary—not implementation internals.
Use deterministic fixtures for known cases, explicit test data for integrations,
and a separate visual baseline review for meaningful appearance changes. A
passing test without an attributable build, browser version, input, and artifact
is weak evidence.

Three principles govern the audit. First, **tests assert user-visible contracts**:
roles, names, states, and outcomes that a customer or administrator can perceive,
so a test still passes when implementation details change and still fails when
the user-facing behavior regresses. Second, **state is declared, not shared**:
each test starts from a known fixture or controlled account, and any shared
service, queued work, or account state is a documented risk that must be bounded
and reproduced on demand. Third, **artifacts are evidence, and evidence is
sanitized**: traces, screenshots, and console output are captured on failure,
retained with attribution, and scanned for credentials, tokens, and customer
content before they leave the test environment.

## Roles and accountability

The frontend owner maintains journey contracts. QA owns coverage, failure
triage, and fixture hygiene. Accessibility reviews keyboard, focus, name, role,
value, and contrast acceptance evidence. Security reviews privileged flows,
tenant boundaries, and artifact redaction. The release owner decides whether
coverage, failures, and approved exceptions meet the promotion gate.

| Role | Owns | Approves | Accountable for |
| --- | --- | --- | --- |
| Frontend owner | Journey contracts, semantic structure, visual baseline | Baseline changes, journey contracts | That user-facing contracts are stable and implemented |
| QA owner | Coverage, fixture registry, failure triage, quarantine policy | Test evidence completeness | That failures are reproducible and triaged |
| Accessibility owner | Keyboard, focus, name, role, value, contrast acceptance | Accessibility exceptions | That required states are operable and named |
| Security owner | Privileged-flow review, tenant boundaries, artifact redaction | Artifact-release approval | That no artifact discloses credentials or customer data |
| Release owner | Promotion gate | Release decision on evidence | That coverage, failures, and exceptions meet the gate |

## Prerequisites and required inputs

Collect a journey inventory, state matrix, threat model, supported viewport and
browser policy, deterministic fixture plan, test-account lifecycle, release
criteria, artifact retention policy, and an accessibility acceptance statement.
Classify any route that changes money, identity, tenant scope, approval state,
or external communication as critical.

Before the audit, confirm the journey inventory is current and the state matrix
names the declared states each critical journey must prove: success, loading,
empty, denied, expired, and recoverable-error. The fixture plan must state how
each state is produced deterministically, which fixtures are versioned, and how
they are recreated after data changes. The browser policy must pin operating
system, viewport, fonts, color profile, and browser version so visual baselines
compare like-for-like.

## Standard operating procedure

1. **Map critical journeys.** For each critical journey, record the business outcome, owner, risk, expected states, and evidence type in the journey inventory. Owner: frontend owner. Threshold: every money, identity, tenant, approval, and external-communication route is classified critical.
2. **Build deterministic fixtures.** Create fixtures that return declared success, loading, empty, denied, expired, and recoverable-error states, with a fixture registry that records version and reproduction steps. Owner: QA owner. Threshold: a failed critical test can be reproduced from the declared fixture without production state.
3. **Author against user-facing contracts.** Use user-facing roles, names, and labels for selectors; require keyboard completion for interactive controls and assert focus order and accessible names for critical controls. Owner: frontend owner.
4. **Run with isolated state and bounded timeouts.** Execute browser tests with isolated data, one worker for shared fixtures, bounded timeouts, and no production credentials. Owner: QA owner.
5. **Capture evidence on failure.** Record traces, screenshots, console output, and browser version on failure unless a release rule requires a baseline artifact; retain the first failure even when a retry passes. Owner: QA owner.
6. **Review visual changes deliberately.** Compare visual changes against an approved baseline at relevant viewport widths and color modes, including empty, error, denial, narrow-screen, dark-mode, and localized states. Owner: frontend owner. Threshold: no baseline update lands without review.
7. **Scan and sanitize artifacts.** Scan fixtures, traces, screenshots, URLs, logs, and browser storage for secrets, authority-bearing data, and customer content before retention. Owner: security owner. Threshold: no artifact with a token, credential, or PII is published.
8. **Triage flake and quarantine.** Give every flake a root cause; quarantine unstable tests with an owner and expiry, and report the quarantine separately from the pass rate. Owner: QA owner.
9. **Gate promotion.** Block promotion on untested critical states, unresolved accessibility findings, unapproved flake rate, or unsafe artifacts, unless an explicit time-bounded exception names the gap and compensating control. Owner: release owner.

### Flake triage decision table

| Observation | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Passes on retry, no input change | Shared state or timing dependency | Inspect first-failure trace and fixture isolation | Isolate fixture; wait on user-visible state, not fixed sleeps |
| Fails in CI, passes locally | Environment drift (fonts, viewport, browser) | Compare pinned browser policy and package lock | Pin OS, viewport, fonts, browser version; rebuild baseline |
| Fails only on shared worker | Test parallelism conflict | Check shared-fixture worker assignment | One worker for shared fixtures; isolated data per test |
| Fails after product change | Deterministic product defect | Reproduce from declared fixture | Fix product or assertion; keep first-failure evidence |
| Intermittent across runs | Nondeterministic fixture data | Check fixture seeding and cleanup | Version fixtures; reset state between runs |

## Worked example

[Product Atlas local visual recovery fixture](../examples/playwright/README.md)
starts a loopback-only static page, uses real headless Chromium, exposes an
accessible evidence-service failure, and proves the retry action is visible
without showing a token. It is deliberately small enough to reproduce offline.

Walk through the expected evidence sequence. The journey is "transfer review":
the user must be able to see that evidence is temporarily unavailable and retry
successfully. The fixture returns the evidence-service failure state; the test
locates the alert by its accessible role, asserts the retry control is visible,
completes the retry by keyboard, and asserts the recovered state. A second
assertion scans the rendered page and the captured screenshot for the support
token and fails the test if any rendering path exposes it. The run records the
fixture version, browser version, command, and result. If the retry control were
not keyboard-operable, the accessibility assertion fails even though the visual
check passes, which is exactly the kind of divergence the audit exists to catch.

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

Automation should enforce the gate, not just run the suite: fail the build when
a critical journey is missing from the release scope, when a baseline image
changed without a review record, when the flake rate exceeds the declared bound,
or when an artifact scan detects a credential. Treat the local fixture run as
the reproducibility check that integration runs cannot provide, and run it
before every critical-flow change.

## Audit prompts

Use [Opus](../prompts/opus/ch14-journey-risk-synthesis.md) to map systemic
journey risk, [Sonnet](../prompts/sonnet/ch14-browser-evidence-review.md) to
review one trace and artifact set, and [Haiku](../prompts/haiku/ch14-ui-test-inventory.md)
to normalize suite inventory.

Use the Opus prompt when the audit spans the journey inventory, fixture plan,
visual baseline, and release gate and you need a consolidated risk statement.
Use the Sonnet prompt to review one critical journey's trace, screenshot, and
fixture evidence end to end, checking that the failure is reproducible and the
artifacts are sanitized. Use the Haiku prompt to normalize the suite inventory
before coverage analysis. Treat model output as a hypothesis to verify against
traces, fixtures, and release records before it becomes a finding.

## Workflow checklist

Run [CL-PLAYWRIGHT-01](../checklists/playwright-testing.md) before changing a
critical browser flow, browser-test platform, fixture, visual baseline, or
release gate.

The checklist controls `ENG-PLAYWRIGHT-001` through `ENG-PLAYWRIGHT-005` cover
deterministic critical-journey evidence, accessibility and artifact safety,
fixture determinism, visual-baseline review, and flake triage.
`ENG-PLAYWRIGHT-003` (fixture determinism) is the control that makes the others
meaningful: without versioned, reproducible fixtures, neither a green run nor a
red run can be attributed to a product behavior.

## Evidence requirements and retention guidance

Retain the source revision, package lock or dependency-resolution evidence,
browser version, command, fixture IDs, test result, timestamp, failure trace,
sanitized screenshot, and approved exception. Do not retain session cookies,
access tokens, production PII, full network payloads, or unredacted browser
storage. Reproduce the failure from a declared fixture before closing a finding.

| Evidence | What to record | Retention | Owner |
| --- | --- | --- | --- |
| Journey inventory | Journey, outcome, owner, risk class, expected states | Life of the journey | Frontend owner |
| Fixture records | Fixture ID, version, seeding and reproduction steps | Life of the fixture plus release evidence | QA owner |
| Run evidence | Source revision, browser version, command, result, timestamp | Release evidence window | QA owner |
| Failure artifacts | First-failure trace, screenshot, console output, sanitized copy | Finding closure plus release window | QA owner |
| Baseline records | Baseline image version, viewport, browser, review approval | Life of the baseline | Frontend owner |
| Exceptions | Missing journey, flake allowance, accessibility exception, expiry | Exception life plus one year | Release owner |

Reproduce every critical failure from a declared fixture before closure. If a
failure cannot be reproduced, it is unresolved even when the next run is green;
record the reproduction command, fixture version, and result.

## Example findings with severity and remediation

**High — UI-ATLAS-14.** The transfer-review error banner was visible but its
retry control could not receive keyboard focus, and a screenshot included a
support token in a hidden details pane. Remediation: use a semantic button,
assert focus order and accessible name, remove token rendering from every state,
and rerun the local fixture plus the affected integration journey.

**High — UI-ATLAS-15.** A critical payment journey passed on the second retry
while the first attempt failed with a deterministic defect; the retry logic
discarded the first-failure trace, so the defect shipped. Remediation: retain
first-failure artifacts, make retry count and first-attempt result part of the
gate, and triage the first failure before accepting the green run.

**Medium — UI-ATLAS-16.** The visual baseline was regenerated automatically
after a font update, which silently accepted a clipped empty state across three
journeys. Remediation: require explicit baseline review with empty, error,
denial, narrow, dark, and localized states, and version baselines with the
browser and font policy that produced them.

## KPIs and domain scorecard

The [Playwright KPI catalog](../scorecards/playwright-kpis.md) measures
critical-journey evidence freshness and flaky-result exposure. Do not reward
test count alone: a green noncritical suite cannot offset an untested critical
state or a result that cannot be reproduced. Review `KPI-PLAYWRIGHT-001` and
`KPI-PLAYWRIGHT-002` at every release candidate and weekly, and add
`KPI-PLAYWRIGHT-003` (critical failure reproducibility) to the weekly review,
because a failure that cannot be reproduced from declared fixtures is
unresolved even when the next run is green.

## Common failure patterns and diagnostic guidance

- Selectors target generated classes, duplicate text, or incidental layout rather than a stable accessible contract.
- Tests share accounts or queued work and pass or fail according to timing instead of declared inputs.
- Retry logic masks a deterministic product defect and reports a green attempt without retaining the first failure.
- Visual baselines change automatically without review of empty, error, denial, narrow-screen, dark-mode, or localized states.
- Browser artifacts contain credentials, customer content, or URLs with authority-bearing query parameters.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Tests break on harmless markup change | Selectors target generated classes or layout | Inspect selector against accessible contract | Use role, name, and label locators |
| Tests pass or fail by timing | Shared accounts or queued work | Check fixture isolation and worker assignment | Declared fixtures; one worker for shared state |
| Green on retry, defect shipped | Retry masks first failure | Verify first-failure trace retained and triaged | Gate on first-attempt result; retain first-failure evidence |
| Baseline silently accepts regressions | Auto-regenerated baseline | Review baseline diff for state coverage | Explicit review; version baseline with browser policy |
| Artifact contains a token | Token rendered in DOM or URL | Scan traces, screenshots, storage, and URLs | Remove token from all states; scan before retention |

## Exit criteria

Exit when each critical journey has an accountable owner, deterministic test
data or a controlled integration environment, stable user-facing assertions,
evidence of required states and keyboard interaction, bounded flake policy,
sanitized artifacts, and an approved release decision.

| Criterion | Evidence | Passes when |
| --- | --- | --- |
| Journey owned and mapped | Journey inventory with owner, risk, states | Every critical route classified and covered |
| Deterministic state | Fixture registry with versions and repro steps | Failure reproduces from declared inputs |
| Stable assertions | Semantic locator and keyboard results | Tests assert user-visible contracts |
| Required states evidenced | Run results for success, loading, empty, denied, expired, error | All declared states proven for critical journeys |
| Flake bounded | Flake report and quarantine register | Rate within bound; quarantines owned with expiry |
| Artifacts safe | Redaction scan results | No credential, token, or customer content retained |
| Release gated | Release decision with exceptions | No untested critical state, unsafe artifact, or unapproved flake |

## Related runbooks, controls, examples, and templates

Use the Playwright checklist, verification-plan template, finding template,
release-decision template, threat-model template, and incident-review template.
Escalate browser test failures that expose cross-tenant content, unintended
authority, or security-sensitive state through the incident response runbook.

> **Application note — Cutctx.** For a token-compression proxy product, the
> browser-test audit applies to configuration and admin consoles that change
> routing presets and compatibility aliases: those routes change money and
> behavior, so they are critical journeys with the same fixture, baseline, and
> artifact requirements as checkout flows. The deterministic-fixture control
> applies to preset-rendering tests, which must pin the engine, model, and
> preset version to reproduce token-count assertions, and the artifact scan must
> cover URLs and storage for tokens, since the trap in
> `docs/handoff-2026-07-28.md` showed a "lossless" label whose measured behavior
> differed from the default routing — a visual-state assertion that would have
> caught the divergence only if the fixture pinned the real default.
