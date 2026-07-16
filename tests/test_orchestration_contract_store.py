from __future__ import annotations

from dataclasses import replace

import pytest

from cutctx.orchestration.contract_store import (
    ContractConflictError,
    ContractStore,
    ContractTransitionError,
)
from cutctx.orchestration.contracts import WorkloadContract


def _contract(contract_id: str, version: str) -> WorkloadContract:
    return WorkloadContract(
        id=contract_id,
        name=contract_id.replace("-", " ").title(),
        version=version,
    )


def test_put_draft_uses_optimistic_revision_and_keeps_versions_immutable(tmp_path) -> None:
    store = ContractStore(tmp_path / "contracts.json")

    first = store.put_draft(_contract("implementation", "1"), expected_revision=0)
    second = store.put_draft(_contract("implementation", "2"), expected_revision=1)

    assert first.revision == 1
    assert second.revision == 2
    assert store.get_version("implementation", "1") == _contract("implementation", "1")
    with pytest.raises(ContractConflictError, match="already exists"):
        store.put_draft(
            replace(_contract("implementation", "1"), description="replacement"),
            expected_revision=2,
        )


def test_put_draft_rejects_stale_revision(tmp_path) -> None:
    store = ContractStore(tmp_path / "contracts.json")
    store.put_draft(_contract("implementation", "1"), expected_revision=0)

    with pytest.raises(ContractConflictError, match="Expected revision 0, found 1"):
        store.put_draft(_contract("review", "1"), expected_revision=0)


def test_contract_lifecycle_requires_valid_order(tmp_path) -> None:
    store = ContractStore(tmp_path / "contracts.json")
    store.put_draft(_contract("implementation", "1"), expected_revision=0)

    with pytest.raises(ContractTransitionError, match="draft to active"):
        store.transition("implementation", "1", "active")

    assert store.transition("implementation", "1", "shadow").state == "shadow"
    assert store.transition("implementation", "1", "canary").state == "canary"
    assert store.transition("implementation", "1", "active").state == "active"


def test_activating_version_retires_previous_active_version(tmp_path) -> None:
    store = ContractStore(tmp_path / "contracts.json")
    store.put_draft(_contract("implementation", "1"), expected_revision=0)
    store.transition("implementation", "1", "shadow")
    store.transition("implementation", "1", "canary")
    store.transition("implementation", "1", "active")
    store.put_draft(_contract("implementation", "2"), expected_revision=4)
    store.transition("implementation", "2", "shadow")
    store.transition("implementation", "2", "canary")

    activated = store.transition("implementation", "2", "active")

    assert activated.state == "active"
    assert store.get_version("implementation", "1").state == "retired"
    assert [contract.version for contract in store.list_contracts("implementation")] == [
        "1",
        "2",
    ]
