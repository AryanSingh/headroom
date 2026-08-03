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
