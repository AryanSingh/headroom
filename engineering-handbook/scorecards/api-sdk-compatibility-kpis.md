---
id: KPI-CATALOG-SDK-COMPATIBILITY
kind: kpi-catalog
chapter: CH-18
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
kpis:
  - id: KPI-SDKCOMPAT-001
    name: Supported-consumer compatibility evidence coverage
    decision: Whether every supported consumer and contract path has current executable compatibility and authority evidence for a proposed release.
    calculation: supported consumer-version and contract-path pairs with passing current evidence divided by all supported consumer-version and contract-path pairs.
    source: support policy, compatibility matrix, contract test records, generated-client results, and release decisions
    frequency: every contract release and weekly during a migration
    owner: API owner
    target: 100 percent
    warning: below 100 percent, an untested supported version, or missing tenant/error contract evidence
    distortions: [counting only latest clients, treating compile success as runtime compatibility, excluding error and authority paths]
    anti_gaming: [sample runtime decoding, require versioned matrices, include rejected requests, independently review a supported legacy client]
    interpretation: Coverage is complete only when each declared support pair has attributable, repeatable evidence.
  - id: KPI-SDKCOMPAT-002
    name: Verified deprecation completion rate
    decision: Whether deprecated contract paths are retired only after their stated adoption, notice, migration, and recovery conditions are met.
    calculation: deprecated paths retired with all recorded exit conditions divided by all retired deprecated paths in the period.
    source: deprecation register, adoption telemetry, consumer attestations, exceptions, and release decisions
    frequency: monthly and at each retirement decision
    owner: SDK owner
    target: 100 percent
    warning: any retired path without consumer confirmation, adoption evidence, migration guidance, or rollback plan
    distortions: [declaring an endpoint unused from partial telemetry, excluding unmanaged consumers, measuring notice delivery instead of migration completion]
    anti_gaming: [retain support matrix snapshots, require negative telemetry and consumer attestation, sample support tickets, review exceptions]
    interpretation: Retirement is safe only when the documented audience has a usable successor and the rollback decision remains executable.
---

# API and SDK compatibility KPI catalog

Review the evidence matrix and deprecation register together. A low-volume legacy client can still carry a high-impact workflow; adoption data must not erase the support commitment.
