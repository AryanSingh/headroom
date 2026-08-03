---
id: CH-12
kind: chapter
title: Release Engineering Audit
purpose: Build and assess release systems that create attributable, reproducible, reversible, and observable changes from approved source to production.
audience: [Release engineers, platform engineers, SREs, security engineers, QA, engineering leaders]
scope: Build provenance, test gates, artifact promotion, configuration, change approval, deployment, rollback, verification, and release evidence.
applicability: Services, CLIs, desktop applications, dashboards, infrastructure, data changes, and AI model or policy releases.
owners: [Release owner, service owner, security owner, SRE owner]
inputs: [approved change, source revision, dependency lockfile, test evidence, artifact manifest, deployment plan, rollback plan]
outputs: [release decision, provenance record, deployment evidence, rollback readiness result]
dependencies: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OTEL-SEMCONV-1.43.0]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OTEL-SEMCONV-1.43.0]
---

# Release Engineering Audit

## Purpose, audience, scope, and applicability

A release is a controlled production change, not merely a successful build. Audit whether source, dependencies, configuration, artifacts, approvals, deployment observations, and rollback actions can be connected without ambiguity.

The audit applies to every production-facing promotion: services, CLIs, desktop applications, dashboards, infrastructure, data and schema changes, and AI model or policy releases. It also applies to changes in the release system itself, because a pipeline that silently stops collecting evidence invalidates every release that flows through it. The release owner is accountable for the gate and the evidence package; the audit asks one question of every promotion: could a competent engineer reconstruct, from retained records alone, exactly what changed, who approved it, what was tested, what was deployed, what was observed, and how it would be reversed?

## Concepts and engineering principles

Promote immutable artifacts rather than rebuilding per environment. Separate code, configuration, policy, and data changes while linking them in one release record. A rollback must be executable under degraded conditions and must state whether it reverses binaries, configuration, schema, traffic, or customer-visible state.

Four principles govern the audit. First, **provenance is the release**: the source revision, dependency lockfile, build inputs, and artifact digest are bound into one record at freeze time, and promotion moves that record, never a rebuild. Second, **environments differ by declaration, not by drift**: staging and production run the same artifact and the same configuration sources, with intentional differences listed, approved, and audited, so a green staging result means something about production. Third, **rollout is an experiment with stop criteria**: traffic, error rate, latency, and business correctness are compared against a baseline, and a declared breach stops the rollout. Fourth, **evidence is collected before the gate closes**: telemetry queries, results, and rollback rehearsals are retained as part of the release record, not reconstructed after an incident.

## Roles and accountability

The release owner owns the gate and evidence package. The service owner owns functional and compatibility acceptance. SRE owns deployment health, traffic control, and rollback execution. Security owns supply-chain and change-control review. QA owns scenario coverage; the incident commander directs emergency changes when activated.

| Role | Owns | Approves | Accountable for |
| --- | --- | --- | --- |
| Release owner | Release record, gate, evidence package | Promotion decisions, emergency-change retrospective | One attributable record per production change |
| Service owner | Functional and compatibility acceptance | Candidate acceptance | That shipped behavior matches the approved change |
| SRE owner | Deployment health, traffic control, rollback execution | Rollout plan, stop criteria, rehearsal results | That rollout stops and rolls back safely |
| Security owner | Supply-chain review, change control, signing | Provenance and signing verification | That artifacts are attributable and tamper-evident |
| QA owner | Scenario coverage, release verification | Test-evidence completeness | That required gates ran against the candidate |
| Incident commander | Emergency change direction | Emergency approvals when activated | That emergency changes produce retrospective evidence |

## Prerequisites and required inputs

Collect the approved change record, source revision, dependency lockfile, build identity, artifact digest, SBOM or equivalent dependency evidence, test results, migration assessment, feature-flag plan, deployment target, telemetry queries, communication plan, and rollback criteria.

Confirm each input is current and bound to the candidate before the audit proceeds. The artifact digest must be produced from the declared build inputs, not from a tag that can move. The dependency lockfile must match the build environment, and the SBOM or dependency evidence must cover runtime dependencies, not only the direct ones. The migration assessment must name the schema or data steps, their direction of change, and their reversibility, because a migration that cannot be reversed changes the rollback strategy. The telemetry queries must be defined before deployment so the rollout compares like-for-like against a captured baseline.

## Standard operating procedure

1. **Freeze the release candidate.** Record the source revision, dependencies, build inputs, artifact digest, and build identity in the release record. Owner: release owner. Threshold: the digest is immutable and reproducible from the declared inputs; rebuilding at promotion is a blocking failure.
2. **Run required gates against the candidate.** Execute unit, integration, security, migration, accessibility, and customer-journey gates on the exact artifact being promoted. Threshold: every gate result carries the candidate digest; a green result from another revision is not evidence. Timeline: gates must complete before the rollout window opens.
3. **Verify configuration and secret injection.** Confirm configuration and secrets are referenced by approved mechanism and never appear in build logs, release evidence, or artifacts. Owner: security owner.
4. **Assess migration and data change.** Review the migration plan for order, reversibility, and dependency on new code. If the migration cannot be reversed with the same tooling, the rollback plan must state the forward-fix strategy instead. Owner: service owner.
5. **Promote the same artifact through staged environments.** Progress from staging to canary to production with explicit approvals, traffic limits, and observable health criteria per stage. Record each stage decision.
6. **Execute the canary or bounded rollout.** Compare client outcomes, error rate, latency, security signals, and business correctness against the captured baseline. Owner: SRE owner. Threshold: breach of any declared stop criterion halts the rollout.
7. **Stop or roll back on breach.** When a criterion is breached, record the reason, the action taken (halt, reduce traffic, roll back), and the customer impact. Execute the component-complete rollback if required, and verify that accepted work is neither lost nor duplicated.
8. **Verify post-deployment.** Run post-deployment checks, confirm release communication, and retain evidence. Assign follow-up owners for any residual items before closing the release record. Timeline: closure within one business day of the rollout completing or stopping.

### Rollout decision table

| Observation during rollout | Likely meaning | Decision | Owner |
| --- | --- | --- | --- |
| Error rate breaches threshold | Defect or dependency failure in candidate | Halt at threshold, preserve telemetry, triage before resuming | SRE owner |
| Latency rises without errors | Performance or scaling regression | Reduce traffic share, capture profile, decide rollback vs. fix-forward | SRE owner |
| Business correctness diverges | Logic or data-semantics regression | Roll back to prior artifact, reconcile outcomes | Service owner |
| Security signal appears | Authorization, injection, or secret exposure | Stop rollout, isolate, invoke incident process | Security owner |
| All signals within bounds | Candidate healthy at current share | Continue to next share with same stop criteria | Release owner |

## Worked example

[Product Atlas release engineering evidence](../examples/release-engineering/README.md) promotes a tenant-export service through a 5% canary, blocks a schema-incompatible worker, and rolls back the immutable artifact without reversing completed exports.

The example exercises the full evidence chain. The candidate `sha256:atlas-export-2026-09-18` is built from the frozen revision with the pinned dependency lockfile, and the SBOM is recorded. Staging gates pass against the exact digest. The rollout opens at 5% traffic; the canary telemetry compares export completion rate, error rate, and queue depth against the baseline captured the previous week. A worker running an older schema version rejects the new payloads, so the error rate breaches the declared threshold. The rollout halts at 5%, the release record captures the telemetry query and result, and the decision is rollback rather than forward-fix because the schema change is not yet reversible. The rollback restores the prior artifact and configuration revision, while the queue reconciliation confirms that completed exports were not re-run and pending exports were retried under the prior version. The release record closes with the rollback log, the outcome-integrity query, the communication, and a follow-up finding for the worker fleet upgrade.

## Automation examples

```bash
atlasctl release verify --artifact sha256:atlas-export-2026-09-18 --environment staging --format json
atlasctl release promote --artifact sha256:atlas-export-2026-09-18 --environment production --traffic-percent 5
atlasctl release rollback --release rel-atlas-2026-09-18 --reason "canary-error-budget-breach"
```

Automation must fail closed on evidence gaps: refuse to promote when the deployed digest differs from the tested digest, when a gate result is missing, or when the telemetry baseline is older than the configured window. Every promotion and rollback command should emit a machine-readable record that the release ledger ingests, so the automation itself produces the evidence it enforces.

## Audit prompts

Use [Opus](../prompts/opus/ch12-release-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch12-release-evidence-review.md), and [Haiku](../prompts/haiku/ch12-release-inventory.md) for release-chain risk synthesis, one candidate's evidence review, and release-record normalization.

Use the Opus prompt when the audit spans the pipeline, signing, environments, and rollback mechanisms and you need a consolidated risk statement. Use the Sonnet prompt to review one candidate's evidence package end to end, checking that digest, tests, approvals, and deployment observations belong to the same release. Use the Haiku prompt to normalize release records from inconsistent sources. Treat every model claim as a hypothesis to verify against the release ledger before it becomes a finding.

## Workflow checklist

Run [CL-RELENG-01](../checklists/release-engineering.md) for every production promotion and for any change to deployment policy, pipeline, signing, environment configuration, migration, or rollback mechanism.

The checklist controls `ENG-RELENG-001` through `ENG-RELENG-005` cover provenance, rollback, environment parity, canary execution, and release-notes accuracy. `ENG-RELENG-003` (environment parity) is the control most often weakened by "just this once" manual configuration; run it whenever staging and production configuration sources diverge, because a staging green means little against a production that never matched it.

## Evidence requirements and retention guidance

Retain change approval, source revision, dependency and artifact digest, test run IDs, deployment target, configuration revision, traffic decision, telemetry query/result, rollback result, and owner attestations. Retain references and hashes rather than secrets, customer content, or full production logs.

| Evidence | What to record | Retention | Owner |
| --- | --- | --- | --- |
| Release record | Change approval, source revision, dependency lockfile, artifact digest, build identity | Life of service plus audit window | Release owner |
| Test evidence | Gate run IDs, candidate digest, pass/fail, environment | Release audit window (two years or more) | QA owner |
| Deployment evidence | Target, configuration revision, traffic decision per stage, timestamps | Release audit window | SRE owner |
| Telemetry results | Baseline and canary queries, results, breach timestamps | Release audit window; queries in source control | SRE owner |
| Rollback evidence | Reason, action, rollback log, outcome-integrity result | Release audit window plus incident linkage | SRE owner |
| Communications | Release notes, known issues, customer/operator notices | Life of release notes plus one year | Release owner |

Secrets, customer content, and full production logs are never part of the release evidence set. Emergency changes produce a retrospective record with the same fields as a normal release within an agreed window; an emergency bypass is a process finding, not a permanent evidence exemption.

## Example findings with severity and remediation

**Critical — REL-ATLAS-01.** Production rebuilt from the same tag with a changed dependency resolution, so the tested artifact digest could not be deployed. Remediation: fail rebuild-on-promotion, persist the tested immutable digest, and require a new candidate when build inputs change.

**High — REL-ATLAS-02.** Staging ran with a feature flag enabled that production did not have, so the canary reached 50% before the disabled-by-default path surfaced a regression. Remediation: diff flag and configuration state between environments in the parity control, and require production-equivalent flag state in staging before promotion.

**High — REL-ATLAS-03.** The rollback restored the previous binary but left the new schema migration active, so the old version wrote incompatible rows until the forward-fix shipped. Remediation: define rollback per component type (binary, configuration, schema, traffic) in the rollback plan, and rehearse the migration-reversal path for every reversible migration.

## KPIs and domain scorecard

The [release KPI catalog](../scorecards/release-kpis.md) measures verified promotion coverage and rollback readiness. Deployment frequency is not a health metric when evidence or reversibility is absent. Review `KPI-RELENG-001` and `KPI-RELENG-002` at every promotion and monthly, and add `KPI-RELENG-003` (release notes accuracy) to the monthly sampling review, because a misleading release note has the same operational cost as a silent behavior change.

## Common failure patterns and diagnostic guidance

- A pipeline reports green while its test result belongs to another source revision.
- A feature flag lacks an owner, expiry, or safe default when the control plane fails.
- A rollback restores code but leaves an incompatible asynchronous consumer or policy revision active.
- Emergency changes bypass evidence collection permanently instead of creating a retrospective record.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Green pipeline, broken production | Gate results not bound to the candidate digest | Compare test run IDs and digests in the release record | Bind gates to the digest; fail promotion on mismatch |
| Flag default changes behavior when control plane fails | Flag has no safe default or no owner | Review flag registry for owner, expiry, and default | Require owner, expiry, and fail-safe default in policy |
| Rollback restores code but system stays broken | Rollback scope excludes workers, schema, or policy | Review rollback plan component inventory | Define per-component rollback; rehearse with adverse fixtures |
| Emergency change leaves no record | Retrospective evidence not scheduled | Check emergency change for a dated retrospective record | Require retrospective record with same fields and a due date |
| Staging green, production fails | Environment drift in configuration or flags | Diff configuration and flag state | Enforce parity control; declare and approve intentional differences |

## Exit criteria

Exit when the release record ties one approved change to immutable artifacts, passing gates, environment configuration, observable deployment results, usable rollback, post-deployment verification, and retained evidence.

| Criterion | Evidence | Passes when |
| --- | --- | --- |
| Provenance bound | Release record with source, dependencies, digest, build identity | Candidate reproducible from declared inputs; no rebuild at promotion |
| Gates passed on candidate | Test run IDs tied to digest | Every required gate green against the exact artifact |
| Environment declared | Configuration revision, flag state, intentional differences | Staging state matches production except documented approvals |
| Rollout observed | Baseline and canary telemetry, stop criteria, traffic decisions | All signals compared; breaches acted on and recorded |
| Rollback usable | Rehearsal or executed rollback evidence | Rollback restores safe state without outcome loss or duplication |
| Verification complete | Post-deployment checks, communications, follow-up owners | Release record closed within one business day |

## Related runbooks, controls, examples, and templates

Use the release checklist, release-decision, verification-plan, migration-plan, incident-review, and executive-summary templates. Use the incident response runbook for an active customer-impacting deployment failure.

> **Application note — Cutctx.** For a token-compression proxy product, model-routing presets and compression engines are release artifacts with the same provenance requirements as binaries: the release record must bind the preset definition, the model router version, and the compatibility-alias mapping to one candidate, because a routing change is a customer-visible behavior change. The environment-parity control covers the trap in `docs/handoff-2026-07-28.md` where a Python path (`cutctx_ai.pth`) points at a worktree and the CLI runs different code than the repository checkout; declare the interpreter and package resolution as configuration, and let the parity control diff it between environments. Rollback readiness applies to preset rollouts, which must revert to the prior routing behavior without confusing in-flight requests.
