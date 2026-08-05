---
id: CL-SDK-COMPATIBILITY-01
kind: checklist
title: API and SDK compatibility checklist
chapter: CH-18
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
controls:
  - id: ENG-SDKCOMPAT-001
    requirement: Supported API and SDK changes must have a documented compatibility classification, version policy, consumer matrix, and executable evidence for requests, responses, errors, and documented behavior.
    applicability: required for public and internal APIs, SDKs, CLIs, webhooks, events, plugins, and generated-client contract changes
    procedure: Compare the prior and candidate contract, enumerate supported consumers, run versioned request-response-error fixtures, and record compatibility, owner, rollback, and migration decisions.
    expected_result: Every supported consumer has a declared compatible path or an approved versioned migration; no breaking behavior is silently released.
    evidence: specification diff, compatibility matrix, generated-client output, consumer-contract runs, migration guide, and release decision
    automation: offline compatibility fixture plus versioned consumer contract tests
    owner: API owner
    frequency: every contract-affecting change and before each compatibility retirement
    failure_action: block promotion or retirement, restore the supported contract or introduce a versioned path, notify consumers, and rerun evidence.
    standards: [NIST-SSDF-1.1, OWASP-API-TOP10-2023]
  - id: ENG-SDKCOMPAT-002
    requirement: Compatibility behavior must preserve authorization, tenant binding, input validation, and machine-readable error semantics across supported versions.
    applicability: required for every contract path that accepts identity, tenant, resource, scope, or externally supplied input
    procedure: Exercise accepted and rejected versioned requests, verify tenant and scope checks, compare error code contracts, and review fallback behavior for authority broadening.
    expected_result: A compatibility path never accepts a cross-tenant or unauthorized request and clients can distinguish actionable contract errors.
    evidence: authorization tests, tenant-bound fixtures, error catalog, security review, and sanitized trace references
    automation: tenant-bound compatibility fixture and authorization regression suite
    owner: Security owner
    frequency: every authority or error-contract change and quarterly for supported interfaces
    failure_action: disable the unsafe compatibility path, contain exposure under incident procedures if required, correct the contract, and repeat independent verification.
    standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
---

# API and SDK compatibility checklist

- [ ] Classify the contract change and attach the prior/candidate specification and behavior diff.
- [ ] Name every supported client, generated SDK, integration, owner, support window, and rollback path.
- [ ] Exercise old and new requests, responses, errors, unknown additive fields, and removed required fields.
- [ ] Verify compatibility preserves authentication, authorization, tenant binding, validation, limits, and machine-readable errors.
- [ ] Publish migration and deprecation evidence, monitor adoption, and retire only after the recorded exit rule is met.
