---
id: CL-AUDIT-01
kind: checklist
title: Audit execution checklist
chapter: CH-01
controls:
  - id: GOV-AUDIT-001
    requirement: Every material audit has an approved decision-oriented brief before evidence collection.
    applicability: required for release, security, migration, and high-risk architecture reviews
    procedure: Confirm the brief contains decision, scope, owners, evidence plan, risk hypotheses, and exit criteria.
    expected_result: A dated brief is linked from the evidence register before audit commands run.
    evidence: Approved brief and evidence-register entry.
    automation: manual review of immutable brief link
    owner: Audit lead
    frequency: at audit intake
    failure_action: pause execution until scope and decision authority are explicit
    standards: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
  - id: GOV-AUDIT-002
    requirement: Findings that influence release disposition have reproducible evidence or a stated reproducibility limit.
    applicability: required for Important and Critical findings
    procedure: Re-run the minimal command against the recorded revision and fixture, then compare captured output.
    expected_result: Evidence packet contains command, revision, output, timestamp, and reviewer.
    evidence: CI URL or retained command log, fixture checksum, finding record.
    automation: documented reproducible command
    owner: Audit lead
    frequency: finding review and retest
    failure_action: keep finding open and classify evidence as blocked
    standards: [NIST-SSDF-1.1]
---

# Audit execution checklist

Use this checklist at intake, before release decision, and after remediation.
For Product Atlas, the audit lead attaches `AB-2026.4.0` and the beta-tenant
authorization test output before asking the release authority to decide.
