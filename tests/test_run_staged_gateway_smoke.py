from __future__ import annotations

from scripts.run_staged_gateway_smoke import (
    StagedGatewayNotConfigured,
    _scenario_trace_matches,
    load_scenarios,
    staged_gateway_config_from_env,
)


def test_staged_gateway_config_requires_safe_credentials(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_STAGED_PROXY_BASE_URL", raising=False)
    monkeypatch.delenv("CUTCTX_STAGED_PROXY_ADMIN_API_KEY", raising=False)

    try:
        staged_gateway_config_from_env()
    except StagedGatewayNotConfigured as exc:
        assert "CUTCTX_STAGED_PROXY_BASE_URL" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected staged gateway configuration failure")


def test_scenario_trace_matches_nested_inspector_fields() -> None:
    trace = {"cache": {"hit": True}, "fallback": {"attempted": True}}
    assert _scenario_trace_matches(trace, {"cache.hit": True, "fallback.attempted": True})
    assert not _scenario_trace_matches(trace, {"cache.hit": False})
    assert not _scenario_trace_matches(trace, {"fallback.reason": "upstream_5xx"})


def test_load_scenarios_requires_named_request_contract(tmp_path) -> None:
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(
        '{"scenarios":[{"name":"cache-hit","request":{"path":"/v1/compress"},"trace":{"cache.hit":true}}]}',
        encoding="utf-8",
    )
    assert load_scenarios(scenario_file)[0]["name"] == "cache-hit"


def test_load_scenarios_rejects_missing_request_path(tmp_path) -> None:
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text('{"scenarios":[{"name":"bad","request":{}}]}', encoding="utf-8")
    try:
        load_scenarios(scenario_file)
    except ValueError as exc:
        assert "requires request.path" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid scenario contract")
