#!/usr/bin/env python3
"""Publish a decision-ready savings-canary report from a /stats payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def _load(source: str, admin_key: str | None) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        headers = {"x-cutctx-admin-key": admin_key} if admin_key else {}
        with urlopen(Request(source, headers=headers), timeout=15) as response:  # noqa: S310
            return json.load(response)
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# CutCtx savings canary report",
        "",
        f"- Enabled: {report.get('enabled', False)}",
        f"- Treatment allocation: {report.get('allocation_percent_per_treatment', 0)}% per arm",
        f"- Control allocation: {report.get('control_percent', 100)}%",
        f"- Hard regression limit: {report.get('regression_limit_percent', 1)}%",
        "",
        "| Arm | Requests | Created $ / 1M input | 95% CI | Lift | Decision |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    metrics = report.get("metrics") or {}
    decisions = report.get("decisions") or {}
    for arm in ("control", "mutable_tail", "tool_api_slimming", "model_routing"):
        metric = metrics.get(arm) or {}
        decision = decisions.get(arm) or {}
        ci = metric.get("created_savings_rate_95_percent_ci")
        ci_label = f"{ci[0]:.4f}–{ci[1]:.4f}" if isinstance(ci, list) else "insufficient data"
        lift = decision.get("created_savings_lift_percent")
        lift_label = f"{lift:.2f}%" if isinstance(lift, int | float) else "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    arm,
                    str(metric.get("requests", 0)),
                    f"{float(metric.get('created_savings_usd_per_million_input_tokens', 0)):.6f}",
                    ci_label,
                    lift_label,
                    decision.get("rollout_decision", "baseline"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="/stats URL or saved stats JSON")
    parser.add_argument("--admin-key")
    parser.add_argument("--json-output", default="artifacts/savings-canary-report.json")
    parser.add_argument("--markdown-output", default="artifacts/savings-canary-report.md")
    args = parser.parse_args()

    payload = _load(args.source, args.admin_key)
    report = payload.get("savings_canary", payload)
    json_path = Path(args.json_output)
    markdown_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
