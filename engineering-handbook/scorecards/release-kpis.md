---
id: KPI-CATALOG-RELEASE
kind: kpi-catalog
chapter: CH-12
kpis:
  - id: KPI-RELENG-001
    name: Verified immutable promotion coverage
    decision: Whether production changes deploy the exact candidate that passed required checks with attributable evidence.
    calculation: production promotions with matching approved source, artifact digest, test evidence, configuration revision, and deployment record divided by all production promotions.
    source: release ledger, artifact registry, CI evidence store, and deployment audit log
    frequency: each promotion and monthly
    owner: Release owner
    target: 100 percent
    warning: below 100 percent or any promotion with a missing or mismatched digest
    distortions: [counting tag names as immutable identity, excluding emergency changes, accepting a green build from another revision]
    anti_gaming: [compare deployed digest to tested digest, require retrospective evidence for emergency changes, sample configuration linkage]
    interpretation: A promotion is verified only when its deployed artifact and evidence package are the same release candidate.
  - id: KPI-RELENG-002
    name: Tested rollback readiness coverage
    decision: Whether release classes have current proof that stop and rollback actions restore a safe service state.
    calculation: release classes with passing threshold, traffic-control, rollback, and outcome-integrity rehearsal in the required interval divided by all release classes.
    source: rollout plans, rehearsal reports, deployment controller events, and outcome-integrity queries
    frequency: quarterly, before high-risk change, and after rollback mechanism changes
    owner: SRE owner
    target: 100 percent
    warning: below 100 percent, unowned stop criterion, or failed rollback rehearsal
    distortions: [rolling back empty environments, reversing code only, ignoring workers or data changes]
    anti_gaming: [require adverse fixtures, component inventory, client-outcome query, and independent evidence review]
    interpretation: Fast deployment does not offset a rollback that leaves incompatible components or corrupt customer outcomes.
---

# Release engineering KPI catalog

Review immutable promotion and rollback readiness together. A release program is healthy when it can prove what changed and stop safely when the observed outcome contradicts the plan.
