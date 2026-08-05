---
id: KPI-CATALOG-CONTINUOUS-VERIFICATION
kind: kpi-catalog
chapter: CH-20
kpis:
  - id: KPI-CV-001
    name: Required-check evidence completeness
    decision: Whether release decisions are based on complete, resolvable evidence for every required qualification check.
    calculation: production promotions with passing or authorized-exception evidence for every declared required check divided by all production promotions.
    source: release ledger, pipeline policy, build provenance, check records, exception register, and release decisions
    frequency: every promotion and weekly
    owner: Release engineering owner
    target: 100 percent
    warning: below 100 percent, any missing candidate binding, expired exception, skipped required check, or unresolved evidence reference
    distortions: [removing failing checks from policy, counting retries as independent evidence, excluding emergency changes]
    anti_gaming: [version policy, retain failed attempts, independently sample candidate bindings, and include emergency releases]
    interpretation: A fast release is not qualified when its checks cannot be tied to the artifact and decision that reached production.
  - id: KPI-CV-002
    name: Safe release automation coverage
    decision: Whether critical releases have tested stop, containment, and rollback or forward-repair automation linked to observable thresholds.
    calculation: critical release paths with a current passing staged-rollout and threshold-breach rehearsal divided by all critical release paths.
    source: service inventory, rollout policies, rehearsal records, deployment telemetry, and incident reviews
    frequency: quarterly, before critical releases, and after deployment-platform changes
    owner: Service owner
    target: 100 percent
    warning: below 100 percent, missing stop authority, untested rollback, absent business threshold, or manual action without owner and evidence
    distortions: [testing only healthy rollouts, treating deployment completion as release success, excluding data and configuration changes]
    anti_gaming: [inject threshold breach, include customer-outcome signals, retain failed rehearsals, and independently review rollback timing]
    interpretation: Automation is safe when it can limit an unsafe release under realistic failure conditions, not when it merely deploys quickly.
---

# Continuous verification and release automation KPI catalog

Review evidence completeness and safe automation together. A fully green dashboard cannot replace a decision record that lacks candidate-bound checks or a rehearsed way to stop a harmful rollout.
