"""Deterministic quality benchmark for the low-complexity model router.

The benchmark measures the decision boundary independently of provider
availability.  Positive cases are safe candidates for the mini/high route;
negative cases require the requested stronger model.  CI can use ``--ci`` to
fail on unsafe downgrades or on regressions below the pinned balanced-accuracy
floor.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cutctx.proxy.model_router import TaskComplexity, assess_task_complexity


@dataclass
class RoutingCase:
    id: str
    prompt: str
    expect_mini: bool
    category: str
    expect_luna: bool = False
    messages: list[dict[str, str]] | None = None
    client: str = "generic"


CASES = [
    RoutingCase("greeting", "Hello", True, "conversation"),
    RoutingCase("definition", "What is idempotency?", True, "informational"),
    RoutingCase("location", "Where is the proxy config?", True, "repository_lookup"),
    RoutingCase("simple_list", "List the supported providers.", True, "informational"),
    RoutingCase("short_explain", "Explain exponential backoff.", True, "informational"),
    RoutingCase("rename", "Rename this variable.", True, "small_edit"),
    RoutingCase("typo", "Fix the typo in this heading.", True, "small_edit"),
    RoutingCase("docstring", "Add a docstring to this helper.", True, "small_edit"),
    RoutingCase("type_hint", "Add type hints to this function.", True, "small_edit"),
    RoutingCase("format", "Format this code.", True, "small_edit"),
    RoutingCase("architecture", "Design a multi-region failover architecture.", False, "design"),
    RoutingCase(
        "security_review", "Audit the authentication flow for vulnerabilities.", False, "security"
    ),
    RoutingCase(
        "debug", "Debug why the websocket reconnect loop drops events.", False, "debugging"
    ),
    RoutingCase(
        "implementation", "Implement durable workflow cancellation.", False, "implementation"
    ),
    RoutingCase("migration", "Plan and execute the database migration.", False, "migration"),
    RoutingCase(
        "benchmark",
        "Run the full benchmark suite and optimize the weakest path.",
        False,
        "evaluation",
    ),
    RoutingCase("release", "Prepare, commit, push, and release all files.", False, "release"),
    RoutingCase("production", "Fix the production billing failure.", False, "production"),
    RoutingCase(
        "code_block", "Explain this:\n```python\nraise RuntimeError('x')\n```", False, "code"
    ),
    RoutingCase("patch", "Apply this patch:\n*** Begin Patch\n*** End Patch", False, "code"),
    RoutingCase("stack", "Investigate this stack trace and propose a fix.", False, "debugging"),
    RoutingCase(
        "large_scope", "Update all modules and services for the new API.", False, "implementation"
    ),
    RoutingCase(
        "tool_context", "Use the deployment tool to publish the release.", False, "tool_use"
    ),
    RoutingCase("ambiguous_fix", "Fix it.", False, "ambiguous"),
    RoutingCase(
        "followup_explanation",
        "Explain the first module.",
        False,
        "contextual",
        expect_luna=True,
        messages=[
            {"role": "user", "content": "Inspect the service."},
            {"role": "assistant", "content": "I found two relevant modules."},
            {"role": "user", "content": "Explain the first module."},
        ],
    ),
    RoutingCase(
        "followup_summary",
        "Summarize that in bullets.",
        False,
        "contextual",
        expect_luna=True,
        messages=[
            {"role": "user", "content": "Describe the deployment history."},
            {"role": "assistant", "content": "The deployment has four phases."},
            {"role": "user", "content": "Summarize that in bullets."},
        ],
    ),
    RoutingCase(
        "moderate_transformation",
        "Rewrite the following customer update in a concise and neutral tone while preserving the stated dates and owners.",
        False,
        "transformation",
        expect_luna=True,
    ),
    RoutingCase(
        "reference_without_history",
        "Explain the first module.",
        False,
        "reference_dependent",
        expect_luna=True,
    ),
]


def load_versioned_cases() -> list[RoutingCase]:
    path = Path(__file__).parent / "fixtures" / "model_routing_quality_v2.json"
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != 2:
        raise ValueError("Unsupported model-routing quality corpus version")
    return [
        RoutingCase(
            id=str(item["id"]),
            prompt=str(item["prompt"]),
            expect_mini=item["expected_tier"] == "mini",
            expect_luna=item["expected_tier"] == "luna",
            category=str(item["category"]),
            messages=item.get("messages"),
            client=str(item["client"]),
        )
        for item in payload["cases"]
    ]


def evaluate() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    tp = tn = fp = fn = 0
    tier_correct = 0
    luna_total = 0
    luna_correct = 0
    all_cases = [*CASES, *load_versioned_cases()]
    for case in all_cases:
        messages = case.messages or [{"role": "user", "content": case.prompt}]
        assessment = assess_task_complexity(messages)
        complexity = assessment.complexity
        predicted_mini = complexity == TaskComplexity.LOW
        predicted_tier = {
            TaskComplexity.LOW: "mini",
            TaskComplexity.MEDIUM: "luna",
            TaskComplexity.HIGH: "strong",
        }[complexity]
        expected_tier = "luna" if case.expect_luna else "mini" if case.expect_mini else "strong"
        tier_correct += predicted_tier == expected_tier
        if case.expect_luna:
            luna_total += 1
            luna_correct += predicted_tier == "luna"
        if case.expect_mini and predicted_mini:
            tp += 1
        elif case.expect_mini:
            fn += 1
        elif predicted_mini:
            fp += 1
        else:
            tn += 1
        rows.append(
            {
                **asdict(case),
                "predicted_mini": predicted_mini,
                "expected_tier": expected_tier,
                "predicted_tier": predicted_tier,
                "complexity": complexity.name.lower(),
                "confidence": assessment.confidence,
                "scorer": assessment.source,
                "correct": predicted_tier == expected_tier,
            }
        )

    positive_recall = tp / max(tp + fn, 1)
    strong_model_recall = tn / max(tn + fp, 1)
    per_client: dict[str, dict[str, float | int]] = {}
    per_category: dict[str, dict[str, float | int]] = {}
    for dimension, target in (("client", per_client), ("category", per_category)):
        values = sorted({str(row[dimension]) for row in rows})
        for value in values:
            selected = [row for row in rows if row[dimension] == value]
            unsafe = sum(
                row["predicted_tier"] == "mini" and row["expected_tier"] != "mini"
                for row in selected
            )
            target[value] = {
                "cases": len(selected),
                "tier_accuracy": sum(bool(row["correct"]) for row in selected) / len(selected),
                "unsafe_downgrades": unsafe,
                "unsafe_downgrade_rate": unsafe / len(selected),
            }
    return {
        "schema_version": 2,
        "corpus_version": 2,
        "cases": len(all_cases),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "metrics": {
            "accuracy": (tp + tn) / len(all_cases),
            "balanced_accuracy": (positive_recall + strong_model_recall) / 2,
            "mini_candidate_recall": positive_recall,
            "strong_model_recall": strong_model_recall,
            "luna_candidate_recall": luna_correct / max(luna_total, 1),
            "tier_accuracy": tier_correct / len(all_cases),
            "unsafe_downgrade_rate": fp / max(tn + fp, 1),
            "mean_confidence": sum(float(row["confidence"]) for row in rows) / len(rows),
        },
        "per_client": per_client,
        "per_category": per_category,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)
    metrics = result["metrics"]
    assert isinstance(metrics, dict)
    if args.ci and (
        float(metrics["unsafe_downgrade_rate"]) > 0.0
        or float(metrics["balanced_accuracy"]) < 0.95
        or float(metrics["tier_accuracy"]) < 0.95
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
