---
id: KPI-CATALOG-CHAOS
kind: kpi-catalog
chapter: CH-15
kpis:
  - id: KPI-CHAOS-001
    name: Critical failure-hypothesis coverage
    decision: Whether material failure modes for critical outcomes have current, bounded, evidence-backed experiments.
    calculation: critical failure hypotheses with a passing or remediated experiment in the required interval divided by all approved critical hypotheses.
    source: risk register, experiment register, and remediation evidence
    frequency: monthly and release review
    owner: SRE owner
    target: 100 percent
    warning: any critical hypothesis lacks current evidence or has an unresolved failed experiment
    distortions: [counting planned tests, testing only process uptime, excluding dependencies]
    anti_gaming: [require fixture result, business reconciliation, scope record, and owner approval]
    interpretation: Coverage is proof of a tested hypothesis, not a count of injected faults.
  - id: KPI-CHAOS-002
    name: Verified recovery correctness rate
    decision: Whether experiments recover without lost, duplicated, or cross-tenant accepted work.
    calculation: experiments with passing outcome reconciliation and recovery evidence divided by completed experiments involving accepted work.
    source: experiment reports, idempotency ledger, queue metrics, and recovery records
    frequency: monthly and after experiment failure
    owner: Service owner
    target: 100 percent
    warning: below 100 percent or any integrity/tenant-scope failure
    distortions: [excluding aborted experiments, counting process restart as recovery, using empty fixtures]
    anti_gaming: [include aborted outcomes, require ledger query, and use versioned representative fixtures]
    interpretation: Recovery is not successful until business correctness and scope reconcile.
---

# Chaos engineering KPI catalog

Review coverage with recovery correctness and unresolved experiment findings; never use the number of failures injected as a maturity score.
