"""Atomic persistence and lifecycle transitions for workload contracts."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    ContractLifecycle,
    WorkloadContract,
    contract_from_dict,
    contract_to_dict,
)


class ContractConflictError(RuntimeError):
    """Raised when optimistic concurrency or immutable versions conflict."""


class ContractTransitionError(RuntimeError):
    """Raised when a contract lifecycle transition is not allowed."""


_TRANSITIONS: dict[str, set[str]] = {
    ContractLifecycle.DRAFT.value: {
        ContractLifecycle.SHADOW.value,
        ContractLifecycle.RETIRED.value,
    },
    ContractLifecycle.SHADOW.value: {
        ContractLifecycle.DRAFT.value,
        ContractLifecycle.CANARY.value,
        ContractLifecycle.PAUSED.value,
        ContractLifecycle.RETIRED.value,
    },
    ContractLifecycle.CANARY.value: {
        ContractLifecycle.ACTIVE.value,
        ContractLifecycle.PAUSED.value,
        ContractLifecycle.DRAFT.value,
        ContractLifecycle.RETIRED.value,
    },
    ContractLifecycle.ACTIVE.value: {
        ContractLifecycle.PAUSED.value,
        ContractLifecycle.RETIRED.value,
    },
    ContractLifecycle.PAUSED.value: {
        ContractLifecycle.DRAFT.value,
        ContractLifecycle.CANARY.value,
        ContractLifecycle.ACTIVE.value,
        ContractLifecycle.RETIRED.value,
    },
    ContractLifecycle.RETIRED.value: set(),
}


@dataclass(frozen=True)
class StoredContract:
    contract: WorkloadContract
    revision: int
    updated_at: str


class ContractStore:
    """Persist immutable contract versions with atomic lifecycle updates."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    @property
    def revision(self) -> int:
        with self._lock:
            return int(self._load().get("revision", 0))

    def list_contracts(self, contract_id: str | None = None) -> list[WorkloadContract]:
        with self._lock:
            payload = self._load()
            contracts = payload.get("contracts", {})
            if not isinstance(contracts, dict):
                raise ValueError("Invalid contracts store")
            selected = (
                {contract_id: contracts.get(contract_id, {})}
                if contract_id is not None
                else contracts
            )
            result: list[WorkloadContract] = []
            for stored_id in sorted(selected):
                versions = selected[stored_id]
                if not isinstance(versions, dict):
                    raise ValueError(f"Invalid contract versions for {stored_id}")
                for version in sorted(versions):
                    values = versions[version]
                    if not isinstance(values, dict):
                        raise ValueError(f"Invalid contract version: {stored_id}@{version}")
                    result.append(contract_from_dict(values))
            return result

    def get_version(self, contract_id: str, version: str) -> WorkloadContract:
        with self._lock:
            payload = self._load()
            values = (
                payload.get("contracts", {})
                .get(contract_id, {})
                .get(version)
            )
            if not isinstance(values, dict):
                raise KeyError(f"Unknown contract version: {contract_id}@{version}")
            return contract_from_dict(values)

    def put_draft(
        self,
        contract: WorkloadContract,
        *,
        expected_revision: int,
    ) -> StoredContract:
        if contract.state != ContractLifecycle.DRAFT.value:
            raise ContractTransitionError("Only draft contracts may be written")
        with self._lock:
            payload = self._load()
            revision = int(payload.get("revision", 0))
            if revision != expected_revision:
                raise ContractConflictError(
                    f"Expected revision {expected_revision}, found {revision}"
                )
            contracts = payload.setdefault("contracts", {})
            versions = contracts.setdefault(contract.id, {})
            if contract.version in versions:
                raise ContractConflictError(
                    f"Contract version already exists: {contract.id}@{contract.version}"
                )
            versions[contract.version] = contract_to_dict(contract)
            next_revision = revision + 1
            payload["revision"] = next_revision
            updated_at = datetime.now(timezone.utc).isoformat()
            payload["updated_at"] = updated_at
            self._save(payload)
            return StoredContract(
                contract=contract,
                revision=next_revision,
                updated_at=updated_at,
            )

    def transition(
        self,
        contract_id: str,
        version: str,
        target: str,
    ) -> WorkloadContract:
        if target not in {item.value for item in ContractLifecycle}:
            raise ContractTransitionError(f"Unknown contract lifecycle: {target}")
        with self._lock:
            payload = self._load()
            contracts = payload.get("contracts", {})
            versions = contracts.get(contract_id, {}) if isinstance(contracts, dict) else {}
            values = versions.get(version) if isinstance(versions, dict) else None
            if not isinstance(values, dict):
                raise KeyError(f"Unknown contract version: {contract_id}@{version}")
            contract = contract_from_dict(values)
            if target not in _TRANSITIONS[contract.state]:
                raise ContractTransitionError(
                    f"Cannot transition {contract.state} to {target}"
                )
            updated = replace(contract, state=target)
            versions[version] = contract_to_dict(updated)
            if target == ContractLifecycle.ACTIVE.value:
                for other_version, other_values in versions.items():
                    if other_version == version or not isinstance(other_values, dict):
                        continue
                    other = contract_from_dict(other_values)
                    if other.state == ContractLifecycle.ACTIVE.value:
                        versions[other_version] = contract_to_dict(
                            replace(other, state=ContractLifecycle.RETIRED.value)
                        )
            payload["revision"] = int(payload.get("revision", 0)) + 1
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(payload)
            return updated

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"revision": 0, "contracts": {}}
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Invalid contracts store")
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


__all__ = [
    "ContractConflictError",
    "ContractStore",
    "ContractTransitionError",
    "StoredContract",
]
