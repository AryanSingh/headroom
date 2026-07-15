"""Zero-provider downstream task evaluation for compression safety.

Unlike lexical retention metrics, these probes execute deterministic consumer
tasks against original and compressed contexts and compare the task outcomes to
ground truth. They are deliberately small and offline; provider-backed SQuAD,
BFCL, HotpotQA, and lm-eval suites remain the stronger release gates.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cutctx.transforms.content_router import ContentRouter


@dataclass(frozen=True)
class OfflineTask:
    id: str
    query: str
    context: str
    expected: Any
    solve: Callable[[str], Any]


def _sum_durations(text: str) -> int:
    return sum(int(value) for value in re.findall(r'"duration_minutes"\s*:\s*(\d+)', text))


def _deployment_target(text: str) -> str:
    matches = re.findall(r"target_region\s*[=:]\s*([a-z0-9-]+)", text, flags=re.IGNORECASE)
    return matches[-1].lower() if matches else ""


def _added_timeout(text: str) -> int:
    match = re.search(r"^\+\s*timeout_seconds\s*=\s*(\d+)", text, flags=re.MULTILINE)
    return int(match.group(1)) if match else -1


def _failed_tool_ids(text: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            re.findall(
                r'"id"\s*:\s*"([^"]+)"\s*,\s*"status"\s*:\s*"failed"',
                text,
                flags=re.IGNORECASE,
            )
        )
    )


def _cases() -> list[OfflineTask]:
    noise = "\n".join(f"INFO healthcheck shard={i} status=ok" for i in range(80))
    return [
        OfflineTask(
            id="incident_duration_total",
            query="What is the total incident duration_minutes across all incidents?",
            context=(
                '{"incidents": ['
                '{"service": "api", "duration_minutes": 12}, '
                '{"service": "worker", "duration_minutes": 8}, '
                '{"service": "billing", "duration_minutes": 5}'
                f'], "diagnostic_log": {json.dumps(noise)}}}'
            ),
            expected=25,
            solve=_sum_durations,
        ),
        OfflineTask(
            id="deployment_target",
            query="What target_region was approved for deployment?",
            context=f"{noise}\nDEPLOY approved target_region=ap-south-1 owner=release\n{noise}",
            expected="ap-south-1",
            solve=_deployment_target,
        ),
        OfflineTask(
            id="configuration_diff",
            query="What timeout_seconds value was added in this diff?",
            context=(
                "diff --git a/service.conf b/service.conf\n"
                "--- a/service.conf\n+++ b/service.conf\n"
                "@@ -1,3 +1,3 @@\n"
                "-timeout_seconds = 30\n+timeout_seconds = 45\n"
                + "\n".join(f" context_key_{i} = unchanged" for i in range(80))
            ),
            expected=45,
            solve=_added_timeout,
        ),
        OfflineTask(
            id="failed_tool_calls",
            query="Which tool call ids have status failed?",
            context=(
                '[{"id":"call-a","status":"ok"},'
                '{"id":"call-b","status":"failed"},'
                '{"id":"call-c","status":"failed"},'
                '{"id":"call-d","status":"ok"}]\n' + noise
            ),
            expected=("call-b", "call-c"),
            solve=_failed_tool_ids,
        ),
    ]


def run_offline_downstream_evaluation(
    *, router: ContentRouter | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """Run deterministic task consumers before and after compression."""
    active_router = router or ContentRouter()
    outcomes: list[dict[str, Any]] = []
    total_original = 0
    total_compressed = 0
    for case in _cases():
        compressed = active_router.compress(case.context, context=case.query).compressed
        original_tokens = max(1, len(case.context) // 4)
        compressed_tokens = max(1, len(compressed) // 4)
        baseline_answer = case.solve(case.context)
        cutctx_answer = case.solve(compressed)
        outcomes.append(
            {
                "id": case.id,
                "expected": case.expected,
                "baseline_answer": baseline_answer,
                "cutctx_answer": cutctx_answer,
                "baseline_correct": baseline_answer == case.expected,
                "cutctx_correct": cutctx_answer == case.expected,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
            }
        )
        total_original += original_tokens
        total_compressed += compressed_tokens

    count = len(outcomes)
    baseline_score = sum(row["baseline_correct"] for row in outcomes) / count
    cutctx_score = sum(row["cutctx_correct"] for row in outcomes) / count
    compression_ratio = total_compressed / total_original if total_original else 1.0
    return {
        "version": "1.0",
        "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
        "model": "deterministic-offline-consumers",
        "summary": {
            "total_benchmarks": 1,
            "passed": int(cutctx_score == 1.0),
            "failed": int(cutctx_score != 1.0),
            "all_passed": cutctx_score == 1.0,
            "total_tokens_saved": total_original - total_compressed,
        },
        "benchmarks": [
            {
                "name": "Offline Downstream Task Consumers",
                "category": "task_outcome",
                "tier": 1,
                "n_samples": count,
                "model": "deterministic-offline-consumers",
                "metric": "accuracy",
                "baseline_score": baseline_score,
                "cutctx_score": cutctx_score,
                "delta": cutctx_score - baseline_score,
                "passed": baseline_score == 1.0 and cutctx_score == 1.0,
                "avg_compression_ratio": compression_ratio,
                "tokens_saved": total_original - total_compressed,
            }
        ],
        "task_outcomes": outcomes,
        "limitations": [
            "Deterministic offline probes cover structured consumer tasks, not open-ended model reasoning.",
            "Provider-backed SQuAD, BFCL, HotpotQA, and lm-eval runs remain required for release-grade model quality claims.",
        ],
    }


def write_offline_downstream_evaluation(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
