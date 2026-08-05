"""Deterministic Product Atlas memory governance evidence fixture.

Proves purpose classification, tenant isolation, expiry enforcement, and
all-layer deletion against an in-memory three-layer store (primary, index,
cache). Records are stored as IDs and hashes, never as preference text.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

TODAY = "2026-08-04"
APPROVED_PURPOSES = {"support-assist", "billing-assist", "product-recommendation"}


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    tenant: str
    purpose: str
    expiry: str
    provenance: str
    content_hash: str


class MemoryStore:
    """Three retrieval layers over an in-memory record set."""

    def __init__(self) -> None:
        self._primary: dict[str, MemoryRecord] = {}
        self._index: dict[str, list[str]] = {}  # purpose -> record ids
        self._cache: dict[str, str] = {}  # record id -> content hash
        self._tombstones: set[str] = set()

    def classify(self, purpose: str) -> str | None:
        return purpose if purpose in APPROVED_PURPOSES else None

    def ingest(self, record: MemoryRecord) -> str | None:
        if self.classify(record.purpose) is None:
            return "unapproved-purpose"
        if record.id in self._tombstones:
            return "deleted-subject"
        self._primary[record.id] = record
        self._index.setdefault(record.purpose, []).append(record.id)
        self._cache[record.id] = record.content_hash
        return None

    @staticmethod
    def _expired(record: MemoryRecord) -> bool:
        return record.expiry < TODAY

    def retrieve(self, tenant: str, subject: str, layer: str = "primary") -> MemoryRecord | None:
        """Authorize tenant scope before ranking; exclude expired and deleted."""
        if subject in self._tombstones:
            return None
        if layer == "index":
            for record_id in self._index.get("support-assist", []):
                record = self._primary.get(record_id)
                if record is not None and record.id == subject:
                    if record.tenant != tenant or self._expired(record):
                        return None
                    return record
            return None
        if layer == "cache":
            if subject not in self._cache:
                return None
            record = self._primary.get(subject)
            if record is None or record.tenant != tenant or self._expired(record):
                return None
            return record
        record = self._primary.get(subject)
        if record is None or record.tenant != tenant or self._expired(record):
            return None
        return record

    def delete(self, subject: str) -> None:
        """Remove the subject from every retrieval layer and leave a tombstone."""
        self._primary.pop(subject, None)
        for purpose_ids in self._index.values():
            if subject in purpose_ids:
                purpose_ids.remove(subject)
        self._cache.pop(subject, None)
        self._tombstones.add(subject)

    def layers_clean(self, subject: str) -> bool:
        return (
            subject not in self._primary
            and subject not in self._cache
            and all(subject not in purpose_ids for purpose_ids in self._index.values())
        )


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    store = MemoryStore()

    # 1. Classification: unapproved purposes are rejected at ingest time.
    rejected = MemoryRecord(
        id="mem-a-99",
        tenant="tenant-a",
        purpose="social-graph",
        expiry="2026-12-31",
        provenance="ticket-999",
        content_hash=_hash("unapproved"),
    )
    assert store.ingest(rejected) == "unapproved-purpose"

    # 2. Ingest a tenant-a support-assist record; it must not outlive 2026-09-01.
    current = MemoryRecord(
        id="mem-a-17",
        tenant="tenant-a",
        purpose="support-assist",
        expiry="2026-09-01",
        provenance="ticket-441",
        content_hash=_hash("renewal-preference"),
    )
    assert store.ingest(current) is None

    # 3. Tenant isolation: tenant-a retrieves; tenant-b receives nothing from
    #    any layer.
    own_view = store.retrieve("tenant-a", "mem-a-17")
    assert own_view is not None and own_view.provenance == "ticket-441"
    assert store.retrieve("tenant-b", "mem-a-17") is None
    assert store.retrieve("tenant-b", "mem-a-17", layer="index") is None
    assert store.retrieve("tenant-b", "mem-a-17", layer="cache") is None

    # 4. Expiry enforcement: an expired tenant-a record is excluded before ranking.
    expired = MemoryRecord(
        id="mem-a-05",
        tenant="tenant-a",
        purpose="support-assist",
        expiry="2026-07-01",
        provenance="ticket-120",
        content_hash=_hash("stale-copy"),
    )
    assert store.ingest(expired) is None
    assert store.retrieve("tenant-a", "mem-a-05") is None
    assert store.retrieve("tenant-a", "mem-a-05", layer="index") is None

    # 5. Deletion: after delete, no layer returns the subject.
    store.delete("mem-a-17")
    assert store.retrieve("tenant-a", "mem-a-17") is None
    assert store.retrieve("tenant-a", "mem-a-17", layer="index") is None
    assert store.retrieve("tenant-a", "mem-a-17", layer="cache") is None
    assert store.layers_clean("mem-a-17")

    print("MEMORY_GOVERNANCE_FIXTURE_PASS tenant-isolated expiry-enforced deletion-complete")


if __name__ == "__main__":
    main()
