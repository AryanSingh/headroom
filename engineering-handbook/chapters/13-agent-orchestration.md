---
id: CH-13
kind: chapter
title: Agent Orchestration Engineering Audit
purpose: Build and assess agent orchestration systems that keep authority, state, tools, delegation, and recovery observable and bounded.
audience: [AI platform engineers, application engineers, security engineers, SREs, QA, engineering leaders]
scope: Agent identity, task delegation, tool authority, execution isolation, state transitions, retries, recovery, evaluation, and audit evidence.
applicability: Single-agent workflows, multi-agent systems, coding harnesses, workflow engines, support automation, and human-in-the-loop operations.
owners: [Agent platform owner, workflow owner, security owner, SRE owner]
inputs: [agent inventory, tool registry, authority policy, workflow definitions, traces, evaluation results, incident records]
outputs: [orchestration risk assessment, control evidence, remediation plan, and release decision]
dependencies: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025, NIST-SSDF-1.1]
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025, NIST-SSDF-1.1]
---

# Agent Orchestration Engineering Audit

## Purpose, audience, scope, and applicability

Agent orchestration is a production control plane, not a prompt chain. Audit whether every actor has a bounded identity, an explicit authority grant, observable state transitions, and a safe recovery path. Apply this chapter to systems that delegate work among models, tools, services, or humans.

The audit covers single-agent workflows that call tools, multi-agent systems that delegate between workers, coding harnesses, workflow engines, support automation, and human-in-the-loop operations. It applies at three moments: before a new workflow or tool capability is enabled, whenever delegation, approval, retry, or retention policy changes, and continuously through trace sampling and evaluation. A workflow that cannot answer "who was allowed to do what, when, and what did the authoritative system actually do?" is not ready for production regardless of how well its prompts perform.

## Concepts and engineering principles

Separate planning from execution, and capability discovery from authority to act. A delegated task must carry a correlation ID, declared inputs, permitted tools, stop conditions, and an accountable owner. Treat agent memory and tool output as untrusted until validated at the authorization boundary. Prefer narrow, revocable capabilities over ambient credentials.

Four invariants shape every audit step. First, **authority is minted per task, not inherited**: the worker receives a capability record that names the tenant scope, tools, action types, expiry, and budget for that delegation, and any request outside it is denied before side effect. Second, **state is observable**: every delegation, tool proposal, approval, invocation, result, retry, and terminal state is written to the trace with the correlation ID, so a run can be replayed without asking the model. Third, **success is authoritative**: a worker reporting success in generated text is not completion; the target system's response is reconciled against the approved request. Fourth, **recovery is accounted for**: a kill switch stops new work, but queued and in-flight side effects are inventoried and closed, because a half-recovered run is a hidden incident.

## Roles and accountability

The agent platform owner owns the orchestration runtime and policy enforcement. The workflow owner defines business outcomes and acceptable escalation. Security approves sensitive capabilities and reviews authority changes. SRE owns runtime availability, kill switches, and degraded-mode recovery. A human approver owns high-impact actions that cannot be reversed safely.

| Role | Owns | Approves | Accountable for |
| --- | --- | --- | --- |
| Agent platform owner | Orchestration runtime, capability broker, policy engine | Tool capability grants, delegation policy | That every invocation carries a matching authority chain |
| Workflow owner | Workflow definitions, business outcomes, escalation rules | Workflow release, exception handling | That delegated work achieves the declared outcome safely |
| Security owner | Sensitive capability classification, authority review | High-risk tool approvals | That no capability exceeds its approved scope |
| SRE owner | Runtime availability, kill switches, degraded-mode recovery | Termination runbooks, retry policy | That stop and recovery actions are testable and accounted for |
| Human approver | High-impact, irreversible action decisions | Individual sensitive actions | That approvals are informed and recorded with the action |

## Prerequisites and required inputs

Collect an agent and tool inventory, authority matrix, task graph, input classification, model configuration, trace samples, retry policy, evaluation results, incident history, and emergency-disable procedure. Every external side effect must have an identified compensating or containment action.

Before the audit, confirm the inventory is current and the authority matrix is the system of record. A tool that exists outside the registry is an ungoverned capability and a blocking finding. The task graph should name every actor, every delegation edge, and every external system a workflow can reach, because the graph is the map the audit uses to find missing approval gates and unreviewed side effects. Model configuration must include the model and version in force, the routing policy, and the reasoning or evaluation settings, so a behavior change can be attributed to a configuration change rather than to drift.

## Standard operating procedure

1. **Assign run identity and objective.** Give each orchestration run a durable correlation ID, an accountable owner, a declared objective, and a retention class before any delegation. Owner: workflow owner. Threshold: no run executes without an owner and an objective it can be checked against.
2. **Validate and classify inputs.** Validate task inputs against schema and policy, and classify the requested action by risk class (read, write, external communication, financial, destructive, cross-tenant) before a planner can delegate. Owner: agent platform owner.
3. **Mint the task-scoped capability.** Issue the worker only the tools, tenant scope, time limit, budget, and escalation path required for that task, with an expiry. Deny anything outside the grant before side effect. Threshold: zero invocations outside the grant in sampled traces.
4. **Record the delegation graph.** Write every delegation, tool proposal, approval, invocation, result, retry, and terminal state to the trace with the correlation ID. Owner: agent platform owner. Threshold: the trace can be replayed end to end without model recall.
5. **Enforce approval for sensitive actions.** Require explicit human or policy approval for irreversible, cross-tenant, financial, destructive, or external-communication actions. Record the approver, the request, and the decision with the action. Owner: workflow owner.
6. **Bound retries.** Stop retries when a policy, authority, budget, or safety condition fails; escalate rather than silently broadening permissions. Record each retry as a new decision with its inputs and reason. Threshold: retries never change model, tool scope, tenant, or budget without a recorded decision.
7. **Reconcile outcomes.** Match the authoritative system result to the approved request for every sensitive or external action before declaring the run complete. Owner: workflow owner.
8. **Test termination and recovery.** Execute the kill-switch and degraded-mode runbook in a fixture: stop new work, inventory queued and in-flight side effects, close or contain them, and record the final state of every affected action. Owner: SRE owner. Frequency: quarterly and after any runtime change.
9. **Reconcile and review.** Compare final business outcomes against the original objective, retain sanitized evidence, and route findings to owners with due dates. Owner: workflow owner.

### Delegation approval decision table

| Action class | Examples | Approval | Evidence required |
| --- | --- | --- | --- |
| Read within scope | Tenant-scoped lookup, status query | Policy-granted, no human | Trace, policy decision, target response |
| Write within scope | Tenant-scoped update, state change | Policy or human per workflow | Trace, approval record, target response, reconciliation |
| External communication | Email, chat message, webhook to third party | Human approver | Request, approval, send record, recipient scope |
| Financial | Charge, refund, entitlement grant with revenue effect | Human approver plus finance rule | Request, approval, ledger entry, invoice link |
| Destructive | Delete, disable, evict, bulk mutation | Human approver plus dry-run evidence | Request, approval, dry-run result, audit record |
| Cross-tenant | Any access outside the named tenant | Blocked by capability scope | Denied-request record, alert to workflow owner |

## Worked example

[Product Atlas delegated account-remediation example](../examples/agent-orchestration/README.md) shows a support triage agent delegating a tenant-scoped entitlement correction, blocking an attempted cross-tenant lookup, and escalating the final write for human approval.

Walk through the expected trace. The support ticket creates a run with correlation ID `run-913`, owner `oncall-manager`, and objective "restore the Pro export entitlement for tenant `atlas-eu-42`". Input validation classifies the action as a tenant-scoped write. The broker mints a capability record for the remediation worker naming the tenant scope, the entitlement tool, an expiry, and a budget; the worker's first lookup is inside scope and proceeds. The worker then proposes a search of tenant `atlas-us-17`, which the broker denies because the identifier does not match the capability scope; the denial is recorded and an alert goes to the workflow owner. The entitlement write is classified as sensitive, so it is queued for human approval; `oncall-manager` approves with the request, scope, and expected outcome visible. The target system confirms the write, and the reconciliation step matches the authoritative response to the approved request before the run closes as complete. The final evidence package is the task envelope, the two capability decisions, the approval record, the target response, and the reconciliation result — enough to replay the run without the model.

## Automation examples

```bash
atlasctl agents run --workflow entitlement-remediation --tenant atlas-eu-42 --request req-913 --dry-run --format json
atlasctl agents approve --run run-913 --action entitlement-write --approver oncall-manager
atlasctl agents trace verify --run run-913 --require-complete-authority-chain
```

Automation should fail closed on evidence gaps: deny invocations whose capability record is missing, expired, or out of scope; refuse to mark a run complete without a reconciliation result for sensitive actions; and alert on any termination that leaves in-flight work unaccounted. The trace verifier should be part of the release gate for every workflow, not an after-the-fact analysis tool.

## Audit prompts

Use [Opus](../prompts/opus/ch13-orchestration-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch13-delegation-evidence-review.md), and [Haiku](../prompts/haiku/ch13-agent-tool-inventory.md) for system-wide risk synthesis, one-run evidence review, and inventory normalization.

Use the Opus prompt when the audit spans workflows, tools, approval policy, and recovery runbooks and you need a consolidated risk statement. Use the Sonnet prompt to review a single run's trace and evidence package end to end, checking that the authority chain is complete and outcomes are reconciled. Use the Haiku prompt to normalize the agent and tool inventory before the audit begins. Treat model output as a hypothesis to verify against traces and audit records before it becomes a finding.

## Workflow checklist

Run [CL-AGENT-ORCH-01](../checklists/agent-orchestration.md) before enabling a new workflow, granting a tool capability, or changing delegation, approval, retry, or retention policy.

The checklist controls `ENG-AGENT-001` through `ENG-AGENT-005` cover bounded authority, sensitive-action approval, delegation-graph completeness, tool-registry governance, and termination authority. `ENG-AGENT-005` (termination authority) is the control most often deferred until an incident; run it as a routine rehearsal because a kill switch that cannot account for in-flight work is only half a control.

## Evidence requirements and retention guidance

Retain sanitized task definitions, correlation IDs, model and policy versions, authority grants, approvals, tool requests and results, state changes, evaluation evidence, and remediation ownership. Never retain raw credentials, unnecessary customer content, or unrestricted tool output when references and hashes are sufficient.

| Evidence | What to record | Retention | Owner |
| --- | --- | --- | --- |
| Task and identity records | Correlation ID, owner, objective, retention class | Workflow audit window | Workflow owner |
| Authority grants | Capability record, tenant scope, tools, expiry, budget | Run retention plus audit window | Agent platform owner |
| Approval records | Approver, request, decision, timestamp, action reference | Run retention plus audit window | Workflow owner |
| Tool invocations | Request, capability decision, target response, result | Run retention plus audit window | Agent platform owner |
| State transitions | Delegation, retry, terminal states with timestamps | Run retention plus audit window | Agent platform owner |
| Termination records | Kill-switch trigger, in-flight inventory, closure actions | Incident linkage plus audit window | SRE owner |

Credentials, customer content, and unrestricted tool output never enter the routine evidence set. Where full tool output is needed for an investigation, retain it in the incident evidence store with an explicit retention and access rule rather than in the workflow trace.

## Example findings with severity and remediation

**High — AGENT-ATLAS-01.** A remediation worker inherited a support-wide search tool and attempted to inspect a tenant not named in the task. Remediation: mint tenant-bound capability tokens, reject mismatched identifiers before tool invocation, and alert the workflow owner on any denied cross-scope request.

**High — AGENT-ATLAS-02.** A retry loop changed the model and broadened the tool scope after the first failure without recording a new decision, so the second attempt ran with authority the original task never granted. Remediation: freeze model, scope, and budget across retries, record each retry as a decision, and terminate the run when a policy condition fails instead of escalating silently.

**Critical — AGENT-ATLAS-03.** The emergency kill switch stopped new work but left a queued refund action in flight; the refund completed after the run was declared stopped and was not reconciled. Remediation: inventory queued and in-flight actions at termination, reconcile or contain each before closing the run, and add a kill-switch fixture that asserts no side effect completes without a closure record.

## KPIs and domain scorecard

The [agent orchestration KPI catalog](../scorecards/agent-orchestration-kpis.md) measures bounded-authority execution and reviewable recovery. High throughput does not compensate for an action whose authority chain cannot be reconstructed. Review `KPI-AGENT-001` and `KPI-AGENT-002` at release and weekly, and add `KPI-AGENT-003` (terminated-run side-effect closure) to the weekly review and to every termination, because a kill switch that stops new work but leaves in-flight actions running is only half a recovery.

## Common failure patterns and diagnostic guidance

- A planner passes user-provided text directly into a tool call without policy or schema validation.
- A retry changes model, tool, tenant scope, or budget without recording a new decision.
- A worker reports success from model text while the authoritative system rejected or never completed the action.
- An emergency kill switch stops new work but leaves queued or in-flight side effects unaccounted for.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Prompt injection leads to tool call | Tool input built from untrusted text without schema validation | Review tool-call construction and policy enforcement point | Validate at the authorization boundary; treat tool output as untrusted |
| Behavior changes between retries | Retry re-plans with new model, scope, or budget | Diff retry records for model, scope, and budget | Freeze retry inputs; record each retry as a decision |
| Run "succeeds" but nothing happened | Success read from generated text | Reconcile target-system response to the request | Require authoritative reconciliation before completion |
| Kill switch leaves side effects | No in-flight inventory at termination | Review termination record for queued actions | Inventory and close all in-flight work at termination |
| Worker accesses wrong tenant | Ambient or inherited credential | Check capability scope against request identifiers | Mint per-task capability tokens; deny mismatch before invocation |

## Exit criteria

Exit when every tested workflow has a reproducible authority chain, bounded tools and data scope, observable terminal state, enforced escalation for sensitive actions, and reconciled outcome evidence.

| Criterion | Evidence | Passes when |
| --- | --- | --- |
| Authority chain reproducible | Trace with capability decisions per invocation | Every invocation links task identity, grant, decision, and outcome |
| Tools and scope bounded | Capability records and denied-request log | Zero invocations outside grant in sampled and fixture runs |
| State observable | Complete delegation and state-transition trace | Run replays end to end without model recall |
| Sensitive actions approved | Approval records with requests and decisions | No sensitive action completes without recorded approval |
| Outcomes reconciled | Target-system responses matched to requests | No completion claimed from generated text alone |
| Recovery accounted | Kill-switch and termination records | All in-flight and queued side effects inventoried and closed |

## Related runbooks, controls, examples, and templates

Use the agent-orchestration checklist, threat-model, AI-evaluation-report, finding, incident-review, and verification-plan templates. Use the incident response runbook when an agent performs or attempts an unsafe external action.

> **Application note — Cutctx.** For a token-compression proxy product, model routing is itself an agent-adjacent control plane: the routing decision, preset version, and compatibility alias are configuration that changes model behavior in production, so the delegation-graph control covers the routing decision path the same way it covers a tool call. The trap in `docs/handoff-2026-07-28.md` — an engine reporting 0% savings while enabled, silent, and doing nothing — is a failure-pattern match: the "success" signal came from generated or config text rather than authoritative measurement, so reconciliation must compare claimed engine behavior against measured per-request outcome. Termination authority applies to routing migrations, which must inventory in-flight requests before switching presets.
