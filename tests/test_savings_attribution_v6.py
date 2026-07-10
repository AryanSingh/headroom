from __future__ import annotations

import json
from copy import deepcopy

import pytest

from cutctx.proxy.canary_identity import resolve_canary_identity
from cutctx.proxy.savings_canary import CanaryStateError, SavingsCanaryCoordinator
from cutctx.proxy.savings_tracker import SavingsTracker
from cutctx.proxy.schema_compress import compress_tool_results, compress_tool_schemas
from scripts.generate_savings_canary_report import _markdown


def test_v6_reconciles_created_and_observed_sources(tmp_path):
    tracker = SavingsTracker(tmp_path / "savings.json")
    tracker.record_request(
        provider="openai",
        model="gpt-5.4",
        client="codex",
        input_tokens=800,
        tokens_saved=300,
        cache_read_tokens=200,
        savings_by_source_tokens={
            "provider_prompt_cache": 200,
            "cutctx_compression": 80,
            "semantic_cache": 20,
        },
        savings_by_source_usd={
            "provider_prompt_cache": 0.20,
            "cutctx_compression": 0.08,
            "semantic_cache": 0.02,
        },
        eligible_input_tokens=500,
        cache_protected_tokens=200,
        compressed_tokens=100,
        decline_reason="below_threshold",
    )

    lifetime = tracker.snapshot()["lifetime"]
    assert lifetime["created_savings_tokens"] == 100
    assert lifetime["observed_provider_savings_tokens"] == 200
    assert lifetime["created_savings_usd"] == pytest.approx(0.10)
    assert lifetime["observed_provider_savings_usd"] == pytest.approx(0.20)
    assert lifetime["attribution_coverage"]["complete"] is True
    assert lifetime["opportunity_funnel"] == {
        "eligible_input_tokens": 500,
        "cache_protected_tokens": 200,
        "compressed_tokens": 100,
        "declined_tokens": 200,
        "decline_reasons": {"below_threshold": 1},
    }


def test_v6_migration_marks_unreconstructable_requests_partial(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 5,
                "lifetime": {"requests": 10, "tokens_saved": 1000},
                "history": [
                    {
                        "timestamp": "2026-07-01T00:00:00Z",
                        "savings_by_source_tokens": {"cutctx_compression": 50},
                    }
                ],
            }
        )
    )

    lifetime = SavingsTracker(path).snapshot()["lifetime"]
    assert lifetime["attribution_coverage"] == {
        "attributed_requests": 1,
        "legacy_unattributed_requests": 9,
        "coverage_percent": 10.0,
        "complete": False,
    }
    assert lifetime["created_savings_tokens"] == 50


def test_savings_canary_is_sticky_mutually_exclusive_and_guarded():
    coordinator = SavingsCanaryCoordinator(
        enabled=True,
        allocation_percent=10,
        min_samples=2,
        regression_limit=0.01,
        salt="test",
    )
    assignments = [
        coordinator.assign(f"session-{index}", client="codex", model="gpt-5.4")
        for index in range(500)
    ]
    assert {assignment.arm for assignment in assignments} == {
        "control",
        "mutable_tail",
        "tool_api_slimming",
        "model_routing",
    }
    sticky = coordinator.assign("same-session", client="codex", model="gpt-5.4")
    assert coordinator.assign("same-session", client="codex", model="gpt-5.4") == sticky

    for _ in range(2):
        coordinator.record(
            "control",
            input_tokens=1000,
            created_savings_usd=1.0,
            observed_provider_savings_usd=1.0,
            quality_success=True,
        )
        coordinator.record(
            "mutable_tail",
            input_tokens=1000,
            created_savings_usd=0.5,
            observed_provider_savings_usd=0.5,
            quality_success=False,
        )

    decision = coordinator.report()["decisions"]["mutable_tail"]
    assert decision["paused"] is True
    assert decision["rollout_decision"] == "stop"


def test_canary_leaves_non_codex_non_gpt_traffic_in_control():
    coordinator = SavingsCanaryCoordinator(enabled=True)
    assignment = coordinator.assign("x", client="claude-code", model="claude-sonnet-5")
    assert assignment.arm == "control"
    assert assignment.eligible is False


def test_canary_report_contains_confidence_intervals_and_decision():
    coordinator = SavingsCanaryCoordinator(enabled=True, min_samples=2)
    for arm, created in (("control", 1.0), ("model_routing", 1.3)):
        for _ in range(3):
            coordinator.record(
                arm,
                input_tokens=1000,
                created_savings_usd=created,
                observed_provider_savings_usd=1.0,
                quality_success=True,
            )
    report = coordinator.report()
    assert report["metrics"]["model_routing"]["created_savings_rate_95_percent_ci"]
    assert report["decisions"]["model_routing"]["meets_20_percent_lift_target"] is True
    markdown = _markdown(report)
    assert "model_routing" in markdown
    assert "promote_to_25_percent" in markdown
    promoted = coordinator.promote("model_routing", 25)
    assert promoted["allocations"]["model_routing"] == 25
    assert promoted["control_percent"] == 55


def test_canary_promotion_requires_quality_window_lift_and_sequential_steps():
    coordinator = SavingsCanaryCoordinator(enabled=True, min_samples=2)
    with pytest.raises(ValueError, match="full evaluation window"):
        coordinator.promote("model_routing", 25)
    with pytest.raises(ValueError, match="10 to 25 to 50"):
        coordinator.promote("model_routing", 50)


def test_canary_transforms_leave_stable_prefix_and_tool_contract_intact():
    prefix = [
        {"role": "system", "content": "stable cached instructions"},
        {"role": "user", "content": "keep this recent request verbatim"},
    ]
    original_prefix = json.dumps(prefix, sort_keys=True).encode()
    tool_messages = [
        *deepcopy(prefix),
        {
            "role": "tool",
            "content": json.dumps(
                [
                    {"id": index, "name": f"item-{index}", "score": index}
                    for index in range(6)
                ]
            ),
        },
    ]
    transformed = compress_tool_results(
        tool_messages,
        max_array_items_for_positional=25,
        min_fields_for_positional=2,
    )
    assert json.dumps(transformed[:2], sort_keys=True).encode() == original_prefix
    assert transformed[-1]["content"] != tool_messages[-1]["content"]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_repository",
                "description": "Search repository files. " * 30,
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Query"}},
                    "required": ["query"],
                },
            },
        }
    ]
    compacted, modified, _, _ = compress_tool_schemas(
        deepcopy(tools),
        max_description_length=120,
        aggressive=True,
    )
    assert modified is True
    assert compacted[0]["function"]["name"] == "search_repository"
    assert compacted[0]["function"]["parameters"]["required"] == ["query"]


def test_canary_state_survives_restart_and_persists_guardrails(tmp_path):
    state_path = tmp_path / "savings-canary.json"
    coordinator = SavingsCanaryCoordinator(
        enabled=True,
        min_samples=1,
        salt="stable-secret",
        state_path=state_path,
    )
    assignment = coordinator.assign("codex-task-1", client="codex", model="gpt-5.4")
    coordinator.record(
        "control",
        input_tokens=1000,
        created_savings_usd=1.0,
        observed_provider_savings_usd=1.0,
        quality_success=True,
    )
    coordinator.record(
        "mutable_tail",
        input_tokens=1000,
        created_savings_usd=0.5,
        observed_provider_savings_usd=0.5,
        quality_success=False,
    )
    coordinator.record(
        "model_routing",
        input_tokens=1000,
        created_savings_usd=1.3,
        observed_provider_savings_usd=1.0,
        quality_success=True,
    )
    coordinator.promote("model_routing", 25)

    restored = SavingsCanaryCoordinator(
        enabled=True,
        min_samples=1,
        salt="stable-secret",
        state_path=state_path,
    )
    assert restored.report()["metrics"]["control"]["requests"] == 1
    assert restored.report()["decisions"]["mutable_tail"]["paused"] is True
    assert restored.report()["allocations"]["model_routing"] == 25
    assert restored.assign("codex-task-1", client="codex", model="gpt-5.4").arm == assignment.arm
    assert state_path.stat().st_mode & 0o777 == 0o600
    persisted = json.loads(state_path.read_text())
    assert "stable-secret" not in state_path.read_text()
    assert all("codex-task-1" not in key for key in persisted["sticky_assignments"])


def test_canary_feedback_is_idempotent_across_restart(tmp_path):
    state_path = tmp_path / "savings-canary.json"
    coordinator = SavingsCanaryCoordinator(
        enabled=True, salt="stable-secret", state_path=state_path
    )
    assert coordinator.record_feedback(
        "model_routing", event_id="eval/task-1", quality_success=True
    ) is False
    assert coordinator.record_feedback(
        "model_routing", event_id="eval/task-1", quality_success=False
    ) is True
    restored = SavingsCanaryCoordinator(
        enabled=True, salt="stable-secret", state_path=state_path
    )
    assert restored.record_feedback(
        "model_routing", event_id="eval/task-1", quality_success=False
    ) is True
    metrics = restored.report()["metrics"]["model_routing"]
    assert metrics["quality_samples"] == 1
    assert metrics["quality_successes"] == 1


def test_canary_multi_process_style_updates_merge_without_duplicate_feedback(tmp_path):
    state_path = tmp_path / "savings-canary.json"
    first = SavingsCanaryCoordinator(
        enabled=True, salt="stable-secret", state_path=state_path
    )
    stale_sibling = SavingsCanaryCoordinator(
        enabled=True, salt="stable-secret", state_path=state_path
    )
    first.record(
        "control",
        input_tokens=100,
        created_savings_usd=0.1,
        observed_provider_savings_usd=0.1,
    )
    stale_sibling.record(
        "control",
        input_tokens=200,
        created_savings_usd=0.2,
        observed_provider_savings_usd=0.2,
    )
    assert first.record_feedback(
        "control", event_id="shared-event", quality_success=True
    ) is False
    assert stale_sibling.record_feedback(
        "control", event_id="shared-event", quality_success=False
    ) is True

    restored = SavingsCanaryCoordinator(
        enabled=True, salt="stable-secret", state_path=state_path
    )
    metrics = restored.report()["metrics"]["control"]
    assert metrics["requests"] == 2
    assert metrics["input_tokens"] == 300
    assert metrics["quality_samples"] == 1
    assert metrics["quality_successes"] == 1


def test_canary_salt_change_is_blocked_and_corrupt_state_is_quarantined(tmp_path):
    state_path = tmp_path / "savings-canary.json"
    original = SavingsCanaryCoordinator(
        enabled=True, salt="original", state_path=state_path
    )
    original.assign("session", client="codex", model="gpt-5.4")
    with pytest.raises(CanaryStateError, match="salt differs"):
        SavingsCanaryCoordinator(enabled=True, salt="changed", state_path=state_path)

    state_path.write_text("{not-json", encoding="utf-8")
    recovered = SavingsCanaryCoordinator(
        enabled=True, salt="original", state_path=state_path
    )
    assert recovered.report()["metrics"]["control"]["requests"] == 0
    assert list(tmp_path.glob("savings-canary.json.corrupt.*.quarantine"))


def test_codex_identity_is_sticky_private_and_request_fallback_is_excluded():
    first = resolve_canary_identity(
        headers={"Authorization": "Bearer secret", "X-Project-Id": "project-a"},
        body={"conversation": {"id": "conversation-a"}},
        request_id="request-1",
        salt="salt",
    )
    repeated = resolve_canary_identity(
        headers={"Authorization": "Bearer secret", "X-Project-Id": "project-a"},
        body={"conversation": {"id": "conversation-a"}},
        request_id="request-2",
        salt="salt",
    )
    second = resolve_canary_identity(
        headers={"Authorization": "Bearer secret", "X-Project-Id": "project-a"},
        body={"conversation": {"id": "conversation-b"}},
        request_id="request-3",
        salt="salt",
    )
    assert first == repeated
    assert first.value != second.value
    assert "conversation-a" not in first.value

    identity_coordinator = SavingsCanaryCoordinator(enabled=True, salt="salt")
    arms = {
        identity_coordinator.assign(
            f"distinct-session-{index}", client="codex", model="gpt-5.4"
        ).arm
        for index in range(200)
    }
    assert len(arms) > 1

    fallback = resolve_canary_identity(
        headers={}, body={}, request_id="request-only", salt="salt"
    )
    coordinator = SavingsCanaryCoordinator(enabled=True, salt="salt")
    assignment = coordinator.assign(
        fallback.value,
        client="codex",
        model="gpt-5.4",
        identity_source=fallback.source,
        sticky=fallback.sticky,
    )
    assert assignment.arm == "control"
    assert assignment.reason == "non_sticky_identity_excluded"
    assert assignment.assignment_sticky is False
