---
id: PROMPT-CH16-SONNET-01
kind: prompt
chapter: CH-16
model_family: sonnet
workload_type: migration execution and reconciliation evidence review
objective: Determine whether one completed or paused migration has sufficient attributable evidence for continue, stop, recovery, or contract decisions.
inputs: [migration record, checkpoint log, telemetry snapshot, query-plan review, reconciliation queries/results, exceptions, rollback or repair result]
boundaries: [review one supplied execution record, do not run database queries or alter data, do not approve a contract change without explicit compatibility and reconciliation proof]
evidence: [cite execution ID, source/target version, batch or checkpoint, tenant result, query/result timestamp, exception, recovery action, and owner]
output_schema: {type: migration-evidence-review, fields: [evidence-matrix, discrepancies, threshold-status, recovery-status, contract-readiness, required-next-actions]}
uncertainty: Label incomplete or aggregated results as unknown; distinguish a measured result from an assumption about production scale.
stop_conditions: [missing tenant result, integrity discrepancy, breached threshold, unsupported reader/writer, unavailable recovery evidence]
escalation: Escalate integrity discrepancy, cross-tenant result, blocked restore, or destructive-action request to the migration and incident owners.
---

# Sonnet migration reconciliation evidence-review prompt

Review the supplied execution as a decision record. Verify that checkpoint behavior, tenant scope, telemetry, and reconciliation agree. Report what blocks continuation, what blocks contract removal, and the smallest evidence-producing recovery or verification action for each discrepancy.
