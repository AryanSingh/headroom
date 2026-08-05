---
id: CH-04
kind: chapter
title: Desktop Engineering and Audit
purpose: Verify desktop applications across install, upgrade, IPC, local data, permissions, and recovery paths.
audience: [Desktop engineers, QA, security, release engineers]
scope: Packaging, update lifecycle, IPC, local storage, OS permissions, crash recovery, and diagnostics.
applicability: Native, Electron, and hybrid desktop applications.
owners: [Desktop owner, release owner, security owner]
inputs: [installer, update manifest, local-data schema, IPC inventory, test device matrix]
outputs: [desktop verification evidence, findings, recovery decision]
dependencies: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
---

# Desktop Engineering and Audit

## Purpose, audience, scope, and applicability

Desktop software crosses a trust boundary at installation, then retains state
after the service, browser, or user session changes. Audit the full lifecycle:
install, first launch, permission grant, update, offline behavior, crash,
restart, and uninstall. Treat local state and IPC as product interfaces.

## Concepts and engineering principles

Separate privileged main-process operations from renderer or plugin requests.
Validate IPC message shape and authorization at the receiving boundary. Version
local schemas and make upgrades resumable. An updater is a deployment system:
it needs provenance, rollback criteria, disk-space behavior, and user-visible
recovery guidance.

## Roles and accountability

Desktop owners maintain IPC and state contracts. Release owners approve package
provenance and staged update evidence. Security owners review privilege and
local-data exposure. Support owners keep recovery instructions current.

## Prerequisites and required inputs

Obtain signed installers, version/update manifests, supported OS matrix, IPC
routes, permission inventory, storage locations, migration history, and clean
and upgrade test devices or VMs.

## Standard operating procedure

1. Install on a clean user profile and capture signature, version, install path,
   permissions, first-launch logs, and outbound connection policy.
2. Trace each privileged IPC operation from caller to authorization, validation,
   filesystem/network action, and audit signal.
3. Test denied, revoked, and malformed permission or IPC states.
4. Upgrade from supported prior versions with realistic local data; interrupt
   download, migration, and first launch to prove recovery.
5. Exercise offline, low-disk, corrupt-cache, and forced-crash behavior.
6. Uninstall and confirm documented retention/deletion behavior for local data.

## Worked example

[Atlas Notes desktop upgrade](../examples/desktop-upgrade/README.md) interrupts a
local-schema migration and verifies that restart either resumes safely or
restores the prior readable state.

## Automation examples

Use disposable OS profiles and scripted install/update fixtures. Capture version,
exit code, local database checksum, and structured logs. A test that only opens
the window does not prove a usable update path.

## Audit prompts

Use [Opus](../prompts/opus/ch04-desktop-risk.md),
[Sonnet](../prompts/sonnet/ch04-ipc-review.md), and
[Haiku](../prompts/haiku/ch04-desktop-inventory.md) for lifecycle synthesis,
focused IPC evidence review, and mechanical inventory normalization.

## Workflow checklist

Run [CL-DESKTOP-01](../checklists/desktop-engineering.md) for install, upgrade,
and release approval.

## Evidence requirements and retention guidance

Keep package hashes, signing evidence, OS/version matrix, redacted logs,
storage checksums, migration reports, permission screenshots, and recovery test
output. Do not retain real user profiles or tokens.

## Example findings with severity and remediation

**Important — DESK-ATLAS-01.** An interrupted migration deleted the old index
before the replacement was durable. Remediation: use a journaled copy/swap,
retain a backup until health checks pass, and add interruption tests.

## KPIs and domain scorecard

The [desktop KPI catalog](../scorecards/desktop-kpis.md) tracks upgrade success,
crash-recovery success, unsupported-OS detection, and privileged IPC coverage.

## Common failure patterns and diagnostic guidance

- Renderer input reaches filesystem IPC without main-process validation.
- A new local schema has no downgrade or recovery behavior.
- Auto-update succeeds in labs but fails under low disk or corporate proxy.
- Uninstall wording conflicts with actual retained state.

## Exit criteria

Exit when clean install, update, interruption, recovery, permission denial, and
uninstall behavior have evidence on supported platforms and blocking findings
are resolved or explicitly accepted.

## Related runbooks, controls, examples, and templates

Use the verification plan, finding record, and release decision templates with
the desktop upgrade example and related release/rollback runbooks.
