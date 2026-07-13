from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from cutctx.cli.main import main
from cutctx.proxy.savings_tracker import SavingsTracker
from scripts.generate_buyer_report_smoke import _seed_savings_history

_OBSERVED_SOURCES = {
    "provider_prompt_cache",
}


def _sum_history_tokens(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        total += sum(int(value) for value in (row.get("savings_by_source_tokens") or {}).values())
    return total


def _sum_history_usd(rows: list[dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        total += sum(float(value) for value in (row.get("savings_by_source_usd") or {}).values())
    return round(total, 6)


def _sum_history_source_usd(rows: list[dict[str, Any]], *, observed: bool) -> float:
    total = 0.0
    for row in rows:
        source_usd = row.get("savings_by_source_usd") or {}
        for source, value in source_usd.items():
            if observed and source not in _OBSERVED_SOURCES:
                continue
            if not observed and source in _OBSERVED_SOURCES:
                continue
            total += float(value)
    return round(total, 6)


def _build_reconciliation_payload(snapshot: dict[str, Any], buyer_payload: dict[str, Any]) -> dict[str, Any]:
    history = list(snapshot["history"])
    lifetime = dict(snapshot["lifetime"])
    display_session = dict(snapshot["display_session"])
    lifetime_created = round(float(lifetime["created_savings_usd"]), 6)
    lifetime_observed = round(float(lifetime["observed_provider_savings_usd"]), 6)

    history_tokens = _sum_history_tokens(history)
    history_usd = _sum_history_usd(history)
    history_created_usd = _sum_history_source_usd(history, observed=False)
    history_observed_usd = _sum_history_source_usd(history, observed=True)
    buyer_source_usd = dict(buyer_payload["savings_by_source_usd"])
    buyer_created_usd = round(
        sum(
            float(value)
            for source, value in buyer_source_usd.items()
            if source not in _OBSERVED_SOURCES
        ),
        6,
    )
    buyer_observed_usd = round(
        sum(
            float(value)
            for source, value in buyer_source_usd.items()
            if source in _OBSERVED_SOURCES
        ),
        6,
    )

    payload = {
        "lifetime": {
            "tokens_saved": int(lifetime["tokens_saved"]),
            "created_savings_usd": lifetime_created,
            "observed_provider_savings_usd": lifetime_observed,
            "total_savings_usd": round(lifetime_created + lifetime_observed, 6),
        },
        "display_session": {
            "requests": int(display_session["requests"]),
            "tokens_saved": int(display_session["tokens_saved"]),
            "created_savings_usd": round(float(display_session["created_savings_usd"]), 6),
            "observed_provider_savings_usd": round(
                float(display_session["observed_provider_savings_usd"]),
                6,
            ),
            "total_savings_usd": round(float(display_session["total_savings_usd"]), 6),
        },
        "history": {
            "rows": len(history),
            "tokens_saved_sum": history_tokens,
            "usd_sum": history_usd,
            "created_savings_usd_sum": history_created_usd,
            "observed_provider_savings_usd_sum": history_observed_usd,
        },
        "buyer_report": {
            "tokens_saved": int(buyer_payload["total_tokens_saved"]),
            "usd_saved": round(float(buyer_payload["total_usd_saved"]), 6),
            "created_savings_usd": buyer_created_usd,
            "observed_provider_savings_usd": buyer_observed_usd,
            "savings_by_source": dict(buyer_payload["savings_by_source"]),
            "savings_by_source_usd": buyer_source_usd,
        },
    }

    payload["validation"] = {
        "lifetime_tokens_match_history": payload["lifetime"]["tokens_saved"] == history_tokens,
        "lifetime_tokens_match_buyer_report": payload["lifetime"]["tokens_saved"]
        == payload["buyer_report"]["tokens_saved"],
        "lifetime_total_usd_matches_history": abs(payload["lifetime"]["total_savings_usd"] - history_usd)
        < 1e-6,
        "lifetime_total_usd_matches_buyer_report": abs(
            payload["lifetime"]["total_savings_usd"] - payload["buyer_report"]["usd_saved"]
        )
        < 1e-6,
        "created_usd_matches_history": abs(
            payload["lifetime"]["created_savings_usd"] - history_created_usd
        )
        < 1e-6,
        "observed_usd_matches_history": abs(
            payload["lifetime"]["observed_provider_savings_usd"] - history_observed_usd
        )
        < 1e-6,
        "created_plus_observed_equals_total": abs(
            payload["lifetime"]["created_savings_usd"]
            + payload["lifetime"]["observed_provider_savings_usd"]
            - payload["lifetime"]["total_savings_usd"]
        )
        < 1e-6,
        "display_session_matches_lifetime": payload["display_session"]["tokens_saved"]
        == payload["lifetime"]["tokens_saved"]
        and abs(
            payload["display_session"]["total_savings_usd"] - payload["lifetime"]["total_savings_usd"]
        )
        < 1e-6,
        "buyer_created_usd_matches_lifetime": abs(
            payload["buyer_report"]["created_savings_usd"] - payload["lifetime"]["created_savings_usd"]
        )
        < 1e-6,
        "buyer_observed_usd_matches_lifetime": abs(
            payload["buyer_report"]["observed_provider_savings_usd"]
            - payload["lifetime"]["observed_provider_savings_usd"]
        )
        < 1e-6,
    }
    return payload


def _render_markdown(payload: dict[str, Any]) -> str:
    lifetime = payload["lifetime"]
    history = payload["history"]
    buyer = payload["buyer_report"]
    validation = payload["validation"]
    lines = [
        "# Savings Reconciliation Smoke",
        "",
        "## Lifetime",
        "",
        f"- Tokens saved: {lifetime['tokens_saved']:,}",
        f"- Created by Cutctx: ${lifetime['created_savings_usd']:.2f}",
        f"- Observed at provider: ${lifetime['observed_provider_savings_usd']:.2f}",
        f"- Total savings: ${lifetime['total_savings_usd']:.2f}",
        "",
        "## History Sums",
        "",
        f"- Rows: {history['rows']}",
        f"- Tokens saved sum: {history['tokens_saved_sum']:,}",
        f"- Created by Cutctx sum: ${history['created_savings_usd_sum']:.2f}",
        f"- Observed at provider sum: ${history['observed_provider_savings_usd_sum']:.2f}",
        f"- Total USD sum: ${history['usd_sum']:.2f}",
        "",
        "## Buyer Report",
        "",
        f"- Tokens saved: {buyer['tokens_saved']:,}",
        f"- Created by Cutctx: ${buyer['created_savings_usd']:.2f}",
        f"- Observed at provider: ${buyer['observed_provider_savings_usd']:.2f}",
        f"- Total USD saved: ${buyer['usd_saved']:.2f}",
        "",
        "## Validation",
        "",
    ]
    for key, value in validation.items():
        lines.append(f"- {key}: {'pass' if value else 'fail'}")
    return "\n".join(lines) + "\n"


def generate_savings_reconciliation_smoke(
    *,
    workspace_dir: Path,
    markdown_output: Path,
    json_output: Path,
) -> dict[str, Any]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    savings_path = workspace_dir / "proxy_savings.json"

    previous_savings_path = os.environ.get("CUTCTX_SAVINGS_PATH")
    os.environ["CUTCTX_SAVINGS_PATH"] = str(savings_path)

    try:
        if savings_path.exists():
            savings_path.unlink()
        _seed_savings_history()
        snapshot = SavingsTracker().snapshot()

        runner = CliRunner()
        result = runner.invoke(main, ["report", "buyer", "--days", "3650", "--format", "json"])
        if result.exit_code != 0:
            raise RuntimeError(result.output or "buyer report JSON generation failed")
        buyer_payload = json.loads(result.output)

        payload = _build_reconciliation_payload(snapshot, buyer_payload)

        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(_render_markdown(payload), encoding="utf-8")

        return payload
    finally:
        if previous_savings_path is None:
            os.environ.pop("CUTCTX_SAVINGS_PATH", None)
        else:
            os.environ["CUTCTX_SAVINGS_PATH"] = previous_savings_path


def main_entry() -> None:
    payload = generate_savings_reconciliation_smoke(
        workspace_dir=Path("artifacts/savings-reconciliation-smoke-workspace"),
        markdown_output=Path("artifacts/savings-reconciliation-smoke.md"),
        json_output=Path("artifacts/savings-reconciliation-smoke.json"),
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main_entry()
