from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.capture.agent_fixture import (
    FixtureValidationError,
    load_scenario_corpus,
    validate_coverage,
    validate_scenario,
    validate_upstream_script,
)
from cutctx.capture.fixture_safety import assert_fixture_safe

FIXTURES = Path(__file__).with_name("fixtures")


def test_scenario_schema_rejects_unknown_actions() -> None:
    scenario = {
        "schema_version": 1,
        "id": "bad-action",
        "client": "codex",
        "client_version": "test",
        "tags": ["resume"],
        "runtimes": ["python"],
        "unsupported_runtimes": [
            {
                "runtime": "native",
                "reason": "not implemented",
                "tracking_issue": "TEST-1",
            }
        ],
        "steps": [{"action": "teleport"}],
        "assertions": {},
    }

    with pytest.raises(FixtureValidationError, match="unsupported action"):
        validate_scenario(scenario)


def test_scenario_schema_requires_explicit_unsupported_runtime_reason() -> None:
    scenario = {
        "schema_version": 1,
        "id": "missing-native-declaration",
        "client": "claude",
        "client_version": "test",
        "tags": ["messages"],
        "runtimes": ["python"],
        "unsupported_runtimes": [{"runtime": "native", "reason": "not implemented"}],
        "steps": [{"action": "request", "transport": "http-json", "path": "/v1/messages"}],
        "assertions": {},
    }

    with pytest.raises(FixtureValidationError, match="tracking_issue"):
        validate_scenario(scenario)


def test_unknown_client_fields_and_upstream_events_are_protocol_drift() -> None:
    scenario = {
        "schema_version": 1,
        "id": "drift",
        "client": "codex",
        "client_version": "test",
        "tags": ["http-sse"],
        "runtimes": ["python"],
        "unsupported_runtimes": [
            {"runtime": "native", "reason": "not implemented", "tracking_issue": "TEST-1"}
        ],
        "steps": [{"action": "request", "transport": "http-sse", "path": "/v1/responses"}],
        "assertions": {},
        "new_client_field": True,
    }
    with pytest.raises(FixtureValidationError, match="unknown scenario fields"):
        validate_scenario(scenario)
    with pytest.raises(FixtureValidationError, match="unknown upstream event"):
        validate_upstream_script(
            {"status": 200, "events": [{"type": "response.brand_new_event"}]},
            client="codex",
        )


def test_committed_fixture_corpus_is_schema_valid_and_covers_required_matrix() -> None:
    scenarios = load_scenario_corpus(FIXTURES)
    coverage = json.loads((FIXTURES / "coverage.json").read_text(encoding="utf-8"))

    assert scenarios
    validate_coverage(scenarios, coverage)

    for scenario in scenarios:
        validate_scenario(scenario)
        assert scenario["runtimes"] or scenario["unsupported_runtimes"]


def test_every_committed_fixture_passes_secret_scan() -> None:
    for path in FIXTURES.rglob("*.json"):
        assert_fixture_safe(json.loads(path.read_text(encoding="utf-8")))
        if path.name.endswith(("sse.json", "ws.json")):
            client = "claude" if "claude-" in path.parent.name else "codex"
            validate_upstream_script(
                json.loads(path.read_text(encoding="utf-8")),
                client=client,
            )


def test_runtime_capability_gaps_are_never_silent() -> None:
    capabilities = json.loads(
        (Path(__file__).with_name("runtime-capabilities.json")).read_text(encoding="utf-8")
    )
    assert set(capabilities["runtimes"]) == {"python", "native"}
    for runtime in capabilities["runtimes"].values():
        for gap in runtime.get("unsupported", []):
            assert gap["reason"]
            assert gap["tracking_issue"]
