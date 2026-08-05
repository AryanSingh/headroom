---
id: RB-RELEASE-002
kind: runbook
title: Rollback
triggers: [Release stop condition, failed canary, material regression, unsafe configuration, operator-directed containment]
severity: [High, Critical when integrity, security, or broad customer impact is credible]
roles: [Release Manager, On-call SRE, Service Owner, Incident Commander when activated]
prerequisites: [Known-good immutable artifact or configuration, rollback authority, deployment access, telemetry links, communication channel]
decisions: [Rollback code, disable flag, shift traffic, pause and investigate, declare incident]
communication: [Release channel, incident channel when activated, support owner, affected stakeholders]
containment_or_rollback: [Stop cohorts, pin prior artifact, revert safe configuration, disable affected feature, isolate unsafe worker]
evidence: [Trigger threshold, timestamps, before-and-after telemetry, executed commands or deployment IDs, approver, verification result]
recovery: [Restore known-good state, reconcile asynchronous work, verify critical journeys and monitoring]
exit_criteria: [Rollback state is stable, impact is contained, verification is recorded, ownership transfers cleanly]
follow_up: [Open incident review or release corrective action; retain failed candidate for diagnosis]
standards: [NIST-IR-800-61R3, NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0]
---

# Rollback

## Purpose and boundary

Rollback restores a known-safe operational state when a declared release condition fails. It does not erase evidence, reverse data blindly, or close an incident. For schema or customer-data actions, use the migration or data-recovery runbook after stopping further exposure.

## Product Atlas example

At 5% traffic, Atlas checkout authorization failures rise from 0.2% to 3.4%, exceeding the 1% stop threshold. The release manager freezes rollout, routes traffic to the previous `checkout-api` digest, and disables the new retry policy. The SRE verifies authorization success and queue depth for 15 minutes before handoff to the incident commander.

## Procedure

1. Record the trigger, threshold, release ID, affected cohort, and current time. Preserve the candidate identity before taking action.
2. Freeze expansion: prevent automatic promotion, pause deployment jobs, and stop new workers or consumers that would deepen the unsafe state.
3. Select the smallest safe containment action: disable a flag, revert configuration, restore a prior immutable artifact, or shift traffic. Do not use an untested workaround.
4. Execute the action through the approved control plane. Record deployment ID, operator, start time, and intended restored state.
5. Check service health, critical business outcome, error rate, latency, backlog, and security alerts against the pre-release baseline. Inspect asynchronous consumers and scheduled jobs separately.
6. If verification fails, widen containment, invoke the incident commander, and preserve the failed state for diagnosis where safe. Do not retry the candidate.
7. Communicate the action and observed impact. State facts, current customer effect, next update time, and incident reference when one exists.
8. Transfer the failed candidate, evidence, and open questions to the release owner or incident commander. Keep release automation disabled until a new decision is approved.

## Verification checklist

- [ ] New cohorts are blocked and no promotion automation remains armed.
- [ ] The expected artifact/configuration/flag state is confirmed in production.
- [ ] At least one critical journey succeeds using the restored path.
- [ ] Error, latency, backlog, and security signals are current and within recovery thresholds.
- [ ] Deferred work has a named reconciliation owner.
- [ ] The decision and evidence record identify what was changed and when.

## Exit and follow-up

Exit when the restored state is stable for the declared observation window and responsibility is explicit. The follow-up record distinguishes rollback execution facts from root-cause hypotheses. Requalification requires a new candidate, corrected evidence, and a fresh release decision.
