"""Exercise a configured staged proxy and verify request-trace evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class StagedGatewayNotConfigured(RuntimeError):
    pass


REQUIRED_TRACE_FIELDS = {"request_id", "routing", "latency", "compression", "cache", "fallback"}


def _scenario_trace_matches(trace: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Return whether a structured inspector trace satisfies one scenario's evidence."""
    for dotted_path, expected_value in expected.items():
        current: Any = trace
        for part in dotted_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        if current != expected_value:
            return False
    return True


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    """Load an operator-supplied, non-secret staging exercise contract.

    The base 20-request compression run is always performed. A scenario file adds
    deliberate cache-hit, rate-limit, or fallback requests suited to the staging
    deployment. It is intentionally environment-specific: the runner records
    real behavior instead of pretending that every deployment has those controls
    enabled.
    """
    parsed = json.loads(path.read_text(encoding="utf-8"))
    scenarios = parsed.get("scenarios") if isinstance(parsed, dict) else None
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("staged scenario file must contain a non-empty 'scenarios' list")
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("name"), str):
            raise ValueError("each staged scenario requires a string 'name'")
        request = scenario.get("request")
        if not isinstance(request, dict) or not isinstance(request.get("path"), str):
            raise ValueError(f"scenario {scenario.get('name')!r} requires request.path")
        trace = scenario.get("trace")
        if trace is not None and not isinstance(trace, dict):
            raise ValueError(f"scenario {scenario['name']!r} trace must be an object")
    return scenarios


def staged_gateway_config_from_env() -> tuple[str, str]:
    base_url = os.environ.get("CUTCTX_STAGED_PROXY_BASE_URL", "").rstrip("/")
    admin_key = os.environ.get("CUTCTX_STAGED_PROXY_ADMIN_API_KEY", "")
    if not base_url or not admin_key:
        raise StagedGatewayNotConfigured(
            "CUTCTX_STAGED_PROXY_BASE_URL and CUTCTX_STAGED_PROXY_ADMIN_API_KEY are required"
        )
    return base_url, admin_key


def _messages(index: int) -> list[dict[str, str]]:
    payload = "\n".join(
        f"row={row} status={'error' if row % 7 == 0 else 'ok'} repeated={index % 3}"
        for row in range(80)
    )
    return [
        {"role": "user", "content": "Summarize this output and retain errors."},
        {"role": "tool", "content": payload},
    ]


def run_staged_gateway_smoke(
    *,
    base_url: str,
    admin_key: str,
    request_count: int = 20,
    scenarios: list[dict[str, Any]] | None = None,
    json_output: Path,
    markdown_output: Path,
) -> dict[str, Any]:
    if request_count < 20:
        raise ValueError("request_count must be at least 20")
    import httpx

    # The compression route authenticates hosted API traffic separately from
    # admin-only routes. Keep the admin header for deployments that use it,
    # and send the same configured staging credential through the hosted API
    # header so `/v1/compress` works when hosted compression auth is enabled.
    headers = {
        "x-cutctx-admin-key": admin_key,
        "x-cutctx-api-key": admin_key,
    }
    observed_request_ids: list[str] = []
    scenario_request_ids: dict[str, str] = {}
    with httpx.Client(timeout=60.0) as client:
        for index in range(request_count):
            response = client.post(
                f"{base_url}/v1/compress",
                headers=headers,
                json={"messages": _messages(index), "model": "gpt-4o"},
            )
            response.raise_for_status()
            request_id = response.json().get("request_id")
            if not request_id:
                raise RuntimeError(
                    f"compression request {index} did not return a stable request ID"
                )
            observed_request_ids.append(str(request_id))

        for scenario in scenarios or []:
            request = scenario["request"]
            response = client.request(
                str(request.get("method", "POST")).upper(),
                f"{base_url}{request['path']}",
                headers={**headers, **request.get("headers", {})},
                json=request.get("json"),
            )
            expected_status = int(scenario.get("expected_status", 200))
            if response.status_code != expected_status:
                raise RuntimeError(
                    f"scenario {scenario['name']!r} returned {response.status_code}, "
                    f"expected {expected_status}"
                )
            request_id = response.headers.get("x-request-id")
            if not request_id:
                request_id = response.json().get("request_id") if response.content else None
            if scenario.get("trace") and not request_id:
                raise RuntimeError(f"scenario {scenario['name']!r} did not return a request ID")
            if request_id:
                scenario_request_ids[scenario["name"]] = str(request_id)

        traces_response = client.get(
            f"{base_url}/transformations/traces?limit=100", headers=headers
        )
        traces_response.raise_for_status()
        traces = traces_response.json().get("traces", [])

    trace_by_id = {str(trace.get("request_id")): trace for trace in traces}
    missing = [request_id for request_id in observed_request_ids if request_id not in trace_by_id]
    if missing:
        raise RuntimeError(f"staged traces missing request IDs: {missing[:5]}")

    incomplete = [
        request_id
        for request_id in observed_request_ids
        if not REQUIRED_TRACE_FIELDS.issubset(trace_by_id[request_id])
    ]
    if incomplete:
        raise RuntimeError(f"staged traces missing control-plane fields: {incomplete[:5]}")

    scenario_results: dict[str, str] = {}
    for scenario in scenarios or []:
        expected_trace = scenario.get("trace")
        if not expected_trace:
            scenario_results[scenario["name"]] = "status_only"
            continue
        request_id = scenario_request_ids[scenario["name"]]
        trace = trace_by_id.get(request_id)
        if trace is None:
            raise RuntimeError(f"scenario {scenario['name']!r} is absent from the trace inspector")
        if not _scenario_trace_matches(trace, expected_trace):
            raise RuntimeError(
                f"scenario {scenario['name']!r} trace did not satisfy {expected_trace!r}"
            )
        scenario_results[scenario["name"]] = "trace_verified"

    payload = {
        "status": "passed",
        "base_url": base_url,
        "requests_sent": request_count,
        "traceable_requests": len(observed_request_ids),
        "trace_completeness": round(len(observed_request_ids) / request_count, 4),
        "scenario_results": scenario_results,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(
        "# Staged Gateway Smoke\n\n"
        f"- Requests sent: {request_count}\n"
        f"- Traceable requests: {len(observed_request_ids)}\n"
        f"- Trace completeness: {payload['trace_completeness']:.2%}\n"
        f"- Scenario results: {json.dumps(scenario_results, sort_keys=True)}\n"
        "- Payload bodies and admin credentials are intentionally excluded.\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    try:
        base_url, admin_key = staged_gateway_config_from_env()
    except StagedGatewayNotConfigured as exc:
        print(json.dumps({"status": "not_configured", "reason": str(exc)}, indent=2))
        return
    scenario_path = os.environ.get("CUTCTX_STAGED_SCENARIO_FILE")
    print(
        json.dumps(
            run_staged_gateway_smoke(
                base_url=base_url,
                admin_key=admin_key,
                scenarios=load_scenarios(Path(scenario_path)) if scenario_path else None,
                json_output=Path("artifacts/staged-gateway-smoke.json"),
                markdown_output=Path("artifacts/staged-gateway-smoke.md"),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
