---
id: EX-CH09-MEMORY
kind: worked-example
chapter: CH-09
standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
preconditions: [Atlas tenant-a and tenant-b fixtures, memory store, vector index, cache, deletion worker]
placement: engineering-handbook/examples/memory-governance
dependencies: [local memory fixture service, deterministic index and cache fixtures]
invocation: Ingest tenant-a support memory, attempt tenant-b retrieval, expire the record, submit deletion, and query every retrieval layer.
expected_output: Tenant-a retrieves the current record; tenant-b receives none; expired memory is excluded; deletion removes all retrievable derivatives.
failure_output: Another tenant retrieves the record, an expired record remains ranked, or any layer returns the deleted subject.
interpretation: Access and deletion are end-to-end properties; primary-store success is insufficient without index and cache verification.
remediation: Enforce tenant filters before ranking, issue retrieval tombstones, repair deletion fan-out, and add all-layer regression checks.
cleanup: Destroy fixtures, deletion-job logs, and sanitized evaluation captures.
---

# Product Atlas memory governance evidence

Atlas stores `mem-a-17`, a tenant-a renewal preference, with purpose `support-assist`, expiry `2026-09-01`, and provenance `ticket-441`. The record may help a tenant-a support agent draft a response but may not be retrieved by tenant-b or after expiry.

| Case | Expected result | Evidence |
| --- | --- | --- |
| Tenant-a retrieval | `mem-a-17` with provenance | scoped query trace and policy version |
| Tenant-b retrieval | empty set | authorization verdict before ranking |
| Expiry job | record excluded | expiry timestamp and search result |
| Subject deletion | no primary/index/cache hit | deletion job and three layer checks |

Atlas records IDs and hashes, not the preference text, in its evidence register. The deletion run remains open until the index and cache both acknowledge removal.

## Executable fixture

Run the deterministic memory governance fixture with the handbook example
runner (`python3 automation/check_examples.py engineering-handbook`) or
directly from this directory:

```shell
python3 memory_governance_fixture.py
```

The fixture classifies an ingested record, checks tenant-a and tenant-b
retrieval across the primary, index, and cache layers, verifies an expired
record is excluded, and deletes a subject with an all-layer verification.
Expected output on stdout, exactly:

```text
MEMORY_GOVERNANCE_FIXTURE_PASS tenant-isolated expiry-enforced deletion-complete
```

The fixture is pure standard library with in-memory layers; it makes no network
calls. Failure interpretation: a non-zero exit means another tenant retrieved
the record, an expired record remained ranked, or any layer returned a deleted
subject. Cleanup: the fixture creates no files or external resources, so no
cleanup step is required.
