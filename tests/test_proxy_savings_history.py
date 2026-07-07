"""Tests for durable proxy savings history."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import cutctx.proxy.savings_tracker as savings_tracker_module
from cutctx.proxy.savings_tracker import CUTCTX_SAVINGS_PATH_ENV_VAR, SavingsTracker
from cutctx.proxy.server import ProxyConfig, create_app


def _record_request(
    client: TestClient,
    *,
    model: str,
    tokens_saved: int,
    input_tokens: int = 120,
) -> None:
    proxy = client.app.state.proxy
    if proxy.cost_tracker:
        proxy.cost_tracker.record_tokens(model, tokens_saved, input_tokens)
    asyncio.run(
        proxy.metrics.record_request(
            provider="openai",
            model=model,
            input_tokens=input_tokens,
            output_tokens=24,
            tokens_saved=tokens_saved,
            latency_ms=15.0,
        )
    )


def test_savings_tracker_helpers_normalize_inputs_and_paths(tmp_path, monkeypatch):
    override_path = tmp_path / "custom-savings.json"
    monkeypatch.setenv(CUTCTX_SAVINGS_PATH_ENV_VAR, str(override_path))
    assert savings_tracker_module.get_default_savings_storage_path() == str(override_path)

    monkeypatch.delenv(CUTCTX_SAVINGS_PATH_ENV_VAR, raising=False)
    default_path = savings_tracker_module.get_default_savings_storage_path()
    assert Path(default_path).as_posix().endswith(".cutctx/proxy_savings.json")

    assert savings_tracker_module._parse_timestamp("") is None
    assert savings_tracker_module._parse_timestamp("not-a-timestamp") is None
    assert savings_tracker_module._parse_timestamp("2026-03-27T09:00:00") == datetime(
        2026, 3, 27, 9, 0, tzinfo=timezone.utc
    )

    assert savings_tracker_module._coerce_int("7") == 7
    assert savings_tracker_module._coerce_int(-5) == 0
    assert savings_tracker_module._coerce_float("0.25") == pytest.approx(0.25)
    assert savings_tracker_module._coerce_float(-0.25) == 0.0

    assert savings_tracker_module._normalize_history_entry(
        ["2026-03-27T09:00:00Z", "12", "0.5"]
    ) == {
        "timestamp": "2026-03-27T09:00:00Z",
        "provider": "unknown",
        "model": "unknown",
        "savings_basis": "estimated",
        "total_tokens_saved": 12,
        "compression_savings_usd": 0.5,
        "compression_savings_observed_usd": 0.0,
        "cache_savings_usd": 0.0,
        "cache_savings_observed_usd": 0.0,
        "semantic_cache_savings_usd": 0.0,
        "semantic_cache_savings_observed_usd": 0.0,
        "self_hosted_prefix_cache_savings_usd": 0.0,
        "self_hosted_prefix_cache_savings_observed_usd": 0.0,
        "model_routing_savings_usd": 0.0,
        "model_routing_savings_observed_usd": 0.0,
        "tool_schema_compaction_savings_usd": 0.0,
        "tool_schema_compaction_savings_observed_usd": 0.0,
        "api_surface_slimming_savings_usd": 0.0,
        "api_surface_slimming_savings_observed_usd": 0.0,
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
        "delta_tokens_saved": 0,
        "delta_savings_usd": 0.0,
        "delta_cache_savings_usd": 0.0,
        "delta_semantic_cache_usd": 0.0,
        "delta_self_hosted_prefix_cache_usd": 0.0,
        "delta_model_routing_usd": 0.0,
        "delta_tool_schema_compaction_usd": 0.0,
        "delta_api_surface_slimming_usd": 0.0,
        "savings_by_source_tokens": {},
        "savings_by_source_usd": {},
    }
    assert savings_tracker_module._normalize_history_entry({"timestamp": "bad"}) is None
    assert savings_tracker_module._normalize_history_entry(object()) is None


def test_savings_tracker_sanitizes_legacy_state_and_applies_retention(tmp_path):
    path = tmp_path / "proxy_savings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 0,
                "lifetime": {
                    "tokens_saved": 1,
                    "compression_savings_usd": 0.001,
                },
                "history": [
                    ["2026-03-24T08:00:00Z", 10, 0.01],
                    {
                        "timestamp": "2026-03-26T12:00:00Z",
                        "total_tokens_saved": 20,
                        "compression_savings_usd": 0.02,
                    },
                    {
                        "timestamp": "2026-03-27T09:00:00Z",
                        "total_tokens_saved": 30,
                        "compression_savings_usd": 0.03,
                    },
                    {"timestamp": "bad", "total_tokens_saved": 999},
                ],
            }
        ),
        encoding="utf-8",
    )

    tracker = SavingsTracker(
        path=str(path),
        max_history_points=1,
        max_history_age_days=2,
    )
    snapshot = tracker.snapshot()

    assert snapshot["schema_version"] == 4
    assert "attribution_note" in snapshot
    assert snapshot["lifetime"] == {
        "requests": 0,
        "tokens_saved": 30,
        "compression_savings_usd": pytest.approx(0.03),
        "compression_savings_observed_usd": 0.0,
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
    }
    assert snapshot["display_session"] == savings_tracker_module._empty_display_session()
    assert snapshot["history"] == [
        {
            "timestamp": "2026-03-27T09:00:00Z",
            "provider": "unknown",
            "model": "unknown",
            "savings_basis": "estimated",
            "total_tokens_saved": 30,
            "compression_savings_usd": 0.03,
            "compression_savings_observed_usd": 0.0,
            "cache_savings_usd": 0.0,
            "cache_savings_observed_usd": 0.0,
            "semantic_cache_savings_usd": 0.0,
            "semantic_cache_savings_observed_usd": 0.0,
            "self_hosted_prefix_cache_savings_usd": 0.0,
            "self_hosted_prefix_cache_savings_observed_usd": 0.0,
            "model_routing_savings_usd": 0.0,
            "model_routing_savings_observed_usd": 0.0,
            "tool_schema_compaction_savings_usd": 0.0,
            "tool_schema_compaction_savings_observed_usd": 0.0,
            "api_surface_slimming_savings_usd": 0.0,
            "api_surface_slimming_savings_observed_usd": 0.0,
            "total_input_tokens": 0,
            "total_input_cost_usd": 0.0,
            "delta_tokens_saved": 0,
            "delta_savings_usd": 0.0,
            "delta_cache_savings_usd": 0.0,
            "delta_semantic_cache_usd": 0.0,
            "delta_self_hosted_prefix_cache_usd": 0.0,
            "delta_model_routing_usd": 0.0,
            "delta_tool_schema_compaction_usd": 0.0,
            "delta_api_surface_slimming_usd": 0.0,
            "savings_by_source_tokens": {},
            "savings_by_source_usd": {},
        }
    ]
    assert snapshot["retention"] == {
        "max_history_points": 1,
        "max_history_age_days": 2,
        "max_response_history_points": 500,
    }


def test_non_dict_savings_state_resets_to_default(tmp_path):
    path = tmp_path / "proxy_savings.json"
    path.write_text("[]", encoding="utf-8")

    tracker = SavingsTracker(path=str(path))
    snapshot = tracker.snapshot()

    assert snapshot["lifetime"] == {
        "requests": 0,
        "tokens_saved": 0,
        "compression_savings_usd": 0.0,
        "compression_savings_observed_usd": 0.0,
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
    }
    assert snapshot["display_session"] == savings_tracker_module._empty_display_session()
    assert snapshot["history"] == []


def test_record_compression_savings_skips_empty_updates_and_normalizes_timestamps(
    tmp_path, monkeypatch
):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(path=str(path))
    monkeypatch.setattr(
        savings_tracker_module,
        "_estimate_compression_savings_usd",
        lambda model, tokens_saved: tokens_saved / 1000.0,
    )

    assert tracker.record_compression_savings(model="gpt-4o", tokens_saved=0) is False
    assert not path.exists()

    local_time = datetime(2026, 3, 27, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    assert tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=10,
        total_input_tokens=120,
        total_input_cost_usd=0.24,
        timestamp=local_time,
    )

    fallback_time = datetime(2026, 3, 27, 12, 34, tzinfo=timezone.utc)
    monkeypatch.setattr(savings_tracker_module, "_utc_now", lambda: fallback_time)
    assert tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=5,
        total_input_tokens=180,
        total_input_cost_usd=0.36,
        timestamp="not-a-timestamp",
    )

    snapshot = tracker.snapshot()
    assert snapshot["history"] == [
        {
            "timestamp": "2026-03-27T08:00:00Z",
            "provider": "unknown",
            "model": "gpt-4o",
            "savings_basis": "estimated",
            "total_tokens_saved": 10,
            "compression_savings_usd": 0.01,
            "total_input_tokens": 120,
            "total_input_cost_usd": 0.24,
        },
        {
            "timestamp": "2026-03-27T12:34:00Z",
            "provider": "unknown",
            "model": "gpt-4o",
            "savings_basis": "estimated",
            "total_tokens_saved": 15,
            "compression_savings_usd": 0.015,
            "total_input_tokens": 180,
            "total_input_cost_usd": 0.36,
        },
    ]

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["lifetime"]["tokens_saved"] == 15
    assert persisted["lifetime"]["total_input_tokens"] == 180
    assert persisted["lifetime"]["total_input_cost_usd"] == pytest.approx(0.36)
    assert persisted["history"][-1]["timestamp"] == "2026-03-27T12:34:00Z"


def test_savings_tracker_save_does_not_flock_target_inode_before_replace(tmp_path, monkeypatch):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(path=str(path))

    tracker.record_request(
        model="gpt-4o",
        input_tokens=120,
        tokens_saved=10,
        timestamp="2026-03-27T09:00:00Z",
    )
    assert path.exists()

    flock_calls: list[int] = []

    class _FcntlSpy:
        LOCK_EX = 1
        LOCK_UN = 2

        def flock(self, _fh, operation: int) -> None:
            flock_calls.append(operation)

    monkeypatch.setattr(savings_tracker_module, "_HAS_FCNTL", True, raising=False)
    monkeypatch.setattr(savings_tracker_module, "_fcntl", _FcntlSpy(), raising=False)

    tracker.record_request(
        model="gpt-4o",
        input_tokens=80,
        tokens_saved=5,
        timestamp="2026-03-27T09:10:00Z",
    )

    assert flock_calls == []
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["lifetime"]["tokens_saved"] == 15


def test_litellm_resolution_and_savings_estimation_fallbacks(monkeypatch):
    def fake_cost_per_token(*, model, prompt_tokens, completion_tokens):
        if model in {"gpt-4o", "anthropic/claude-sonnet-4-6"}:
            return {
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        raise RuntimeError("unknown model")

    fake_litellm = SimpleNamespace(
        cost_per_token=fake_cost_per_token,
        model_cost={
            "anthropic/claude-sonnet-4-6": {"input_cost_per_token": 0.002},
            "gpt-4o": {"input_cost_per_token": 0.001},
        },
    )
    monkeypatch.setattr(savings_tracker_module, "LITELLM_AVAILABLE", True)
    monkeypatch.setattr(savings_tracker_module, "litellm", fake_litellm)

    assert savings_tracker_module._resolve_litellm_model("gpt-4o") == "gpt-4o"
    assert (
        savings_tracker_module._resolve_litellm_model("claude-sonnet-4-6")
        == "anthropic/claude-sonnet-4-6"
    )
    assert savings_tracker_module._estimate_compression_savings_usd(
        "claude-sonnet-4-6", 100
    ) == pytest.approx(0.2)
    assert savings_tracker_module._estimate_input_cost_usd(
        "claude-sonnet-4-6",
        100,
        cache_read_tokens=10,
        cache_write_tokens=5,
        uncached_input_tokens=85,
    ) == pytest.approx(0.2)

    fake_litellm.model_cost = {}
    assert savings_tracker_module._estimate_compression_savings_usd("gpt-4o", 100) == 0.0
    assert savings_tracker_module._estimate_input_cost_usd("gpt-4o", 100) == 0.0

    monkeypatch.setattr(
        fake_litellm,
        "cost_per_token",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert savings_tracker_module._resolve_litellm_model("mystery-model") == "mystery-model"
    assert savings_tracker_module._estimate_compression_savings_usd("mystery-model", 100) == 0.0

    monkeypatch.setattr(savings_tracker_module, "LITELLM_AVAILABLE", False)
    assert savings_tracker_module._estimate_compression_savings_usd("gpt-4o", 100) == 0.0
    assert savings_tracker_module._estimate_input_cost_usd("gpt-4o", 100) == 0.0


def test_display_session_rolls_after_inactivity_and_counts_zero_savings_requests(
    tmp_path, monkeypatch
):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(path=str(path), display_session_inactivity_minutes=30)
    # A0/A4 changed USD computation to use value_tokens_usd with real litellm
    # pricing. Monkeypatch both for deterministic test values.
    import cutctx.proxy.savings_pricing as sp
    monkeypatch.setattr(
        sp, "value_tokens_usd",
        lambda model, tokens, rate_per_million=None: tokens / 1000.0 if rate_per_million is None else (rate_per_million / 1_000_000) * tokens,
    )
    monkeypatch.setattr(
        savings_tracker_module,
        "_estimate_compression_savings_usd",
        lambda model, tokens_saved: tokens_saved / 1000.0,
    )
    monkeypatch.setattr(
        savings_tracker_module,
        "_estimate_input_cost_usd",
        lambda model, input_tokens, **kwargs: input_tokens / 1000.0,
    )

    tracker.record_request(
        model="gpt-4o",
        input_tokens=120,
        tokens_saved=0,
        timestamp="2026-03-27T09:00:00Z",
    )
    tracker.record_request(
        model="gpt-4o",
        input_tokens=80,
        tokens_saved=20,
        timestamp="2026-03-27T09:10:00Z",
    )

    monkeypatch.setattr(
        savings_tracker_module,
        "_utc_now",
        lambda: datetime(2026, 3, 27, 9, 15, tzinfo=timezone.utc),
    )
    active_session = tracker.snapshot()["display_session"]
    assert active_session == {
        "requests": 2,
        "tokens_saved": 20,
        "compression_savings_usd": pytest.approx(0.02),
        "compression_savings_observed_usd": pytest.approx(0.02),
        "cache_savings_usd": 0.0,
        "cache_savings_observed_usd": 0.0,
        "semantic_cache_savings_usd": 0.0,
        "semantic_cache_savings_observed_usd": 0.0,
        "self_hosted_prefix_cache_savings_usd": 0.0,
        "self_hosted_prefix_cache_savings_observed_usd": 0.0,
        "model_routing_savings_usd": 0.0,
        "model_routing_savings_observed_usd": 0.0,
        "tool_schema_compaction_savings_usd": 0.0,
        "tool_schema_compaction_savings_observed_usd": 0.0,
        "api_surface_slimming_savings_usd": 0.0,
        "api_surface_slimming_savings_observed_usd": 0.0,
        "total_input_tokens": 200,
        "total_input_cost_usd": pytest.approx(0.2),
        "scaffolding_tokens": 0,
        "ghost_tokens": 0,
        "savings_percent": pytest.approx(10.0),
        "started_at": "2026-03-27T09:00:00Z",
        "last_activity_at": "2026-03-27T09:10:00Z",
    }

    monkeypatch.setattr(
        savings_tracker_module,
        "_utc_now",
        lambda: datetime(2026, 3, 27, 9, 45, tzinfo=timezone.utc),
    )
    assert tracker.snapshot()["display_session"] == savings_tracker_module._empty_display_session()

    tracker.record_request(
        model="gpt-4o",
        input_tokens=50,
        tokens_saved=5,
        timestamp="2026-03-27T10:05:00Z",
    )

    monkeypatch.setattr(
        savings_tracker_module,
        "_utc_now",
        lambda: datetime(2026, 3, 27, 10, 10, tzinfo=timezone.utc),
    )
    rolled = tracker.snapshot()
    assert rolled["lifetime"]["requests"] == 3
    assert rolled["display_session"] == {
        "requests": 1,
        "tokens_saved": 5,
        "compression_savings_usd": pytest.approx(0.005),
        "compression_savings_observed_usd": pytest.approx(0.005),
        "cache_savings_usd": 0.0,
        "cache_savings_observed_usd": 0.0,
        "semantic_cache_savings_usd": 0.0,
        "semantic_cache_savings_observed_usd": 0.0,
        "self_hosted_prefix_cache_savings_usd": 0.0,
        "self_hosted_prefix_cache_savings_observed_usd": 0.0,
        "model_routing_savings_usd": 0.0,
        "model_routing_savings_observed_usd": 0.0,
        "tool_schema_compaction_savings_usd": 0.0,
        "tool_schema_compaction_savings_observed_usd": 0.0,
        "api_surface_slimming_savings_usd": 0.0,
        "api_surface_slimming_savings_observed_usd": 0.0,
        "total_input_tokens": 50,
        "total_input_cost_usd": pytest.approx(0.05),
        "scaffolding_tokens": 0,
        "ghost_tokens": 0,
        "savings_percent": pytest.approx(10.0),
        "started_at": "2026-03-27T10:05:00Z",
        "last_activity_at": "2026-03-27T10:05:00Z",
    }


def test_savings_tracker_rollups_preserve_spend_and_input_history(tmp_path, monkeypatch):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(
        path=str(path),
        max_history_points=100,
        max_history_age_days=30,
    )
    monkeypatch.setattr(
        "cutctx.proxy.savings_tracker._estimate_compression_savings_usd",
        lambda model, tokens_saved: tokens_saved / 1000.0,
    )

    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=100,
        total_input_tokens=120,
        total_input_cost_usd=0.24,
        timestamp="2026-03-27T09:10:00Z",
    )
    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=50,
        total_input_tokens=210,
        total_input_cost_usd=0.42,
        timestamp="2026-03-27T09:40:00Z",
    )
    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=25,
        total_input_tokens=300,
        total_input_cost_usd=0.63,
        timestamp="2026-03-27T10:05:00Z",
    )
    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=10,
        total_input_tokens=360,
        total_input_cost_usd=0.75,
        timestamp="2026-03-28T08:00:00Z",
    )
    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=20,
        total_input_tokens=450,
        total_input_cost_usd=0.93,
        timestamp="2026-04-02T14:00:00Z",
    )

    response = tracker.history_response()

    assert response["lifetime"]["tokens_saved"] == 205
    assert response["lifetime"]["compression_savings_usd"] == pytest.approx(0.205)
    assert response["lifetime"]["total_input_tokens"] == 450
    assert response["lifetime"]["total_input_cost_usd"] == pytest.approx(0.93)
    assert len(response["history"]) == 5

    hourly = response["series"]["hourly"]
    assert [point["timestamp"] for point in hourly] == [
        "2026-03-27T09:00:00Z",
        "2026-03-27T10:00:00Z",
        "2026-03-28T08:00:00Z",
        "2026-04-02T14:00:00Z",
    ]
    assert hourly[0]["tokens_saved"] == 150
    assert hourly[0]["total_tokens_saved"] == 150
    assert hourly[0]["total_input_tokens_delta"] == 210
    assert hourly[0]["total_input_tokens"] == 210
    assert hourly[0]["total_input_cost_usd_delta"] == pytest.approx(0.42)
    assert hourly[0]["total_input_cost_usd"] == pytest.approx(0.42)
    assert hourly[1]["tokens_saved"] == 25
    assert hourly[1]["total_tokens_saved"] == 175
    assert hourly[1]["total_input_tokens_delta"] == 90
    assert hourly[1]["total_input_tokens"] == 300
    assert hourly[1]["total_input_cost_usd_delta"] == pytest.approx(0.21)
    assert hourly[1]["total_input_cost_usd"] == pytest.approx(0.63)
    assert hourly[2]["tokens_saved"] == 10
    assert hourly[2]["total_tokens_saved"] == 185
    assert hourly[2]["total_input_tokens_delta"] == 60
    assert hourly[2]["total_input_tokens"] == 360
    assert hourly[2]["total_input_cost_usd_delta"] == pytest.approx(0.12)
    assert hourly[2]["total_input_cost_usd"] == pytest.approx(0.75)
    assert hourly[3]["tokens_saved"] == 20
    assert hourly[3]["total_tokens_saved"] == 205
    assert hourly[3]["total_input_tokens_delta"] == 90
    assert hourly[3]["total_input_tokens"] == 450
    assert hourly[3]["total_input_cost_usd_delta"] == pytest.approx(0.18)
    assert hourly[3]["total_input_cost_usd"] == pytest.approx(0.93)

    daily = response["series"]["daily"]
    assert [point["timestamp"] for point in daily] == [
        "2026-03-27T00:00:00Z",
        "2026-03-28T00:00:00Z",
        "2026-04-02T00:00:00Z",
    ]
    assert daily[0]["tokens_saved"] == 175
    assert daily[0]["total_tokens_saved"] == 175
    assert daily[0]["total_input_tokens_delta"] == 300
    assert daily[0]["total_input_tokens"] == 300
    assert daily[0]["total_input_cost_usd_delta"] == pytest.approx(0.63)
    assert daily[0]["total_input_cost_usd"] == pytest.approx(0.63)
    assert daily[1]["tokens_saved"] == 10
    assert daily[1]["total_tokens_saved"] == 185
    assert daily[1]["total_input_tokens_delta"] == 60
    assert daily[1]["total_input_tokens"] == 360
    assert daily[1]["total_input_cost_usd_delta"] == pytest.approx(0.12)
    assert daily[1]["total_input_cost_usd"] == pytest.approx(0.75)
    assert daily[2]["tokens_saved"] == 20
    assert daily[2]["total_tokens_saved"] == 205
    assert daily[2]["total_input_tokens_delta"] == 90
    assert daily[2]["total_input_tokens"] == 450
    assert daily[2]["total_input_cost_usd_delta"] == pytest.approx(0.18)
    assert daily[2]["total_input_cost_usd"] == pytest.approx(0.93)

    weekly = response["series"]["weekly"]
    assert [point["timestamp"] for point in weekly] == [
        "2026-03-23T00:00:00Z",
        "2026-03-30T00:00:00Z",
    ]
    assert weekly[0]["tokens_saved"] == 185
    assert weekly[0]["total_tokens_saved"] == 185
    assert weekly[1]["tokens_saved"] == 20
    assert weekly[1]["total_tokens_saved"] == 205

    monthly = response["series"]["monthly"]
    assert [point["timestamp"] for point in monthly] == [
        "2026-03-01T00:00:00Z",
        "2026-04-01T00:00:00Z",
    ]
    assert monthly[0]["tokens_saved"] == 185
    assert monthly[0]["total_tokens_saved"] == 185
    assert monthly[1]["tokens_saved"] == 20
    assert monthly[1]["total_tokens_saved"] == 205

    assert response["exports"]["available_formats"] == ["json", "csv"]
    assert response["exports"]["available_series"] == [
        "history",
        "hourly",
        "daily",
        "weekly",
        "monthly",
    ]


def test_savings_tracker_rollup_attributes_savings_per_provider(tmp_path, monkeypatch):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(
        path=str(path),
        max_history_points=100,
        max_history_age_days=30,
    )
    monkeypatch.setattr(
        "cutctx.proxy.savings_tracker._estimate_compression_savings_usd",
        lambda model, tokens_saved: tokens_saved / 1000.0,
    )

    # Two providers active in the same hour bucket.
    tracker.record_compression_savings(
        model="claude-3-5-sonnet",
        tokens_saved=100,
        provider="anthropic",
        total_input_tokens=120,
        total_input_cost_usd=0.24,
        timestamp="2026-03-27T09:10:00Z",
    )
    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=40,
        provider="openai",
        total_input_tokens=200,
        total_input_cost_usd=0.40,
        timestamp="2026-03-27T09:40:00Z",
    )
    # Only anthropic active in the next hour bucket.
    tracker.record_compression_savings(
        model="claude-3-5-sonnet",
        tokens_saved=25,
        provider="anthropic",
        total_input_tokens=260,
        total_input_cost_usd=0.52,
        timestamp="2026-03-27T10:05:00Z",
    )
    # A legacy-style record with no provider collapses into "unknown".
    tracker.record_compression_savings(
        model="gpt-4o",
        tokens_saved=15,
        total_input_tokens=320,
        total_input_cost_usd=0.64,
        timestamp="2026-03-27T11:00:00Z",
    )

    hourly = tracker.history_response()["series"]["hourly"]

    first = hourly[0]
    assert first["tokens_saved"] == 140
    assert set(first["by_provider"]) == {"anthropic", "openai"}
    assert first["by_provider"]["anthropic"]["tokens_saved"] == 100
    assert first["by_provider"]["anthropic"]["total_input_tokens_delta"] == 120
    assert first["by_provider"]["anthropic"]["compression_savings_usd_delta"] == pytest.approx(0.1)
    assert first["by_provider"]["anthropic"]["total_input_cost_usd_delta"] == pytest.approx(0.24)
    assert first["by_provider"]["openai"]["tokens_saved"] == 40
    assert first["by_provider"]["openai"]["total_input_tokens_delta"] == 80
    assert first["by_provider"]["openai"]["compression_savings_usd_delta"] == pytest.approx(0.04)
    assert first["by_provider"]["openai"]["total_input_cost_usd_delta"] == pytest.approx(0.16)
    # Per-provider deltas sum back to the bucket total.
    assert (
        first["by_provider"]["anthropic"]["tokens_saved"]
        + first["by_provider"]["openai"]["tokens_saved"]
        == first["tokens_saved"]
    )

    second = hourly[1]
    assert set(second["by_provider"]) == {"anthropic"}
    assert second["by_provider"]["anthropic"]["tokens_saved"] == 25
    assert second["by_provider"]["anthropic"]["total_input_tokens_delta"] == 60

    third = hourly[2]
    assert set(third["by_provider"]) == {"unknown"}
    assert third["by_provider"]["unknown"]["tokens_saved"] == 15


def test_savings_tracker_rollup_attributes_savings_per_model(tmp_path, monkeypatch):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(
        path=str(path),
        max_history_points=100,
        max_history_age_days=30,
    )

    monkeypatch.setattr(
        "cutctx.proxy.savings_tracker._estimate_compression_savings_usd",
        lambda model, tokens_saved: tokens_saved / 1000.0,
    )

    # Two models from the same provider land in the same bucket.
    tracker.record_compression_savings(
        model="claude-sonnet-4-6",
        tokens_saved=100,
        provider="anthropic",
        total_input_tokens=120,
        total_input_cost_usd=0.24,
        timestamp="2026-03-27T09:10:00Z",
    )
    tracker.record_compression_savings(
        model="claude-opus-4-8",
        tokens_saved=40,
        provider="anthropic",
        total_input_tokens=200,
        total_input_cost_usd=0.40,
        timestamp="2026-03-27T09:40:00Z",
    )
    tracker.record_compression_savings(
        model="claude-sonnet-4-6",
        tokens_saved=25,
        provider="anthropic",
        total_input_tokens=260,
        total_input_cost_usd=0.52,
        timestamp="2026-03-27T10:05:00Z",
    )

    response = tracker.history_response()

    # Checkpoints persist the model alongside the provider.
    assert [point["model"] for point in response["history"]] == [
        "claude-sonnet-4-6",
        "claude-opus-4-8",
        "claude-sonnet-4-6",
    ]

    hourly = response["series"]["hourly"]

    first = hourly[0]
    assert set(first["by_model"]) == {"claude-sonnet-4-6", "claude-opus-4-8"}
    assert first["by_model"]["claude-sonnet-4-6"]["tokens_saved"] == 100
    assert first["by_model"]["claude-sonnet-4-6"]["total_input_tokens_delta"] == 120
    assert first["by_model"]["claude-sonnet-4-6"]["compression_savings_usd_delta"] == pytest.approx(
        0.1
    )
    assert first["by_model"]["claude-sonnet-4-6"]["total_input_cost_usd_delta"] == pytest.approx(
        0.24
    )
    assert first["by_model"]["claude-opus-4-8"]["tokens_saved"] == 40
    # Per-model deltas sum back to the bucket total.
    assert (
        first["by_model"]["claude-sonnet-4-6"]["tokens_saved"]
        + first["by_model"]["claude-opus-4-8"]["tokens_saved"]
        == first["tokens_saved"]
    )

    second = hourly[1]
    assert set(second["by_model"]) == {"claude-sonnet-4-6"}
    assert second["by_model"]["claude-sonnet-4-6"]["tokens_saved"] == 25

    # The expected no-cutctx cost is derivable per bucket: actual input cost
    # delta plus the compression savings delta.
    sonnet = first["by_model"]["claude-sonnet-4-6"]
    assert sonnet["total_input_cost_usd_delta"] + sonnet["compression_savings_usd_delta"] == (
        pytest.approx(0.34)
    )


def test_legacy_checkpoints_without_model_collapse_into_unknown(tmp_path):
    path = tmp_path / "proxy_savings.json"
    legacy_state = {
        "schema_version": 2,
        "lifetime": {
            "requests": 1,
            "tokens_saved": 50,
            "compression_savings_usd": 0.05,
            "total_input_tokens": 100,
            "total_input_cost_usd": 0.2,
        },
        "history": [
            {
                "timestamp": "2026-03-27T09:10:00Z",
                "provider": "anthropic",
                "total_tokens_saved": 50,
                "compression_savings_usd": 0.05,
                "total_input_tokens": 100,
                "total_input_cost_usd": 0.2,
            }
        ],
    }
    path.write_text(json.dumps(legacy_state), encoding="utf-8")

    tracker = SavingsTracker(path=str(path))
    response = tracker.history_response()

    assert response["history"][0]["model"] == "unknown"
    hourly = response["series"]["hourly"]
    assert set(hourly[0]["by_model"]) == {"unknown"}
    assert hourly[0]["by_model"]["unknown"]["tokens_saved"] == 50


def test_stats_history_defaults_to_compact_history_but_can_return_full_history(
    tmp_path, monkeypatch
):
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(
        path=str(path),
        max_history_points=100,
        max_history_age_days=30,
        max_response_history_points=5,
    )
    monkeypatch.setattr(
        "cutctx.proxy.savings_tracker._estimate_compression_savings_usd",
        lambda model, tokens_saved: tokens_saved / 1000.0,
    )

    for i in range(8):
        tracker.record_compression_savings(
            model="gpt-4o",
            tokens_saved=10,
            total_input_tokens=(i + 1) * 100,
            total_input_cost_usd=(i + 1) * 0.1,
            timestamp=f"2026-03-27T09:{i:02d}:00Z",
        )

    compact = tracker.history_response()
    assert compact["history_summary"] == {
        "mode": "compact",
        "stored_points": 8,
        "returned_points": 5,
        "compacted": True,
    }
    assert len(compact["history"]) == 5
    assert compact["history"][0]["timestamp"] == "2026-03-27T09:00:00Z"
    assert compact["history"][-1]["timestamp"] == "2026-03-27T09:07:00Z"

    full = tracker.history_response(history_mode="full")
    assert full["history_summary"] == {
        "mode": "full",
        "stored_points": 8,
        "returned_points": 8,
        "compacted": False,
    }
    assert len(full["history"]) == 8

    none = tracker.history_response(history_mode="none")
    assert none["history"] == []
    assert none["history_summary"] == {
        "mode": "none",
        "stored_points": 8,
        "returned_points": 0,
        "compacted": True,
    }


def test_stats_history_persists_across_restarts_and_stats_stays_compatible(tmp_path, monkeypatch):
    savings_path = tmp_path / "proxy_savings.json"
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))
    monkeypatch.setattr(
        "cutctx.proxy.server.CostTracker._get_cache_prices",
        lambda self, model: (0.001, 0.0015, 0.002),
    )

    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )

    with TestClient(create_app(config)) as client:
        _record_request(client, model="gpt-4o", tokens_saved=40)

        stats = client.get("/stats")
        assert stats.status_code == 200
        stats_data = stats.json()
        assert "savings_history" in stats_data
        assert "persistent_savings" in stats_data
        assert all(len(point) == 2 for point in stats_data["savings_history"])
        assert stats_data["persistent_savings"]["lifetime"]["tokens_saved"] == 40
        assert stats_data["persistent_savings"]["storage_path"] == str(savings_path)

        history = client.get("/stats-history")
        assert history.status_code == 200
        history_data = history.json()
        assert history_data["schema_version"] >= 3  # may be 4 after migration
        assert history_data["storage_path"] == str(savings_path)
        assert history_data["lifetime"]["tokens_saved"] == 40
        assert history_data["lifetime"]["total_input_tokens"] == 120
        assert history_data["lifetime"]["total_input_cost_usd"] == pytest.approx(0.24)
        assert history_data["display_session"]["requests"] == 1
        assert history_data["display_session"]["tokens_saved"] == 40
        assert history_data["display_session"]["total_input_tokens"] == 120
        assert history_data["display_session"]["savings_percent"] == pytest.approx(33.33)
        assert list(history_data["series"].keys()) == [
            "hourly",
            "daily",
            "weekly",
            "monthly",
        ]
        assert history_data["exports"]["available_series"][-2:] == ["weekly", "monthly"]
        assert history_data["series"]["hourly"][0]["total_input_tokens_delta"] == 120
        assert history_data["series"]["hourly"][0]["total_input_cost_usd_delta"] == pytest.approx(
            0.24
        )
        assert history_data["history_summary"] == {
            "mode": "compact",
            "stored_points": 1,
            "returned_points": 1,
            "compacted": False,
        }

        assert stats_data["display_session"] == history_data["display_session"]
        assert (
            stats_data["persistent_savings"]["display_session"] == history_data["display_session"]
        )

    with TestClient(create_app(config)) as client:
        history = client.get("/stats-history")
        assert history.status_code == 200
        assert history.json()["lifetime"]["tokens_saved"] == 40
        assert history.json()["display_session"]["requests"] == 1

        _record_request(client, model="gpt-4o", tokens_saved=15)

        updated = client.get("/stats-history").json()
        assert updated["lifetime"]["tokens_saved"] == 55
        assert updated["lifetime"]["total_input_tokens"] == 240
        assert updated["lifetime"]["total_input_cost_usd"] == pytest.approx(0.48)
        assert updated["lifetime"]["requests"] == 2
        assert len(updated["history"]) == 2
        assert updated["display_session"]["requests"] == 2
        assert updated["display_session"]["tokens_saved"] == 55
        assert updated["display_session"]["total_input_tokens"] == 240
        assert updated["display_session"]["savings_percent"] == pytest.approx(22.92)
        assert updated["series"]["daily"][0]["total_input_tokens_delta"] == 240
        assert updated["series"]["daily"][0]["total_input_cost_usd_delta"] == pytest.approx(0.48)

        full = client.get("/stats-history?history_mode=full").json()
        assert full["history_summary"]["mode"] == "full"
        assert full["history_summary"]["stored_points"] == 2
        assert full["history_summary"]["returned_points"] == 2

        persisted = json.loads(savings_path.read_text())
        assert persisted["lifetime"]["tokens_saved"] == 55
        assert persisted["lifetime"]["total_input_tokens"] == 240
        assert persisted["lifetime"]["total_input_cost_usd"] == pytest.approx(0.48)
        assert persisted["display_session"]["requests"] == 2


def test_restart_safe_stats_preserve_models_and_full_source_attribution(tmp_path, monkeypatch):
    savings_path = tmp_path / "proxy_savings.json"
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))
    monkeypatch.setattr(
        "cutctx.proxy.server.CostTracker._get_cache_prices",
        lambda self, model: (0.001, 0.0015, 0.002),
    )

    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )

    with TestClient(create_app(config)) as client:
        proxy = client.app.state.proxy
        asyncio.run(
            proxy.metrics.record_request(
                provider="openai",
                model="gpt-5.4",
                input_tokens=1_000,
                output_tokens=24,
                tokens_saved=100,
                latency_ms=15.0,
                savings_by_source_tokens={
                    "cutctx_compression": 100,
                    "normalization": 30,
                    "batch_routing": 20,
                    "memoization": 10,
                    "output_optimization": 5,
                },
                savings_by_source_usd={
                    "cutctx_compression": 0.10,
                    "normalization": 1.25,
                    "batch_routing": 2.50,
                    "memoization": 3.75,
                    "output_optimization": 4.00,
                },
            )
        )
        asyncio.run(
            proxy.metrics.record_request(
                provider="openai",
                model="gpt-4o",
                input_tokens=500,
                output_tokens=24,
                tokens_saved=40,
                latency_ms=15.0,
                savings_by_source_tokens={"cutctx_compression": 40},
                savings_by_source_usd={"cutctx_compression": 0.04},
            )
        )

    with TestClient(create_app(config)) as client:
        stats = client.get("/stats").json()
        assert stats["requests"]["by_model"] == {}
        assert stats["persistent_savings"]["lifetime"]["tokens_saved"] == 140
        assert stats["savings_by_source"]["tokens"]["normalization"] == 30
        assert stats["savings_by_source"]["tokens"]["batch_routing"] == 20
        assert stats["savings_by_source"]["tokens"]["memoization"] == 10
        assert stats["savings_by_source"]["tokens"]["output_optimization"] == 5
        assert stats["savings_by_source"]["usd"]["normalization"] == pytest.approx(1.25)
        assert stats["savings_by_source"]["usd"]["batch_routing"] == pytest.approx(2.50)
        assert stats["savings_by_source"]["usd"]["memoization"] == pytest.approx(3.75)
        assert stats["savings_by_source"]["usd"]["output_optimization"] == pytest.approx(4.00)

        history = client.get("/stats-history").json()
        hourly = history["series"]["hourly"][0]
        assert set(hourly["by_model"]) == {"gpt-5.4", "gpt-4o"}
        assert hourly["by_model"]["gpt-5.4"]["tokens_saved"] == 100
        assert hourly["by_model"]["gpt-4o"]["tokens_saved"] == 40


def test_stats_history_csv_export_is_frontend_friendly(tmp_path, monkeypatch):
    savings_path = tmp_path / "proxy_savings.json"
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))
    monkeypatch.setattr(
        "cutctx.proxy.server.CostTracker._get_cache_prices",
        lambda self, model: (0.001, 0.0015, 0.002),
    )

    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )

    with TestClient(create_app(config)) as client:
        _record_request(client, model="gpt-4o", tokens_saved=40)
        _record_request(client, model="gpt-4o", tokens_saved=10)

        response = client.get("/stats-history?format=csv&series=daily")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert (
            'attachment; filename="cutctx-stats-history-daily.csv"'
            == response.headers["content-disposition"]
        )
        lines = response.text.strip().splitlines()
        assert lines[0] == (
            "timestamp,tokens_saved,compression_savings_usd_delta,total_tokens_saved,"
            "compression_savings_usd,total_input_tokens_delta,total_input_tokens,"
            "total_input_cost_usd_delta,total_input_cost_usd"
        )
        assert len(lines) >= 2
        assert "total_tokens_saved" in lines[0]
        assert "total_input_cost_usd" in lines[0]


def test_malformed_savings_state_is_ignored_safely(tmp_path, monkeypatch):
    savings_path = tmp_path / "proxy_savings.json"
    savings_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))

    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )

    with TestClient(create_app(config)) as client:
        response = client.get("/stats-history")
        assert response.status_code == 200
        data = response.json()
        assert data["lifetime"]["tokens_saved"] == 0
        assert data["history"] == []


def test_dashboard_includes_history_toggle_and_endpoint(tmp_path, monkeypatch):
    savings_path = tmp_path / "proxy_savings.json"
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))

    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )

    with TestClient(create_app(config)) as client:
        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.text
        assert "<!doctype html>" in html.lower()
        if 'id="root"' in html:
            assert "/assets/index-" in html
            assert "/assets/index-" in html
        else:
            assert "Session" in html
            assert "Historical" in html
            assert "fetch('/stats-history')" in html
            assert "Export CSV" in html
            assert "Weekly Savings" in html
            assert "Monthly Savings" in html
            assert "Per-Model Breakdown" in html
            assert "historyChartModeOptions" in html
            assert "Expected cost (without Cutctx)" in html
            assert "toggleHistoryModel" in html
            # Checkpoint view plots no per-model lines, so an active model
            # filter must not suppress the aggregate line there.
            assert "if (this.historySelectedSeriesKey === 'history') return null;" in html
            # Breakdown header labels the effective (substituted) series.
            assert "historyModelSourceSeriesLabel + ' buckets'" in html
            # Non-top-5 breakdown rows swap into the last chart slot when selected.
            assert "topModels[topModels.length - 1] = selected;" in html
