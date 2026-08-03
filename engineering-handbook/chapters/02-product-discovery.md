---
id: CH-02
kind: chapter
title: Product Discovery and Capability Mapping
purpose: Establish an evidence-backed map of product capabilities, paths, dependencies, ownership, and verification status.
audience: [Staff engineers, product engineers, audit leads, platform engineers, engineering managers]
scope: Repository, runtime, route, command, data, provider, feature-flag, enterprise, and ownership discovery.
applicability: Use before an audit, major release, integration review, modernization program, or security assessment.
owners: [Discovery lead, service owners, product owner]
inputs: [Repository access, runtime configuration, deployment inventory, product brief, telemetry and test locations]
outputs: [Capability map, evidence register, unknowns register, ownership map, verification plan]
dependencies: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
standards: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
---

# Product Discovery and Capability Mapping

## Purpose, audience, scope, and applicability

Discovery turns an unfamiliar system into a reviewable map. Its deliverable is
not a prose overview; it is a set of capabilities linked to user value, entry
points, owners, data classes, dependencies, operational signals, and evidence.
Use it before asking whether the product is secure, reliable, complete, or
ready to release. A capability that is absent from the map remains an explicit
unknown rather than a presumed non-risk.

## Concepts and engineering principles

A capability is a user- or operator-observable outcome, such as “an account
owner exports an invoice report,” not a folder or a class. One capability can
cross a CLI, API, web UI, queue, provider, and database. Record both configured
behavior and observed behavior: a feature flag may say a provider is enabled
while a runtime trace proves it is unreachable. Model boundaries first, then
code ownership. This prevents a directory tree from becoming a false product
map.

## Roles and accountability

The discovery lead maintains taxonomy and evidence quality. Product owners
define intended user outcomes and business priority. Service owners explain
runtime paths and approve ownership assignments. Security and reliability
reviewers classify data and operational dependencies. The audit lead converts
unknowns and high-risk paths into verification work. No reviewer may close an
unknown on hearsay; closure requires evidence or a documented decision to defer.

## Prerequisites and required inputs

Collect the product brief, primary user journeys, repository revision, build and
deployment manifests, configuration and feature-flag sources, public routes or
commands, data stores, provider integrations, ownership records, current test
locations, dashboards, and incident history. Obtain a safe local environment
or read-only production inventory. Redact tokens and customer data from records.

## Standard operating procedure

1. Define a capability taxonomy: customer journeys, operator workflows,
   administration, integrations, data lifecycle, and recovery paths.
2. List declared entry points: UI routes, API operations, CLI commands, jobs,
   webhooks, scheduled tasks, SDK calls, and support tooling.
3. Trace each high-value entry point through authorization, state mutation,
   persistence, queues, external providers, observability, and recovery.
4. Record each capability row with owner, data classification, feature flag,
   dependencies, tests, runtime signal, and verification status.
5. Compare configuration to runtime evidence. Mark a difference as configured,
   observed, unreachable, disabled, or unknown; do not collapse these states.
6. Interview owners only after the initial map exists. Ask them to validate
   paths and resolve conflicts with links to source or operational evidence.
7. Prioritize unknowns by impact, exposure, change frequency, and reversibility.
   Create a verification plan for every high-risk unknown.
8. Publish the versioned map and schedule refresh at material change, release,
   or a stated cadence.

## Worked example

The linked [Atlas Subscription capability-map example](../examples/capability-map/README.md)
maps a self-service plan upgrade. The path begins in the dashboard, calls the
billing API, selects a payment provider, writes a subscription record, emits an
event, and exposes an operator recovery action. The example finds a documented
but untested retry worker, which becomes a verification gap rather than a pass.

## Automation examples

Start with deterministic inventory commands. A repository review might use:

```shell
rtk rg --files -g '!*node_modules*' -g '!*.lock' | sort
rtk rg -n "(route|router|command|webhook|feature flag|provider)" src docs tests
rtk pytest tests/inventory -q
```

Automate collection into a CSV or JSON capability seed, but require a human to
resolve ownership and user-value labels. Source search discovers candidates; it
does not prove a path is reachable in a deployed environment.

## Audit prompts

Use the linked [Opus](../prompts/opus/ch02-system-map.md),
[Sonnet](../prompts/sonnet/ch02-capability-review.md), and
[Haiku](../prompts/haiku/ch02-inventory-normalization.md) prompts. They produce
respectively a cross-system path model, a focused capability review, and a
normalized inventory. They must not be used as evidence without source links.

## Workflow checklist

Apply [CL-DISCOVERY-01](../checklists/master-checklist.md) during discovery.
The control rows force entry-point, owner, data, dependency, runtime, and test
evidence into the same review rather than treating a README as sufficient.

## Evidence requirements and retention guidance

Keep the map revision, repository commit, configuration snapshot, command
output, source links, owner confirmations, runtime observation window, test
reports, and unresolved-unknowns list. Refresh or invalidate evidence when a
route, provider, permission model, feature flag, data store, or owner changes.

## Example findings with severity and remediation

**Important — MAP-ATLAS-01.** The billing retry worker was enabled in the
deployment manifest but no current test, alert, or named owner covered its
duplicate-charge failure path. Remediation: assign a service owner, add an
idempotency/retry contract test, create a failure alert, and update the map with
the evidence links. The capability remains unknown until the retest is recorded.

## KPIs and domain scorecard

The [discovery KPI catalog](../scorecards/discovery-kpis.md) measures unknown
capability rate, ownership completeness, runtime-evidence freshness, and
critical-path test coverage. The scorecard does not allow a high average to
offset an unknown critical authorization or recovery path.

## Common failure patterns and diagnostic guidance

- The map mirrors packages instead of user outcomes. Reframe each row as an
  observable outcome and add its entry point.
- A declared integration has no observed runtime evidence. Keep it “configured”
  or “unreachable”; do not call it active.
- One team owns an API but no one owns the end-to-end journey. Assign both
  service and capability ownership.
- A feature flag hides a path from normal testing. Include flag state, rollout
  cohort, and a safe test environment in the row.

## Exit criteria

Discovery exits when every high-priority capability has an owner, entry point,
data/dependency classification, verification status, and linked evidence; when
critical unknowns have a named next action; and when the accountable product and
engineering owners have reviewed the map revision.

## Related runbooks, controls, examples, and templates

Use the evidence register, verification plan, audit report, and finding record
templates. Related chapters add CLI, desktop, UI, API, routing, memory, and
operational-depth mappings to this baseline taxonomy.
