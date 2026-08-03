---
id: KPI-CAT-PLAYWRIGHT-01
kind: kpi-catalog
title: Playwright and visual testing KPI catalog
chapter: CH-14
kpis:
  - id: KPI-PLAYWRIGHT-001
    name: Critical journey evidence freshness
    decision: Decide whether release-critical browser evidence is current enough to support promotion.
    calculation: Count critical journeys with a passing attributable result from the candidate revision within the release evidence window divided by all declared critical journeys, multiplied by 100.
    source: Journey inventory, CI result records, revision metadata, and release evidence register.
    frequency: every release candidate
    owner: Release owner
    target: 100 percent
    warning: below 100 percent
    distortions: Teams can lower the denominator by omitting journeys or labeling a critical flow noncritical.
    anti_gaming: Require product, security, and QA review of the journey classification and reconcile it with incident history and change scope.
    interpretation: A score below target blocks release unless an explicit time-bounded exception names the missing journey and compensating control.
  - id: KPI-PLAYWRIGHT-002
    name: Critical browser-test flake rate
    decision: Decide whether browser evidence is trustworthy enough for release gating and failure triage.
    calculation: Count critical test runs that pass only after retry or show inconsistent outcomes on unchanged inputs divided by all critical test executions, multiplied by 100.
    source: CI retry metadata, trace records, fixture versions, and test result history.
    frequency: weekly and before release
    owner: QA owner
    target: at most 1 percent
    warning: above 2 percent or any repeated critical-flow flake
    distortions: Disabling retries or quarantining unstable tests can make the rate look lower while coverage disappears.
    anti_gaming: Report quarantined and skipped critical tests separately; require root cause and expiry for every quarantine.
    interpretation: A high rate means a green run has reduced evidentiary value; repair isolation, waiting conditions, or the product defect before relying on the suite.
---

# Playwright and visual testing KPI catalog

Review these measures with the journey inventory and release decision. They are
evidence-quality measures, not productivity targets.
