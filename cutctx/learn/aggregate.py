"""Local-only aggregation for Cutctx Learn.

WS6 intentionally ships the local half only: aggregate anonymized pattern stats
from already-discovered project histories without model calls or network egress.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from cutctx.learn.models import ProjectInfo, SessionData


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _project_id(project: ProjectInfo | Any) -> str:
    path = getattr(project, "project_path", "")
    return _stable_hash(str(Path(path).resolve()))


def aggregate_project_sessions(
    project: ProjectInfo | Any,
    sessions: list[SessionData],
    *,
    agent: str,
) -> dict[str, Any]:
    """Aggregate one project's sessions without leaking content or paths."""

    error_categories: Counter[str] = Counter()
    tool_hashes: Counter[str] = Counter()
    total_calls = 0
    total_failures = 0

    for session in sessions:
        for tool_call in session.tool_calls:
            total_calls += 1
            tool_hashes[_stable_hash(tool_call.name)] += 1
            if tool_call.is_error:
                total_failures += 1
                error_categories[tool_call.error_category.value] += 1

    return {
        "agent": agent,
        "project_id": _project_id(project),
        "session_count": len(sessions),
        "total_calls": total_calls,
        "total_failures": total_failures,
        "failure_rate": (total_failures / total_calls) if total_calls else 0.0,
        "error_categories": dict(sorted(error_categories.items())),
        "tool_name_hashes": dict(sorted(tool_hashes.items())),
    }


def aggregate_projects(
    agent_projects: list[tuple[str, Any, list[Any]]],
    *,
    max_workers: int,
) -> dict[str, Any]:
    """Scan and aggregate projects for one or more learn plugins."""

    project_summaries: list[dict[str, Any]] = []
    totals = Counter()

    for agent_name, plugin, projects in agent_projects:
        for project in projects:
            sessions = plugin.scan_project(project, max_workers=max_workers)
            summary = aggregate_project_sessions(project, sessions, agent=agent_name)
            project_summaries.append(summary)
            totals["projects"] += 1
            totals["sessions"] += summary["session_count"]
            totals["calls"] += summary["total_calls"]
            totals["failures"] += summary["total_failures"]

    return {
        "schema_version": "learn_aggregate_v1",
        "local_only": True,
        "sharing_implemented": False,
        "project_count": totals["projects"],
        "session_count": totals["sessions"],
        "total_calls": totals["calls"],
        "total_failures": totals["failures"],
        "failure_rate": (
            totals["failures"] / totals["calls"] if totals["calls"] else 0.0
        ),
        "projects": project_summaries,
    }


def dumps_aggregate(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def share_aggregate(_payload: dict[str, Any]) -> None:
    """Future egress hook.

    This is deliberately not implemented until product/security approve a
    concrete destination, consent UX, and data contract.
    """

    raise NotImplementedError("Learn telemetry sharing is not implemented")
