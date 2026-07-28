"""Thin skill-survival eval harness."""

from __future__ import annotations

from cutctx.evals.skill_survival import evaluate_skill_survival


def _identity_compress(messages):
    return messages


def test_skill_survival_eval_passes_on_identity() -> None:
    result = evaluate_skill_survival(_identity_compress)
    assert result["passed"] is True
    assert result["retained_rules"] == result["total_rules"]


def test_skill_survival_eval_fails_when_rules_stripped() -> None:
    def _strip(messages):
        return [{"role": m.get("role"), "content": "gone"} for m in messages]

    result = evaluate_skill_survival(_strip)
    assert result["passed"] is False
    assert result["retained_rules"] < result["total_rules"]


def test_attribution_invariant_created_vs_observed() -> None:
    from cutctx.evals.skill_survival import check_attribution_invariant

    rows = [
        {"savings_by_source_tokens": {"cutctx_compression": 10, "provider_prompt_cache": 5}},
        {"savings_by_source_tokens": {"cutctx_compression": 0, "provider_prompt_cache": 7}},
    ]
    result = check_attribution_invariant(rows)
    assert result["passed"] is True
    assert result["created_savings_tokens"] == 10
    assert result["observed_provider_cache_tokens"] == 12
