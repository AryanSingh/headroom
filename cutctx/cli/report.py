"""CLI report commands for Cutctx scheduled exports."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import click

from .main import main

_BUYER_CAVEAT = "Rates below are for eligible compressible payloads unless labeled all-traffic."

_BUYER_ELIGIBLE_NOTE = (
    "Eligible requests = total requests minus those bypassed as too small to compress."
)

_BUYER_NO_BYPASS_NOTE = (
    "No request in this period recorded a bypassed-as-too-small reason, so the "
    "eligible rate is the all-traffic rate. Treat them as one measurement, not two."
)

_SMALL_DECLINE_REASONS = frozenset(
    {
        "below_threshold",
        "too_small",
        "below_min_tokens",
    }
)


def _derive_buyer_honesty_fields(row: dict[str, Any]) -> dict[str, bool]:
    """Derive compressed/bypassed_small from persisted tracker telemetry."""
    if "bypassed_small" in row:
        bypassed_small = bool(row["bypassed_small"])
    else:
        reason = row.get("decline_reason")
        normalized = None
        if isinstance(reason, str) and reason.strip():
            from cutctx.proxy.outcome import normalize_decline_reason

            normalized = normalize_decline_reason(reason)
        bypassed_small = normalized in _SMALL_DECLINE_REASONS

    if "compressed" in row:
        compressed = bool(row["compressed"])
    else:
        funnel = row.get("opportunity_funnel") or {}
        compressed_tokens = 0
        if isinstance(funnel, dict):
            compressed_tokens = int(funnel.get("compressed_tokens", 0) or 0)
        sources = row.get("savings_by_source_tokens") or {}
        cutctx_compression = 0
        if isinstance(sources, dict):
            cutctx_compression = int(sources.get("cutctx_compression", 0) or 0)
        compressed = compressed_tokens > 0 or cutctx_compression > 0

    return {"compressed": compressed, "bypassed_small": bypassed_small}


def build_buyer_report_payload(
    rows: list[dict[str, Any]],
    *,
    requests_total: int | None = None,
    scope: str = "retained_history",
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build honesty fields for the buyer ROI report.

    Separates Cutctx-created compression savings from observed provider
    cache discounts, and reports eligible vs all-traffic compression rates.

    RC-2 (audit C7): ``requests_total`` used to be ``len(rows)`` — the size
    of the savings ring buffer, so every report claimed exactly 5,000
    requests against a true lifetime of 139k+. Callers that know the real
    count must pass it; ``requests_rows_observed`` keeps reporting how many
    rows the rates were actually computed from.
    """
    from cutctx.proxy.savings_tracker import split_savings_by_attribution

    rows_observed = len(rows)
    requests_compressed = 0
    requests_bypassed_small = 0
    created_savings_tokens = 0
    observed_provider_cache_tokens = 0
    aggregate_sources: dict[str, int] = {}

    for row in rows:
        sources = row.get("savings_by_source_tokens") or {}
        if not isinstance(sources, dict):
            sources = {}
        created_savings_tokens += int(sources.get("cutctx_compression", 0) or 0)
        observed_provider_cache_tokens += int(sources.get("provider_prompt_cache", 0) or 0)
        for source, tokens in sources.items():
            aggregate_sources[str(source)] = aggregate_sources.get(str(source), 0) + int(
                tokens or 0
            )

        bypassed = bool(row.get("bypassed_small"))
        if bypassed:
            requests_bypassed_small += 1

        compressed = row.get("compressed")
        if compressed is None:
            compressed = int(sources.get("cutctx_compression", 0) or 0) > 0
        if compressed and not bypassed:
            requests_compressed += 1

    cutctx_attributable_tokens, provider_native_tokens = split_savings_by_attribution(
        aggregate_sources
    )
    # Rates are only measurable over the rows we actually have. Dividing a
    # rate measured on 5,000 rows by a lifetime request count would be a
    # different lie from the one being fixed.
    requests_total = rows_observed if requests_total is None else max(0, int(requests_total))
    rate_denominator = rows_observed
    eligible = max(0, rate_denominator - requests_bypassed_small)
    eligible_rate = (requests_compressed / eligible) if eligible else 0.0
    all_traffic_rate = (requests_compressed / rate_denominator) if rate_denominator else 0.0

    # The eligible/all-traffic split is only a real distinction when the
    # request path recorded a below-threshold decline reason. Today most
    # producers emit no per-request reason, so the two rates collapse. Say
    # that out loud rather than printing one number twice as if it were two
    # measurements.
    bypass_telemetry_available = requests_bypassed_small > 0

    return {
        "requests_total": requests_total,
        "requests_rows_observed": rows_observed,
        "rates_measured_over_requests": rate_denominator,
        "scope": scope,
        "history_coverage": coverage or {},
        "requests_compressed": requests_compressed,
        "requests_bypassed_small": requests_bypassed_small,
        "eligible_compression_rate": eligible_rate,
        "all_traffic_compression_rate": all_traffic_rate,
        "bypass_telemetry_available": bypass_telemetry_available,
        "created_savings_tokens": created_savings_tokens,
        "observed_provider_cache_tokens": observed_provider_cache_tokens,
        # RC-3: the split every buyer-facing surface must show.
        "cutctx_attributable_tokens": cutctx_attributable_tokens,
        "provider_native_tokens": provider_native_tokens,
        "caveat": _BUYER_CAVEAT,
        "eligibility_note": (
            _BUYER_ELIGIBLE_NOTE if bypass_telemetry_available else _BUYER_NO_BYPASS_NOTE
        ),
        "request_count_note": (
            f"Compression rates are measured over the {rows_observed} savings rows "
            f"retained on disk; requests_total ({requests_total}) is the request "
            "count for the scope. They are different denominators — do not mix them."
            if requests_total != rows_observed
            else (
                f"Compression rates and requests_total both cover the same "
                f"{rows_observed} retained savings rows."
            )
        ),
    }


def _tracker_scope_facts(days: int) -> dict[str, Any]:
    """Real request counts and retention coverage from the durable tracker.

    RC-1/RC-2 (audit C7): reports used to infer their request count from
    ``len(history_rows)`` — the ring-buffer size — and had no way to say
    whether the requested window was even answerable.
    """
    from cutctx.proxy.savings_tracker import SavingsTracker, get_default_savings_storage_path

    facts: dict[str, Any] = {
        "scope": "all_time" if days <= 0 else "window",
        "requests_total": None,
        "lifetime_requests": None,
        "window_covered": True,
        "window_note": None,
        "history_coverage": {},
    }
    try:
        path = Path(get_default_savings_storage_path())
        if not path.exists():
            return facts
        tracker = SavingsTracker(path=path)
        now = datetime.now(timezone.utc)
        from datetime import timedelta

        start = now - timedelta(days=days) if days > 0 else None
        stats = tracker.get_summary_stats(start_time=start)
    except Exception as exc:  # noqa: BLE001 — a report must not die on telemetry
        facts["window_note"] = f"Could not read the savings tracker: {exc}"
        return facts

    facts["scope"] = stats.get("scope", facts["scope"])
    facts["lifetime_requests"] = stats.get("lifetime_requests")
    facts["window_covered"] = bool(stats.get("window_covered", True))
    facts["window_note"] = stats.get("window_note")
    facts["history_coverage"] = stats.get("history_coverage", {})
    facts["requests_total"] = (
        stats.get("lifetime_requests") if days <= 0 else stats.get("total_requests")
    )
    # The report layer aggregates retained history ROWS, so an "all time"
    # request count paired with row-derived token totals would be two
    # different scopes side by side — the defect this fix exists to remove.
    coverage = facts["history_coverage"] or {}
    if days <= 0 and coverage.get("history_complete") is False:
        facts["scope"] = "all_time_partial_retained_history"
        facts["window_covered"] = False
        facts["window_note"] = (
            "Token and USD totals below are aggregated from the "
            f"{coverage.get('history_points_retained', 0)} savings rows still on disk "
            f"(~{coverage.get('retained_window_hours', 0)}h of history); older rows were "
            "trimmed. They are a LOWER BOUND on all-time savings. The request count is "
            "the true lifetime figure — the two cover different spans."
        )
    return facts


def _get_schedule_path() -> Path:
    """Get the schedule config file path."""
    from cutctx import paths as _paths

    workspace = _paths.workspace_dir()
    return workspace / "report_schedule.json"


def _load_storage():
    """Load storage backend from disk."""
    from cutctx import paths as _paths

    workspace = _paths.workspace_dir()
    db_path = workspace / "cutctx.db"
    if db_path.exists():
        from cutctx.storage import SQLiteStorage

        return SQLiteStorage(str(db_path))
    sessions_dir = workspace / "sessions"
    if sessions_dir.exists() and list(sessions_dir.glob("*.jsonl")):
        from cutctx.storage import JSONLStorage

        return JSONLStorage(str(sessions_dir.parent))
    from cutctx.storage import SQLiteStorage

    return SQLiteStorage(str(db_path))


def _collect_data(days: int) -> list[dict[str, Any]]:
    """Collect savings data for export."""
    storage = _load_storage()
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    start_time = now - timedelta(days=days) if days > 0 else None

    all_time_stats = storage.get_summary_stats()
    filtered_stats = (
        storage.get_summary_stats(start_time=start_time) if days > 0 else all_time_stats
    )

    return [
        {
            "date": now.strftime("%Y-%m-%d"),
            "tokens_before": filtered_stats.get("total_tokens_before", 0),
            "tokens_after": filtered_stats.get("total_tokens_after", 0),
            "tokens_saved": filtered_stats.get("total_tokens_saved", 0),
            "compression_pct": round(
                (
                    filtered_stats.get("total_tokens_saved", 0)
                    / max(filtered_stats.get("total_tokens_before", 1), 1)
                )
                * 100,
                1,
            ),
            # RC-2: the tracker/storage contract is ``total_requests``;
            # ``request_count`` never existed, so this column was always 0.
            "requests": filtered_stats.get(
                "total_requests", filtered_stats.get("request_count", 0)
            ),
            "scope": filtered_stats.get("scope", "all_time" if days <= 0 else "window"),
        }
    ]


def _delta_float(raw: dict[str, Any], key: str) -> float:
    """Read a per-request USD delta, or 0.0 when the row has none.

    Deliberately has no fallback to a lifetime counter — see the note at the
    call site. Anything summable must be a delta.
    """
    try:
        return float(raw.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _delta_int(raw: dict[str, Any], key: str) -> int:
    """Token-count equivalent of :func:`_delta_float`."""
    try:
        return int(raw.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _collect_savings_history(days: int) -> list[dict[str, Any]]:
    """Collect per-request savings history from the durable savings tracker.

    Each row carries provider/model, dollar deltas, and the
    ``savings_by_source_tokens`` breakdown written by
    ``savings_tracker.record_request``. Returns an empty list if the
    tracker file does not exist.
    """
    from datetime import timedelta

    from cutctx.proxy.savings_tracker import (
        SCHEMA_VERSION,
        _normalize_history_entry,
        get_default_savings_storage_path,
    )

    path = get_default_savings_storage_path()
    if not Path(path).exists():
        return []

    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return []

    if payload.get("schema_version") != SCHEMA_VERSION:
        return []

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days) if days > 0 else None
    rows: list[dict[str, Any]] = []
    history = payload.get("history") or []
    for raw in history:
        normalized = _normalize_history_entry(raw)
        if normalized is None:
            continue
        ts_str = normalized.get("timestamp")
        ts = _parse_iso(ts_str) if isinstance(ts_str, str) else None
        if start is not None and ts is not None and ts < start:
            continue
        row = {
            "timestamp": ts_str,
            "provider": normalized.get("provider"),
            "model": normalized.get("model"),
            # Per-request DELTAS only. Never fall back to the lifetime
            # counters that sit alongside them.
            #
            # `compression_savings_usd`, `cache_savings_usd` and
            # `total_tokens_saved` are cumulative running totals — $10,794
            # on the first history row and $12,000 on the last. The old
            # `delta or cumulative` fallback substituted that running total
            # whenever a row had no delta (1,006 of 5,000 rows here), and
            # the caller then SUMS these rows. Summing a monotonic counter
            # as though it were a delta inflated the buyer-facing ROI
            # report by ~9,730x: it reported $1,740,947 saved where the
            # truth was $1,236.
            #
            # A row without a delta contributed nothing measurable, so it
            # contributes zero. Under-reporting an unrecorded row is
            # survivable; inflating an ROI number by four orders of
            # magnitude in front of a buyer is not.
            "tokens_saved": _delta_int(raw, "delta_tokens_saved"),
            "compression_savings_usd": _delta_float(raw, "delta_savings_usd"),
            "cache_savings_usd": _delta_float(raw, "delta_cache_savings_usd"),
            # Deliberately excludes savings_by_source_usd: that dict is a
            # breakdown *of* these same deltas, and adding it here double
            # counted every attributed request.
            "cost_savings_usd": (
                _delta_float(raw, "delta_savings_usd")
                + _delta_float(raw, "delta_cache_savings_usd")
            ),
            "savings_by_source_tokens": dict(normalized.get("savings_by_source_tokens") or {}),
            "savings_by_source_usd": dict(normalized.get("savings_by_source_usd") or {}),
            "opportunity_funnel": dict(normalized.get("opportunity_funnel") or {}),
            "decline_reason": normalized.get("decline_reason"),
        }
        row.update(_derive_buyer_honesty_fields(row))
        rows.append(row)
    return rows


def _parse_iso(value: str):
    """Parse an ISO-8601 timestamp string. Returns None on failure."""
    try:
        # Accept trailing Z and other forms.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        from datetime import datetime as _dt

        parsed = _dt.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    q = min(max(q, 0.0), 1.0)
    idx = int(round((len(sorted_values) - 1) * q))
    return float(sorted_values[idx])


def _collect_request_telemetry(days: int) -> dict[str, Any]:
    """Collect a compact telemetry snapshot from durable request logs."""

    from cutctx.paths import request_history_path

    path = request_history_path()
    if not path.exists():
        return {
            "status": "no_data",
            "requests_observed": 0,
            "providers": {},
            "clients": {},
            "fallback": {"count": 0, "providers": {}, "reasons": {}},
            "decline_reasons": {},
            "routing": {"routed_requests": 0, "model_switches": 0},
            "latency_ms": {"avg": 0.0, "p50": 0.0, "p95": 0.0},
            "optimization_latency_ms": {"avg": 0.0, "p50": 0.0, "p95": 0.0},
            "request_cost_usd": 0.0,
            "note": f"No request history found at {path}",
        }

    now = datetime.now(timezone.utc)
    start = None if days <= 0 else now - __import__("datetime").timedelta(days=days)
    providers: dict[str, int] = {}
    clients: dict[str, int] = {}
    fallback_providers: dict[str, int] = {}
    fallback_reasons: dict[str, int] = {}
    decline_reasons: dict[str, int] = {}
    latency_values: list[float] = []
    optimization_values: list[float] = []
    routed_requests = 0
    model_switches = 0
    request_cost_usd = 0.0
    requests_observed = 0

    try:
        lines = path.read_text().splitlines()
    except OSError:
        lines = []

    for raw_line in lines:
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        ts_str = row.get("timestamp")
        ts = _parse_iso(ts_str) if isinstance(ts_str, str) else None
        if start is not None and ts is not None and ts < start:
            continue

        requests_observed += 1

        provider = str(row.get("provider") or "unknown")
        providers[provider] = providers.get(provider, 0) + 1

        tags = row.get("tags")
        if isinstance(tags, dict):
            client = str(tags.get("client") or "").strip()
            if client:
                clients[client] = clients.get(client, 0) + 1

        fallback = row.get("fallback")
        if isinstance(fallback, dict):
            fallback_provider = str(fallback.get("provider") or "unknown")
            fallback_providers[fallback_provider] = fallback_providers.get(fallback_provider, 0) + 1
            fallback_reason = str(fallback.get("reason") or "unknown")
            fallback_reasons[fallback_reason] = fallback_reasons.get(fallback_reason, 0) + 1

        decline_reason = row.get("decline_reason")
        if isinstance(decline_reason, str) and decline_reason.strip():
            decline_reasons[decline_reason] = decline_reasons.get(decline_reason, 0) + 1

        total_latency = row.get("total_latency_ms")
        if isinstance(total_latency, int | float):
            latency_values.append(float(total_latency))

        optimization_latency = row.get("optimization_latency_ms")
        if isinstance(optimization_latency, int | float):
            optimization_values.append(float(optimization_latency))

        routing = row.get("routing_metadata")
        if isinstance(routing, dict):
            if bool(routing.get("routed")):
                routed_requests += 1
            requested_model = str(routing.get("requested_model") or "").strip()
            actual_model = str(routing.get("actual_model") or row.get("model") or "").strip()
            if requested_model and actual_model and requested_model != actual_model:
                model_switches += 1

        request_cost = row.get("request_cost_usd")
        if isinstance(request_cost, int | float):
            request_cost_usd += float(request_cost)

    latency_values.sort()
    optimization_values.sort()

    def _summary(values: list[float]) -> dict[str, float]:
        if not values:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0}
        return {
            "avg": round(mean(values), 2),
            "p50": round(_quantile(values, 0.50), 2),
            "p95": round(_quantile(values, 0.95), 2),
        }

    return {
        "status": "observed" if requests_observed else "no_data",
        "requests_observed": requests_observed,
        "providers": dict(sorted(providers.items())),
        "clients": dict(sorted(clients.items())),
        "fallback": {
            "count": sum(fallback_providers.values()),
            "providers": dict(sorted(fallback_providers.items())),
            "reasons": dict(sorted(fallback_reasons.items())),
        },
        "decline_reasons": dict(sorted(decline_reasons.items())),
        "routing": {
            "routed_requests": routed_requests,
            "model_switches": model_switches,
        },
        "latency_ms": _summary(latency_values),
        "optimization_latency_ms": _summary(optimization_values),
        "request_cost_usd": round(request_cost_usd, 4),
        "note": (
            "Telemetry snapshot derived from durable request history."
            if requests_observed
            else f"No parseable request rows found at {path}"
        ),
    }


@main.group("report")
def report_group() -> None:
    """Generate and schedule reports."""
    pass


@report_group.command("export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Export format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path. Stdout if omitted.")
@click.option("--days", "-d", default=30, help="Number of days to include.")
def report_export(fmt: str, output: str | None, days: int) -> None:
    """Export savings data to JSON or CSV.

    \b
    Examples:
        cutctx report export                    JSON to stdout
        cutctx report export --format csv -o report.csv
        cutctx report export --days 7           Last 7 days only
    """
    data = _collect_data(days)

    if fmt == "json":
        content = json.dumps(data, indent=2)
    else:
        import io

        buf = io.StringIO()
        if data:
            writer = csv.DictWriter(buf, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        content = buf.getvalue()

    if output:
        Path(output).write_text(content)
        click.echo(f"Report exported to {output}")
    else:
        click.echo(content)


@report_group.command("schedule")
@click.option("--daily", is_flag=True, help="Run daily.")
@click.option("--weekly", is_flag=True, help="Run weekly.")
@click.option("--email", required=True, help="Email for report delivery.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Report format.",
)
def report_schedule(daily: bool, weekly: bool, email: str, fmt: str) -> None:
    """Schedule automatic report delivery.

    \b
    Examples:
        cutctx report schedule --daily --email ops@company.com
        cutctx report schedule --weekly --email cfo@company.com --format csv
    """
    if not daily and not weekly:
        click.echo("Error: specify --daily or --weekly", err=True)
        return

    schedule_path = _get_schedule_path()
    schedule = {
        "frequency": "daily" if daily else "weekly",
        "email": email,
        "format": fmt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
    }
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    schedule_path.write_text(json.dumps(schedule, indent=2))
    click.echo(f"Report schedule saved to {schedule_path}")
    click.echo(f"  Frequency: {schedule['frequency']}")
    click.echo(f"  Email: {email}")
    click.echo(f"  Format: {fmt}")

    click.echo("\nTo actually run this schedule, you must set up a daemon.")
    click.echo("Option 1: crontab (Linux/macOS)")
    click.echo("-------------------------------")
    cron_freq = "0 8 * * *" if daily else "0 8 * * 1"
    click.echo("Run `crontab -e` and add the following line:")
    click.echo(
        f"{cron_freq} cutctx report export --format {fmt} --days {1 if daily else 7} | mail -s 'Cutctx Report' {email}"
    )

    click.echo("\nOption 2: launchd (macOS)")
    click.echo("-------------------------")
    click.echo("Create ~/Library/LaunchAgents/com.cutctx.report.plist:")
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cutctx.report</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>cutctx report export --format {fmt} --days {
        1 if daily else 7
    } | mail -s 'Cutctx Report' {email}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>{
        ""
        if daily
        else '''
        <key>Weekday</key>
        <integer>1</integer>'''
    }
    </dict>
</dict>
</plist>"""
    click.echo(plist)
    click.echo("\nThen run: launchctl load ~/Library/LaunchAgents/com.cutctx.report.plist")


@report_group.command("schedule-list")
def report_schedule_list() -> None:
    """List configured report schedules."""
    schedule_path = _get_schedule_path()
    if not schedule_path.exists():
        click.echo("No report schedules configured.")
        return
    schedule = json.loads(schedule_path.read_text())
    click.echo(f"Schedule: {schedule.get('frequency', 'unknown')}")
    click.echo(f"  Email: {schedule.get('email', 'N/A')}")
    click.echo(f"  Format: {schedule.get('format', 'json')}")
    click.echo(f"  Enabled: {schedule.get('enabled', False)}")
    click.echo(f"  Created: {schedule.get('created_at', 'N/A')}")


@report_group.command("buyer")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path. Stdout if omitted.",
)
@click.option("--days", "-d", default=30, help="Number of days to include.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Buyer-readable report format.",
)
def report_buyer(output: str | None, days: int, fmt: str) -> None:
    """Phase 5.3: buyer-grade ROI report with defensible savings attribution.

    Breaks savings into provider cache (discount you get for free with
    native caching) and Cutctx compression (the value Cutctx adds on
    top). The two are tracked independently so a buyer can see the
    marginal value of Cutctx above and beyond their existing provider
    prompt cache.

    \b
    Examples:
        cutctx report buyer                Text summary to stdout
        cutctx report buyer --format markdown -o roi.md
        cutctx report buyer --format json -o roi.json
    """
    from cutctx.savings import SavingsSource

    # Phase 5.3: read per-request rows from the durable savings tracker
    # so the buyer report shows actual persisted attribution, not just
    # whatever the legacy storage layer happened to know about.
    data = _collect_savings_history(days)
    if not data:
        # Fall back to the legacy storage aggregator so the report
        # still renders (with zero by_source) instead of failing.
        data = _collect_data(days)
    # Aggregate by source across the collected savings rows.
    by_source: dict[str, int] = {src.value: 0 for src in SavingsSource}
    for row in data:
        sources = row.get("savings_by_source_tokens") or {}
        if isinstance(sources, dict):
            for src, n in sources.items():
                by_source[src] = by_source.get(src, 0) + int(n)
    total_tokens = sum(by_source.values())

    total_usd = 0.0
    compression_usd = 0.0
    cache_usd = 0.0
    by_source_usd: dict[str, float] = {src.value: 0.0 for src in SavingsSource}
    for row in data:
        source_usd = row.get("savings_by_source_usd") or {}
        if isinstance(source_usd, dict) and source_usd:
            row_total = 0.0
            for src, usd in source_usd.items():
                value = float(usd or 0.0)
                by_source_usd[src] = by_source_usd.get(src, 0.0) + value
                row_total += value
            total_usd += row_total
            compression_usd += float(source_usd.get("cutctx_compression", 0.0) or 0.0)
            cache_usd += float(source_usd.get("provider_prompt_cache", 0.0) or 0.0)
        else:
            # Legacy row without per-source USD attribution. Split
            # the legacy dollar figures between Cutctx compression
            # and provider prompt cache so the by-source USD table is
            # consistent: ``total_usd`` and ``by_source_usd`` must
            # agree to the cent. This is the restart-safety
            # attribution the buyer report needs.
            row_compression_usd = float(
                row.get("compression_savings_observed_usd")
                or row.get("compression_savings_usd", 0)
                or 0
            )
            row_cache_usd = float(
                row.get("cache_savings_observed_usd") or row.get("cache_savings_usd", 0) or 0
            )
            row_total = float(row.get("cost_savings_usd", 0) or 0)
            # If only the combined total is present (no per-source
            # split), attribute it all to Cutctx compression — that
            # is what the legacy column actually measured.
            if row_total and not row_compression_usd and not row_cache_usd:
                row_compression_usd = row_total
                row_cache_usd = 0.0
            by_source_usd["cutctx_compression"] = (
                by_source_usd.get("cutctx_compression", 0.0) + row_compression_usd
            )
            by_source_usd["provider_prompt_cache"] = (
                by_source_usd.get("provider_prompt_cache", 0.0) + row_cache_usd
            )
            total_usd += row_compression_usd + row_cache_usd
            compression_usd += row_compression_usd
            cache_usd += row_cache_usd

    from cutctx.proxy.savings_tracker import split_savings_by_attribution

    scope_facts = _tracker_scope_facts(days)
    honesty = build_buyer_report_payload(
        data,
        requests_total=scope_facts.get("requests_total"),
        scope=scope_facts.get("scope", "retained_history"),
        coverage=scope_facts.get("history_coverage") or {},
    )
    cutctx_attributable_tokens, provider_native_tokens = split_savings_by_attribution(by_source)
    scope_label = scope_facts.get("scope", "retained_history")
    scope_lines = [
        f"Scope: {scope_label}"
        + ("" if scope_facts.get("window_covered", True) else " (LOWER BOUND)"),
        f"Requests in scope: {honesty['requests_total']:,} "
        f"(rates measured over {honesty['requests_rows_observed']:,} retained savings rows; "
        f"{int(scope_facts.get('lifetime_requests') or 0):,} lifetime)",
        f"Cutctx-attributable tokens: {cutctx_attributable_tokens:,}",
        f"Provider-native tokens (not Cutctx): {provider_native_tokens:,}",
    ]
    if scope_facts.get("window_note"):
        scope_lines.insert(1, str(scope_facts["window_note"]))

    if fmt == "json":
        payload = {
            "period_days": days,
            "scope": scope_label,
            "window_covered": scope_facts.get("window_covered", True),
            "window_note": scope_facts.get("window_note"),
            "history_coverage": scope_facts.get("history_coverage", {}),
            "lifetime_requests": scope_facts.get("lifetime_requests"),
            # ``total_tokens_saved`` is every source added up, including the
            # provider's own cache. The Cutctx claim is the split below.
            "total_tokens_saved": total_tokens,
            "cutctx_attributable_tokens": cutctx_attributable_tokens,
            "provider_native_tokens": provider_native_tokens,
            "headline_tokens": cutctx_attributable_tokens,
            "headline_basis": "cutctx_attributable_tokens",
            "total_usd_saved": round(total_usd, 4),
            "compression_savings_usd": round(compression_usd, 4),
            "cache_savings_usd": round(cache_usd, 4),
            "savings_by_source": by_source,
            "savings_by_source_total": total_tokens,
            "savings_by_source_usd": {
                src.value: round(by_source_usd.get(src.value, 0.0), 4) for src in SavingsSource
            },
            "savings_sources": [
                {
                    "id": src.value,
                    "label": src.label,
                    "tokens": by_source.get(src.value, 0),
                    "usd": round(by_source_usd.get(src.value, 0.0), 4),
                }
                for src in SavingsSource
            ],
            "attribution_note": (
                "All tracked savings sources are tracked independently. "
                "The total is the sum of per-source values, not a "
                "difference, so there is no double counting. Provider "
                "cache and semantic cache discounts are observed on the "
                "upstream side; Cutctx compression, self-hosted prefix "
                "cache, and model routing are observed on the proxy side."
            ),
            **honesty,
        }
        content = json.dumps(payload, indent=2)
    elif fmt == "markdown":
        lines: list[str] = []
        lines.append(f"# Cutctx ROI Report — last {days} days")
        lines.append("")
        lines.append(f"> {honesty['caveat']}")
        lines.append(">")
        lines.append(f"> {honesty['eligibility_note']}")
        lines.append(">")
        lines.append(f"> {honesty['request_count_note']}")
        lines.append("")
        lines.append("## Scope")
        lines.append("")
        lines.extend(f"- {line}" for line in scope_lines)
        lines.append("")
        lines.append("## Combined savings")
        lines.append("")
        lines.append(f"- **Cutctx-attributable tokens saved:** {cutctx_attributable_tokens:,}")
        lines.append(f"- **Provider-native tokens (not Cutctx):** {provider_native_tokens:,}")
        lines.append(f"- **Total tokens saved (all sources):** {total_tokens:,}")
        lines.append(f"- **Total USD saved:** ${total_usd:,.2f}")
        lines.append(
            f"- **Requests:** {honesty['requests_total']:,} total, "
            f"{honesty['requests_compressed']} compressed, "
            f"{honesty['requests_bypassed_small']} bypassed (too small) "
            f"— rates over {honesty['requests_rows_observed']:,} retained rows"
        )
        lines.append(f"- **Eligible compression rate:** {honesty['eligible_compression_rate']:.1%}")
        lines.append(
            f"- **All-traffic compression rate:** {honesty['all_traffic_compression_rate']:.1%}"
        )
        lines.append(f"- **Created (Cutctx) tokens:** {honesty['created_savings_tokens']:,}")
        lines.append(
            f"- **Observed provider cache tokens:** {honesty['observed_provider_cache_tokens']:,}"
        )
        lines.append("")
        lines.append("## By source")
        lines.append("")
        lines.append("| Source | Tokens |")
        lines.append("|---|---:|")
        for src in SavingsSource:
            n = by_source.get(src.value, 0)
            if n == 0:
                continue
            lines.append(f"| {src.label} | {n:,} |")
        lines.append(f"| **Total** | **{total_tokens:,}** |")
        lines.append("")
        lines.append("## By source USD")
        lines.append("")
        lines.append("| Source | USD |")
        lines.append("|---|---:|")
        for src in SavingsSource:
            usd = by_source_usd.get(src.value, 0.0)
            if usd == 0:
                continue
            lines.append(f"| {src.label} | ${usd:,.2f} |")
        lines.append(f"| **Total** | **${total_usd:,.2f}** |")
        lines.append("")
        lines.append("## Attribution")
        lines.append("")
        lines.append(
            "All tracked savings sources are tracked independently. "
            "The total is the sum of per-source values, not a "
            "difference, so there is no double counting. Provider "
            "prompt cache and semantic cache discounts are observed "
            "on the upstream side; Cutctx compression, self-hosted "
            "prefix cache, and model routing are observed on the "
            "proxy side."
        )
        content = "\n".join(lines) + "\n"
    else:  # text
        lines = []
        lines.append(f"Cutctx ROI Report — last {days} days")
        lines.append("=" * 50)
        lines.append("")
        lines.append(honesty["caveat"])
        lines.append(honesty["eligibility_note"])
        lines.append(honesty["request_count_note"])
        lines.append("")
        lines.extend(scope_lines)
        lines.append("")
        lines.append(f"Cutctx-attributable tokens:{cutctx_attributable_tokens:>12,}")
        lines.append(f"Provider-native tokens:    {provider_native_tokens:>12,}")
        lines.append(f"Total tokens saved (all):  {total_tokens:>12,}")
        lines.append(f"Total USD saved:            ${total_usd:>11,.2f}")
        lines.append(
            f"Requests (compressed/bypassed/rows/total): "
            f"{honesty['requests_compressed']}/"
            f"{honesty['requests_bypassed_small']}/"
            f"{honesty['requests_rows_observed']}/"
            f"{honesty['requests_total']}"
        )
        lines.append(f"Eligible compression rate:  {honesty['eligible_compression_rate']:>11.1%}")
        lines.append(
            f"All-traffic compression:    {honesty['all_traffic_compression_rate']:>11.1%}"
        )
        lines.append(f"Created (Cutctx) tokens:    {honesty['created_savings_tokens']:>12,}")
        lines.append(
            f"Observed provider cache:    {honesty['observed_provider_cache_tokens']:>12,}"
        )
        lines.append("")
        lines.append("By source:")
        for src in SavingsSource:
            n = by_source.get(src.value, 0)
            if n == 0:
                continue
            lines.append(f"  {src.label:30s} {n:>12,}")
        lines.append(f"  {'Total':30s} {total_tokens:>12,}")
        lines.append("")
        lines.append("By source USD:")
        for src in SavingsSource:
            usd = by_source_usd.get(src.value, 0.0)
            if usd == 0:
                continue
            lines.append(f"  {src.label:30s} ${usd:>11,.2f}")
        lines.append(f"  {'Total':30s} ${total_usd:>11,.2f}")
        lines.append("")
        lines.append("Attribution:")
        lines.append("  All tracked savings sources are tracked independently. The total is")
        lines.append("  the sum of per-source values, not a difference, so there")
        lines.append("  is no double counting.")
        content = "\n".join(lines) + "\n"

    if output:
        Path(output).write_text(content)
        click.echo(f"Buyer report written to {output}")
    else:
        click.echo(content)


def _assurance_section() -> dict[str, Any]:
    """Build the assurance section for the agent context report."""
    try:
        from cutctx.assurance import EvidenceLedger

        ledger_path = EvidenceLedger._default_path()
        if not ledger_path.exists():
            return {"status": "no_data", "note": "No local evidence ledger found."}

        ledger = EvidenceLedger()
        stats = ledger.stats()
        return {
            "status": "available",
            "note": "WS7 local evidence ledger active. Run `cutctx report assurance` for bundle.",
            "events": stats["total_events"],
            "chain_intact": not stats["chain"]["chain_broken"],
        }
    except Exception as exc:
        return {"status": "error", "note": f"Could not read assurance ledger: {exc}"}


def _build_agent_context_report(days: int) -> dict[str, Any]:
    """Build a CFO/CISO-forwardable context control-plane report."""

    rows = _collect_savings_history(days)
    telemetry = _collect_request_telemetry(days)
    raw_pipeline_delta_tokens = sum(int(row.get("tokens_saved") or 0) for row in rows)
    total_usd = sum(float(row.get("cost_savings_usd") or 0.0) for row in rows)
    source_tokens: dict[str, int] = {}
    for row in rows:
        for source, tokens in (row.get("savings_by_source_tokens") or {}).items():
            source_tokens[source] = source_tokens.get(source, 0) + int(tokens or 0)

    from cutctx.proxy.savings_tracker import (
        RAW_PIPELINE_DELTA_NOTE,
        SAVINGS_ATTRIBUTION_INVARIANT,
        split_savings_by_attribution,
    )
    from cutctx.proxy.session_replay import is_replay_enabled

    cutctx_attributable_tokens, provider_native_tokens = split_savings_by_attribution(source_tokens)
    by_source_total = cutctx_attributable_tokens + provider_native_tokens
    scope_facts = _tracker_scope_facts(days)
    requests_total = scope_facts.get("requests_total")
    if not requests_total:
        requests_total = len(rows)

    # RC-5 (audit C7): this object used to print the sum of per-request
    # ``delta_tokens_saved`` as "Tokens saved" directly above a by-source
    # table that summed to a different number (76.7M apart on production
    # data), with nothing saying they measured different things. They are
    # now named separately, reconciled, and each explained.
    return {
        "schema_version": "agent_context_report_v1",
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope_facts.get("scope", "all_time" if days <= 0 else "window"),
        "window_covered": scope_facts.get("window_covered", True),
        "window_note": scope_facts.get("window_note"),
        "history_coverage": scope_facts.get("history_coverage", {}),
        "summary": {
            # Real request count for the scope; ``savings_rows_observed`` is
            # how many durable savings rows those figures were computed from.
            "requests": requests_total,
            "savings_rows_observed": len(rows),
            # The one buyer-facing savings number.
            "tokens_saved": cutctx_attributable_tokens,
            "cutctx_attributable_tokens_saved": cutctx_attributable_tokens,
            "provider_native_tokens_saved": provider_native_tokens,
            "raw_pipeline_delta_tokens": raw_pipeline_delta_tokens,
            "usd_saved": round(total_usd, 4),
        },
        "savings_reconciliation": {
            "invariant": SAVINGS_ATTRIBUTION_INVARIANT,
            "cutctx_attributable_tokens": cutctx_attributable_tokens,
            "provider_native_tokens": provider_native_tokens,
            "by_source_total_tokens": by_source_total,
            "invariant_ok": (cutctx_attributable_tokens + provider_native_tokens)
            == by_source_total,
            "raw_pipeline_delta_tokens": raw_pipeline_delta_tokens,
            "raw_vs_by_source_difference": by_source_total - raw_pipeline_delta_tokens,
            "raw_pipeline_delta_note": RAW_PIPELINE_DELTA_NOTE,
            "explanation": (
                "raw_pipeline_delta_tokens sums per-request outcome.tokens_saved; "
                "by_source_total_tokens sums the per-source ledger. They differ "
                "because the ledger also carries provider-native cache reads and "
                "because the cutctx_compression residual is floor-clamped at zero. "
                "Only cutctx_attributable_tokens is a Cutctx claim."
            ),
        },
        "savings_by_source_tokens": dict(sorted(source_tokens.items())),
        "telemetry": telemetry,
        "quality_guard": {
            "status": "observed" if telemetry.get("requests_observed") else "no_data",
            "note": (
                "Telemetry snapshot includes request-level fallback, routing, decline, and latency observations."
                if telemetry.get("requests_observed")
                else "Quality-guard stats will be included once persisted request history exposes them."
            ),
        },
        "policy": {
            "context_policy_env": bool(__import__("os").environ.get("CUTCTX_CONTEXT_POLICY")),
        },
        "assurance": _assurance_section(),
        "session_replay": {
            "enabled": is_replay_enabled(),
            "status": "available" if is_replay_enabled() else "disabled",
        },
    }


def _render_agent_context_report(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, sort_keys=True)

    summary = payload["summary"]
    source_tokens = payload["savings_by_source_tokens"]
    telemetry = payload.get("telemetry") or {}
    latency = telemetry.get("latency_ms") or {}
    optimization_latency = telemetry.get("optimization_latency_ms") or {}
    fallback = telemetry.get("fallback") or {}
    routing = telemetry.get("routing") or {}
    reconciliation = payload.get("savings_reconciliation") or {}
    lines = [
        f"# Agent Context Report — last {payload['period_days']} days",
        "",
        "## Executive Summary",
        "",
        f"- Scope: {payload.get('scope', 'unknown')}"
        + ("" if payload.get("window_covered", True) else " (LOWER BOUND)"),
        f"- Requests in scope: {summary['requests']:,}",
        f"- Savings rows analyzed: {summary.get('savings_rows_observed', 0):,}",
        f"- Cutctx-attributable tokens saved: {summary['tokens_saved']:,}",
        f"- Provider-native tokens (not Cutctx): "
        f"{summary.get('provider_native_tokens_saved', 0):,}",
        f"- Raw pipeline delta (not a savings claim): "
        f"{summary.get('raw_pipeline_delta_tokens', 0):,}",
        f"- Estimated USD saved: ${summary['usd_saved']:,.2f}",
    ]
    if payload.get("window_note"):
        lines.append(f"- Coverage: {payload['window_note']}")
    lines.extend(
        [
            "",
            "## Savings Reconciliation",
            "",
            f"- Invariant: `{reconciliation.get('invariant', 'n/a')}` — "
            f"holds: {reconciliation.get('invariant_ok', False)}",
            f"- By-source total: {int(reconciliation.get('by_source_total_tokens', 0)):,} "
            f"= {int(reconciliation.get('cutctx_attributable_tokens', 0)):,} Cutctx "
            f"+ {int(reconciliation.get('provider_native_tokens', 0)):,} provider-native",
            f"- Raw pipeline delta differs from the by-source total by "
            f"{int(reconciliation.get('raw_vs_by_source_difference', 0)):,} tokens: "
            f"{reconciliation.get('explanation', '')}",
            "",
            "## Savings By Source",
            "",
        ]
    )
    if source_tokens:
        lines.extend(["| Source | Tokens | Attribution |", "|---|---:|---|"])
        from cutctx.proxy.savings_tracker import PROVIDER_NATIVE_SAVINGS_SOURCES

        for source, tokens in source_tokens.items():
            attribution = (
                "provider-native"
                if source in PROVIDER_NATIVE_SAVINGS_SOURCES
                else "cutctx-attributable"
            )
            lines.append(f"| {source} | {tokens:,} | {attribution} |")
    else:
        lines.append("No savings-source rows found for this period.")

    lines.extend(
        [
            "",
            "## Telemetry Snapshot",
            "",
            f"- Telemetry status: {telemetry.get('status', 'no_data')}",
            f"- Request log rows observed: {int(telemetry.get('requests_observed') or 0):,}",
            f"- Fallback events: {int(fallback.get('count') or 0):,}",
            f"- Routed requests: {int(routing.get('routed_requests') or 0):,}",
            f"- Model switches: {int(routing.get('model_switches') or 0):,}",
            f"- Latency p50/p95: {float(latency.get('p50') or 0.0):,.2f} ms / {float(latency.get('p95') or 0.0):,.2f} ms",
            f"- Optimization latency p50/p95: {float(optimization_latency.get('p50') or 0.0):,.2f} ms / {float(optimization_latency.get('p95') or 0.0):,.2f} ms",
            f"- Estimated request cost observed: ${float(telemetry.get('request_cost_usd') or 0.0):,.2f}",
        ]
    )
    providers = telemetry.get("providers") or {}
    if providers:
        lines.append(f"- Providers: {', '.join(f'{k}={v}' for k, v in providers.items())}")
    fallback_providers = fallback.get("providers") or {}
    if fallback_providers:
        lines.append(
            f"- Fallback providers: {', '.join(f'{k}={v}' for k, v in fallback_providers.items())}"
        )
    decline_reasons = telemetry.get("decline_reasons") or {}
    if decline_reasons:
        lines.append(
            f"- Decline reasons: {', '.join(f'{k}={v}' for k, v in decline_reasons.items())}"
        )
    lines.extend(["", f"- Telemetry note: {telemetry.get('note', 'No telemetry note available.')}"])
    lines.extend(
        [
            "",
            "## Governance And Assurance",
            "",
            f"- Quality guard: {payload['quality_guard']['status']}",
            f"- Context policy configured: {payload['policy']['context_policy_env']}",
            f"- Context Assurance: {payload['assurance']['status']} — {payload['assurance']['note']}",
            f"- Session replay: {payload['session_replay']['status']}",
            "",
        ]
    )
    markdown = "\n".join(lines)
    if fmt == "markdown":
        return markdown + "\n"
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>Agent Context Report</title></head><body>"
        + markdown.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>\n")
        + "</body></html>\n"
    )


@report_group.command("agent-context")
@click.option("--days", "-d", default=30, help="Number of days to include.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "html", "json"]),
    default="markdown",
    help="Report format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path. Stdout if omitted.")
def report_agent_context(output: str | None, days: int, fmt: str) -> None:
    """Generate Agent Context Report v1 from existing telemetry."""

    payload = _build_agent_context_report(days)
    content = _render_agent_context_report(payload, fmt)
    if output:
        Path(output).write_text(content)
        click.echo(f"Agent Context Report written to {output}")
    else:
        click.echo(content)


@report_group.command("assurance")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Evidence bundle format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path. Stdout if omitted.")
@click.option("--verify", is_flag=True, help="Verify the local evidence ledger chain.")
def report_assurance(output: str | None, fmt: str, verify: bool) -> None:
    """Export or verify the WS7 Context Assurance evidence ledger."""
    from cutctx.assurance import EvidenceLedger

    ledger = EvidenceLedger()
    if verify:
        content = json.dumps(ledger.verify_chain(), indent=2, sort_keys=True)
    else:
        content = ledger.export_bundle(fmt=fmt)

    if output:
        Path(output).write_text(content)
        click.echo(f"Context Assurance report written to {output}")
    else:
        click.echo(content)


@report_group.command("schedule-cancel")
def report_schedule_cancel() -> None:
    """Cancel all report schedules."""
    schedule_path = _get_schedule_path()
    if schedule_path.exists():
        schedule_path.unlink()
        click.echo("Report schedule cancelled.")
    else:
        click.echo("No schedule to cancel.")
