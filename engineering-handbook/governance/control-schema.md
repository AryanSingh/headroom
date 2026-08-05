# Control schema

Controls are stable, auditable requirements that connect a handbook procedure
to observable evidence and, where applicable, a pinned standards source.
Control records live in checklist front matter under a `controls` list.

## Identifier

Use `DOMAIN-FAMILY-NNN`, for example `SEC-AUTH-004`. An identifier is permanent
after publication. Retired controls remain reserved and are marked retired in a
later catalog rather than reused.

## Required fields

| Field | Type | Contract |
| --- | --- | --- |
| `id` | string | Globally unique stable control identifier. |
| `requirement` | string | Behavior the team demonstrates. |
| `applicability` | string | `required`, `recommended`, or `contextual`, with conditions. |
| `procedure` | string or list | Exact, reproducible verification method. |
| `expected_result` | string | Observable pass condition. |
| `evidence` | string or list | Durable artifacts proving the result. |
| `automation` | string or list | Test, script, query, or pipeline stage; use `manual` when justified. |
| `owner` | string | Accountable role, not a transient individual. |
| `frequency` | string | Change, release, quarter, incident, or another explicit cadence. |
| `failure_action` | string | Block, remediate, accept through governance, or monitor. |
| `standards` | list | IDs from `standards/registry.yaml`; an empty list is explicit. |

## Checklist front matter

```yaml
id: CL-IDENTITY-01
kind: checklist
title: Identity verification checklist
controls:
  - id: SEC-IDENTITY-001
    requirement: The service verifies identity before granting protected access.
    applicability: required for protected resources
    procedure:
      - Execute the anonymous-access contract test.
      - Execute the valid-session contract test.
    expected_result: Anonymous access is denied and the valid session is authorized.
    evidence:
      - test report
      - authorization decision log
    automation: tests/security/test_identity.py
    owner: Service owner
    frequency: every change and release
    failure_action: block release and remediate
    standards:
      - OWASP-ASVS-5.0.0
```

## Evidence and exceptions

Evidence names the artifact, collection point, retention period, and integrity
expectation in the surrounding checklist or chapter. A control failure is never
silently waived. The finding records the decision owner, rationale, expiry, and
follow-up; validator suppressions affect publication findings only and do not
constitute control acceptance.
