---
id: PROMPT-CH16-OPUS-01
kind: prompt
chapter: CH-16
model_family: opus
workload_type: cross-system migration failure-chain synthesis
objective: Produce a prioritized risk assessment spanning compatibility, lock and performance behavior, backfill semantics, tenant isolation, recovery, reconciliation, and contract removal.
inputs: [migration plan, schema diff, dependency map, query plans, batch design, checkpoint semantics, backup evidence, reconciliation results]
boundaries: [analyze supplied evidence only, do not execute migrations or access production systems, do not infer recovery proof from a backup policy]
evidence: [cite plan section, schema version, dependency, query-plan result, batch boundary, checkpoint, tenant result, recovery run, and accountable owner for each conclusion]
output_schema: {type: migration-risk-synthesis, fields: [transition-map, failure-chains, evidence-gaps, ranked-risks, required-gates, decision-recommendation]}
uncertainty: Separate observed evidence, supported inference, and unknown behavior under production-scale volume or failure.
stop_conditions: [missing compatibility analysis, absent rollback or forward-repair plan, no tenant-scoped reconciliation, unbounded lock risk]
escalation: Escalate cross-tenant exposure, unrecoverable integrity loss, destructive contract change, or untested recovery to database, security, SRE, and release owners.
---

# Opus migration failure-chain synthesis prompt

Build the change transition map before ranking risks. Trace each old and new reader/writer, batch boundary, checkpoint, retry, tenant predicate, recovery option, and contract condition. Treat missing reconciliation or recovery evidence as a release-blocking gap rather than evidence that the change is safe.
