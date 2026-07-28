from __future__ import annotations

from scripts.savings_harness import Scenario, build_proxy_command, scenario_passed, scenarios


def _result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "saved_tokens": 10,
        "upstream_calls": 1,
        "requests_sent": 1,
        "response_statuses": [200],
        "stats_status": 200,
        "model_ok": None,
    }
    result.update(overrides)
    return result


def test_savings_harness_rejects_zero_upstream_false_success() -> None:
    scenario = Scenario(name="openai", why="contract", body={}, expect_savings=True)

    assert scenario_passed(scenario, _result(saved_tokens=100, upstream_calls=0)) is False


def test_savings_harness_rejects_non_successful_proxy_response() -> None:
    scenario = Scenario(name="openai", why="contract", body={}, expect_savings=True)

    assert scenario_passed(scenario, _result(response_statuses=[401])) is False


def test_savings_harness_rejects_missing_authenticated_stats_evidence() -> None:
    scenario = Scenario(name="stats", why="contract", body={}, expect_savings=True)

    assert scenario_passed(scenario, _result(stats_status=401)) is False


def test_savings_harness_requires_expected_model_evidence() -> None:
    scenario = Scenario(
        name="routing",
        why="contract",
        body={},
        expect_savings=False,
        expect_upstream_model="claude-haiku-4-5",
    )

    assert scenario_passed(scenario, _result(model_ok=False)) is False


def test_savings_harness_accepts_valid_measured_scenario() -> None:
    scenario = Scenario(name="valid", why="contract", body={}, expect_savings=True)

    assert scenario_passed(scenario, _result()) is True


def test_savings_harness_routes_anthropic_and_openai_to_capture_upstream() -> None:
    scenario = Scenario(name="openai", why="contract", body={})

    command = build_proxy_command(scenario, proxy_port=9123, upstream_port=9124)

    assert command[command.index("--anthropic-api-url") + 1] == "http://127.0.0.1:9124"
    assert command[command.index("--openai-api-url") + 1] == "http://127.0.0.1:9124"


def test_savings_harness_distinguishes_safe_passthrough_from_aggressive_prose() -> None:
    by_name = {scenario.name: scenario for scenario in scenarios()}

    assert by_name["compression:prose"].expect_savings is False
    assert by_name["compression:table"].expect_savings is False
    assert by_name["compression:prose:aggressive"].expect_savings is True
