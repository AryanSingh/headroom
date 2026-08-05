---
id: EX-CH18-SDK-COMPATIBILITY-README
kind: worked-example
chapter: CH-18
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
preconditions: [isolated Product Atlas fixture, versioned v1 client contract, approved tenant-binding policy]
placement: engineering-handbook/examples/sdk-compatibility
dependencies: [Python 3 standard library]
invocation: Run python3 compatibility_fixture.py from this directory or the handbook example runner from the handbook root.
expected_output: The fixture accepts an additive response field, rejects a request bound to another tenant, and blocks removal of a required v1 response field.
failure_output: An accepted cross-tenant request or removed required field is a release-blocking compatibility failure.
interpretation: The fixture proves contract-gate mechanics; real releases require generated-client, consumer, and production-telemetry evidence.
remediation: Restore the contract, add a versioned endpoint or client path, update the compatibility matrix, and rerun consumer and contract checks.
cleanup: The fixture reads and writes no service, credential store, network endpoint, or customer system.
---

# Product Atlas offline SDK compatibility fixture

Atlas keeps the v1 account client usable while adding an optional response field. The fixture proves that additive output is tolerated, an Atlas B request cannot be presented as Atlas A, and a removed v1 `plan` field blocks compatibility approval.

Run `python3 compatibility_fixture.py`. A passing result is:

```text
SDK_COMPATIBILITY_FIXTURE_PASS additive-safe tenant-bound breaking-change-blocked
```

Attach the API specification diff, generated-client version, supported-client matrix, consumer-contract results, deprecation notice, and owner release decision to a real compatibility record.
