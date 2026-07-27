"""Thin compression integrity evals: skill survival + attribution invariants."""

from __future__ import annotations

from typing import Any, Callable

from cutctx.cli.report import build_buyer_report_payload

CompressFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]

_RULE_PREFIX = "SKILL_SURVIVAL_RULE_"


def _fixture_messages(rule_count: int = 20) -> tuple[list[dict[str, Any]], list[str]]:
    rules = [f"{_RULE_PREFIX}{i:02d}: keep this instruction intact." for i in range(rule_count)]
    body = "---\nname: survival-fixture\ndescription: eval skill\n---\n" + "\n".join(rules)
    messages = [
        {"role": "system", "content": "Follow installed skills."},
        {"role": "user", "content": body},
        {"role": "user", "content": "Summarize the build log:\n" + ("ERROR boom\n" * 50)},
    ]
    return messages, rules


def evaluate_skill_survival(
    compress_fn: CompressFn,
    *,
    min_retention: float = 0.95,
    rule_count: int = 20,
) -> dict[str, Any]:
    """Assert skill/instruction rule strings survive a compression pass.

    ``passed`` requires retention >= ``min_retention`` (default 95%).
    """
    messages, rules = _fixture_messages(rule_count)
    out = compress_fn(messages)
    joined = "\n".join(
        m.get("content", "")
        for m in out
        if isinstance(m, dict) and isinstance(m.get("content"), str)
    )
    retained = sum(1 for rule in rules if rule in joined)
    total = len(rules)
    ratio = (retained / total) if total else 1.0
    return {
        "passed": ratio >= min_retention,
        "retained_rules": retained,
        "total_rules": total,
        "retention_ratio": ratio,
        "min_retention": min_retention,
    }


def check_attribution_invariant(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Created (Cutctx) and observed (provider cache) tokens must not be conflated."""
    payload = build_buyer_report_payload(rows)
    created = int(payload["created_savings_tokens"])
    observed = int(payload["observed_provider_cache_tokens"])
    # Invariant: sources are additive and independently tracked — neither field
    # should silently absorb the other.
    double_counted = created == observed and created > 0 and len(rows) > 1
    return {
        "passed": not double_counted,
        "created_savings_tokens": created,
        "observed_provider_cache_tokens": observed,
        "caveat": payload["caveat"],
    }
