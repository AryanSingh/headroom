"""Deterministic Product Atlas API contract evidence fixture.

Proves tenant isolation, idempotency, retry-after-accept, and malformed-input
rejection against an in-memory transfer service. The tenant is derived from the
authenticated principal, never from a client-supplied tenant header.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Problem:
    """Stable machine-readable problem record for a rejected request."""

    type: str
    detail: str


@dataclass(frozen=True)
class Transfer:
    id: str
    tenant: str
    account: str
    cents: int
    ledger_entries: int = 1


class TransferService:
    """In-memory contract fixture mirroring the documented Atlas API surface."""

    def __init__(self) -> None:
        self._principals = {"tok-tenant-a": "tenant-a", "tok-tenant-b": "tenant-b"}
        # Accounts are owned by a tenant; acct-b belongs to tenant-b so a
        # tenant-a principal must never see it.
        self._accounts = {"tenant-a": {"acct-a"}, "tenant-b": {"acct-b", "acct-x"}}
        self._by_key: dict[str, Transfer] = {}
        self._next_id = 104

    def _tenant_for(self, token: str) -> Optional[str]:
        return self._principals.get(token)

    def create_transfer(
        self, token: str, account: str, cents: int, idempotency_key: str
    ) -> tuple[Optional[Transfer], Optional[Problem]]:
        tenant = self._tenant_for(token)
        if tenant is None:
            return None, Problem("unauthorized", "principal is not recognized")
        if account not in self._accounts.get(tenant, set()):
            return None, Problem(
                "not_found", "account is not scoped to the authenticated tenant"
            )
        if not isinstance(cents, int) or cents <= 0 or cents > 10_000_000:
            return None, Problem("malformed", "cents must be a positive integer")
        if not idempotency_key or len(idempotency_key) > 64:
            return None, Problem("malformed", "idempotency key is missing or too long")

        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            if existing.account != account or existing.cents != cents:
                return None, Problem(
                    "idempotency_conflict",
                    "the same idempotency key was sent with a changed body",
                )
            return existing, None

        transfer = Transfer(
            id=f"tr-{self._next_id}", tenant=tenant, account=account, cents=cents
        )
        self._next_id += 1
        self._by_key[idempotency_key] = transfer
        return transfer, None

    def status_by_key(self, token: str, idempotency_key: str) -> Optional[Transfer]:
        """Timeout-after-accept retry path: return the original, never a duplicate."""
        tenant = self._tenant_for(token)
        if tenant is None:
            return None
        transfer = self._by_key.get(idempotency_key)
        if transfer is None or transfer.tenant != tenant:
            return None
        return transfer

    @property
    def ledger_size(self) -> int:
        return sum(transfer.ledger_entries for transfer in self._by_key.values())


def main() -> None:
    service = TransferService()
    token_a = "tok-tenant-a"
    token_b = "tok-tenant-b"

    # 1. Valid transfer: tenant-a creates tr-104 on acct-a with one ledger entry.
    created, problem = service.create_transfer(token_a, "acct-a", 1200, "pay-104")
    assert problem is None and created is not None
    assert created.id == "tr-104" and created.tenant == "tenant-a"
    assert created.ledger_entries == 1

    # 2. Duplicate replay: the same key and body return the original transfer.
    replayed, problem = service.create_transfer(token_a, "acct-a", 1200, "pay-104")
    assert problem is None and replayed is not None
    assert replayed.id == "tr-104"
    assert service.ledger_size == 1  # no second ledger entry

    # 3. Timeout after accept: a status retry returns tr-104 with no new mutation.
    retried = service.status_by_key(token_a, "pay-104")
    assert retried is not None and retried.id == "tr-104"
    assert service.ledger_size == 1

    # 4. Same key, changed body: documented conflict, no mutation.
    conflicted, problem = service.create_transfer(token_a, "acct-a", 9999, "pay-104")
    assert problem is not None and problem.type == "idempotency_conflict"
    assert conflicted is None
    assert service.ledger_size == 1

    # 5. Cross-tenant access: tenant-a must never reach tenant-b's acct-b.
    cross, problem = service.create_transfer(token_a, "acct-b", 500, "pay-105")
    assert problem is not None and problem.type == "not_found"
    assert cross is None
    assert service.status_by_key(token_a, "pay-105") is None
    # tenant-b itself can create on acct-b; the principal, not the account, wins.
    owned, problem = service.create_transfer(token_b, "acct-b", 500, "pay-105")
    assert problem is None and owned is not None and owned.tenant == "tenant-b"

    # 6. Malformed input: a non-positive amount is rejected with a problem record.
    malformed, problem = service.create_transfer(token_a, "acct-a", -5, "pay-106")
    assert problem is not None and problem.type == "malformed"
    assert malformed is None
    assert service.status_by_key(token_a, "pay-106") is None

    print("API_CONTRACTS_FIXTURE_PASS tenant-scoped idempotent-conflict malformed-rejected")


if __name__ == "__main__":
    main()
