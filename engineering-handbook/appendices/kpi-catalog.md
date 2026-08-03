---
id: APP-KPI-CATALOG
kind: appendix
title: KPI decision catalog
standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0]
---

# KPI decision catalog

This is a cross-catalog index, not a second source of metric definitions. Each
linked scorecard remains authoritative for population, exclusions, threshold,
and anti-gaming controls. A metric is useful only when its decision, source
timestamp, denominator, and failure action are visible together.

## Scorecard operating rules

- Preserve numerator, denominator, inclusion rule, time window, unit, and
  missing-data behavior with every reported value.
- Pair speed and volume KPIs with outcome, safety, or quality KPIs. A faster
  release cadence does not offset failed changes; lower cost does not offset an
  unauthorized route.
- Report the raw denominator beside percentages. `100%` of one case is not a
  readiness claim.
- Use a warning as an investigation trigger, not as permission to normalize a
  failing required control.
- If an owner changes a definition materially, create a new KPI ID and retain a
  migration note; do not silently rewrite historical trend lines.

## Decision map

| Domain | KPI IDs | Decision supported | Required companion evidence | Source |
| --- | --- | --- | --- | --- |
| Audit operations | `KPI-AUDIT-001/002` | Is the audit complete and are findings closing effectively? | scope ledger, evidence register, finding record | `scorecards/audit-operations-kpis.md` |
| Discovery | `KPI-DISCOVERY-001/002` | Is capability coverage sufficient for a release/audit? | capability map and ownership review | `scorecards/discovery-kpis.md` |
| CLI | `KPI-CLI-001/002` | Are scripts reliable and protected operations safe? | command contract and production-action evidence | `scorecards/cli-kpis.md` |
| Desktop | `KPI-DESKTOP-001/002` | Are upgrades recoverable and privileged local paths bounded? | lifecycle fixture and IPC review | `scorecards/desktop-kpis.md` |
| Dashboard | `KPI-DASH-001/002` | Do critical journeys remain usable and authorized? | state matrix and browser evidence | `scorecards/dashboard-kpis.md` |
| API/backend | `KPI-API-001/002` | Are API correctness and protected writes meeting policy? | contract, authorization, and idempotency tests | `scorecards/api-kpis.md` |
| Integrations | `KPI-INTEGRATION-001/002` | Are callbacks trustworthy and authority boundaries explicit? | signature/replay and approval traces | `scorecards/integration-kpis.md` |
| Routing | `KPI-ROUTING-001/002` | Is selection policy safe within cost/latency constraints? | route-policy version and traces | `scorecards/routing-kpis.md` |
| Memory | `KPI-MEMORY-001/002` | Is retained context isolated and deletable? | classification, deletion, and replay evidence | `scorecards/memory-kpis.md` |
| Reliability | `KPI-RELPERF-001/002` | Can the service meet objectives under load and recovery? | SLO view, load test, recovery rehearsal | `scorecards/reliability-kpis.md` |
| Commercial | `KPI-COMM-001/002` | Do commercial claims and lifecycle outcomes reconcile? | claim register and entitlement/billing reconciliation | `scorecards/commercial-kpis.md` |
| Release engineering | `KPI-RELENG-001/002` | Is deployment risk controlled and rollback usable? | qualification, canary, rollback ledger | `scorecards/release-kpis.md` |
| Agent orchestration | `KPI-AGENT-001/002` | Is delegation controlled and consequential execution reviewable? | delegation graph, tool approvals, replay trace | `scorecards/agent-orchestration-kpis.md` |
| Playwright | `KPI-PLAYWRIGHT-001/002` | Do critical browser journeys and visual checks remain trustworthy? | deterministic fixture, screenshot/diff ledger | `scorecards/playwright-kpis.md` |
| Chaos | `KPI-CHAOS-001/002` | Are resilience claims proven under bounded faults? | experiment record, abort/recovery trace | `scorecards/chaos-kpis.md` |
| Migrations | `KPI-MIGRATION-001/002` | Is data change reconciled and recovery-ready? | per-tenant reconciliation and restore rehearsal | `scorecards/migration-kpis.md` |
| AI evaluation | `KPI-AIEVAL-001/002` | Does a candidate meet quality, safety, and routing policy? | dataset manifest, raw cases, adjudications | `scorecards/ai-evaluation-kpis.md` |
| SDK compatibility | `KPI-SDKCOMPAT-001/002` | Can consumers upgrade without an unapproved break? | compatibility fixture and adoption evidence | `scorecards/api-sdk-compatibility-kpis.md` |
| Observability | `KPI-OBS-001/002` | Can operators detect, explain, and act on service risk? | correlated telemetry, alert exercise, runbook | `scorecards/observability-kpis.md` |
| Continuous verification | `KPI-CVRA-001/002` | Are promotion gates evidence-led and resistant to bypass? | failed-path proof, provenance, promotion event | `scorecards/continuous-verification-kpis.md` |

## Reading a KPI without being misled

Use the following review sequence for every scorecard:

| Question | Good answer | Escalate when |
| --- | --- | --- |
| What decision changes? | A named release, routing, recovery, or investment decision. | The metric is merely “tracked.” |
| What population is missing? | Explicit exclusions with a reason and count. | Failures, blocked requests, or small tenants disappear. |
| Could the owner optimize the number while harming users? | A listed anti-gaming check and balancing metric. | Only throughput, cost, or completion is measured. |
| Is the value reproducible? | Query/report version, timestamp, raw denominator, and source links. | Dashboard screenshot is the only evidence. |
| What happens at warning/fail? | A named investigation, release block, or exception route. | No action is tied to the threshold. |

## Example: a safe release decision

Product Atlas reports `KPI-RELENG-001` within target and a green canary
dashboard. The decision is still *hold* if `KPI-OBS-002` has no actionable
alert exercise or `ENG-MIGRATION-002` lacks reconciliation evidence. The
scorecard supports prioritization; it never supersedes a required control.
