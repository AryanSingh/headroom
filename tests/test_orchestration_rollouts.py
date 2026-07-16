from __future__ import annotations

from pathlib import Path

import pytest

from cutctx.orchestration.config import LayeredConfigStore
from cutctx.orchestration.contract_store import ContractStore, ContractTransitionError
from cutctx.orchestration.contracts import (
    ContractEvaluationPolicy,
    ContractObjective,
    WorkloadContract,
)
from cutctx.orchestration.credentials import EncryptedCredentialStore
from cutctx.orchestration.models import ExecutionRecord, OrchestrationConfig, Role, RouteBinding
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.orchestration.service import OrchestrationService


def _contract(version: str) -> WorkloadContract:
    return WorkloadContract(
        id="implementation",
        name="Implementation",
        version=version,
        baseline_model="openai:gpt-5.4-mini",
        objective=ContractObjective(quality_floor=0.9),
        evaluation=ContractEvaluationPolicy(
            minimum_samples=2,
            unsafe_quality_floor=0.8,
            maximum_unsafe_rate=0.1,
        ),
    )


def _service(tmp_path: Path) -> OrchestrationService:
    config = OrchestrationConfig(
        roles=[Role(id="implementation", name="Implementation")],
        bindings=[
            RouteBinding(
                id="implementation-default",
                role="implementation",
                model="openai:gpt-5.4-mini",
            )
        ],
    )
    store = LayeredConfigStore({"project": tmp_path / "orchestration.json"})
    store.save(config)
    return OrchestrationService(
        config_store=store,
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        contract_store=ContractStore(tmp_path / "contracts.json"),
    )


def test_empty_store_exposes_behavior_preserving_legacy_contracts(tmp_path: Path) -> None:
    service = _service(tmp_path)

    contracts = service.list_contracts()

    assert [(item.id, item.state, item.baseline_model) for item in contracts] == [
        ("implementation", "active", "openai:gpt-5.4-mini")
    ]
    assert service.contract_store.revision == 0


def test_promotion_is_evidence_gated_and_reports_quality_safe_savings(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.put_contract_draft(_contract("1"), expected_revision=0)
    service.transition_contract("implementation", "1", target="shadow")

    with pytest.raises(ContractTransitionError, match="insufficient_evidence"):
        service.promote_contract("implementation", "1", target="canary")

    evidence = service.record_contract_evidence(
        "implementation",
        "1",
        {
            "samples": 2,
            "quality_scores": [0.95, 0.75],
            "accepted": 1,
            "fallbacks": 1,
            "routed_savings_usd": [0.4, 0.3],
        },
    )

    assert evidence["status"] == "quality_blocked"
    assert evidence["raw_routed_savings_usd"] == pytest.approx(0.7)
    assert evidence["quality_safe_savings_usd"] == pytest.approx(0.4)
    with pytest.raises(ContractTransitionError, match="quality_floor_not_met"):
        service.promote_contract("implementation", "1", target="canary")


def test_passing_evidence_allows_canary_activation_and_rollback(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.put_contract_draft(_contract("0"), expected_revision=0)
    service.transition_contract("implementation", "0", target="shadow")
    service.record_contract_evidence(
        "implementation",
        "0",
        {
            "samples": 2,
            "quality_scores": [0.97, 0.96],
            "accepted": 2,
            "fallbacks": 0,
            "routed_savings_usd": [0.2, 0.2],
        },
    )
    service.promote_contract("implementation", "0", target="canary")
    service.promote_contract("implementation", "0", target="active")

    service.put_contract_draft(_contract("1"), expected_revision=4)
    service.transition_contract("implementation", "1", target="shadow")
    service.record_contract_evidence(
        "implementation",
        "1",
        {
            "samples": 2,
            "quality_scores": [0.98, 0.95],
            "accepted": 2,
            "fallbacks": 0,
            "routed_savings_usd": [0.3, 0.3],
        },
    )
    service.promote_contract("implementation", "1", target="canary")
    service.promote_contract("implementation", "1", target="active")

    restored = service.rollback_contract("implementation")

    assert restored.version == "0"
    assert restored.state == "active"
    assert service.get_contract("implementation", "1").state == "paused"


def test_execution_receipt_lookup_uses_the_unified_receipt_schema(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.telemetry.record(
        ExecutionRecord(
            request_id="request-42",
            requested_role="implementation",
            assigned_model="openai:gpt-5.4-mini",
            actual_model="gpt-5.4-mini",
            provider="openai",
            account_id="main",
            binding_id="implementation-default",
            routing_reason="role_binding",
            mode="strict",
            policy="role_locked",
            started_at="2026-07-16T00:00:00+00:00",
        )
    )

    receipt = service.receipt("request-42")

    assert receipt["receipt_version"] == 2
    assert receipt["selected_model"] == "openai:gpt-5.4-mini"
    assert receipt["selected_deployment"] == "openai:main:gpt-5.4-mini"
    assert receipt["evidence"]["executed"] is True


def test_contract_evidence_rejects_impossible_aggregate_counts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.put_contract_draft(_contract("1"), expected_revision=0)

    with pytest.raises(ValueError, match="cannot exceed samples"):
        service.record_contract_evidence(
            "implementation",
            "1",
            {
                "samples": 2,
                "quality_scores": [0.95, 0.96],
                "accepted": 3,
                "fallbacks": 0,
                "routed_savings_usd": [0.2, 0.2],
            },
        )
