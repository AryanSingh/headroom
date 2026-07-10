"""Tests for the deterministic verbatim compactor."""

from __future__ import annotations

from cutctx.transforms.verbatim_compactor import VerbatimCompactor


def test_verbatim_compactor_preserves_exact_critical_lines() -> None:
    compactor = VerbatimCompactor()

    text = """INFO start request_id=req_9f2c
DEBUG cache hit bucket=config
DEBUG cache hit bucket=templates
DEBUG cache hit bucket=manifests
DEBUG cache hit bucket=policies
Traceback (most recent call last):
  File \"services/payments/vault.py\", line 77, in issue_token
    raise PermissionDeniedError(\"vault token expired\")
PermissionDeniedError: vault token expired
INFO rollback finished
"""

    result = compactor.compress(
        text,
        context="Which file raised `PermissionDeniedError` for request_id=req_9f2c?",
        critical_items=[
            "services/payments/vault.py",
            "line 77",
            "PermissionDeniedError: vault token expired",
            "request_id=req_9f2c",
        ],
    )

    assert "services/payments/vault.py" in result.compressed
    assert "PermissionDeniedError: vault token expired" in result.compressed
    assert "request_id=req_9f2c" in result.compressed
    assert result.omitted_lines > 0


def test_verbatim_compactor_infers_needles_from_query_context() -> None:
    compactor = VerbatimCompactor()

    text = """INFO replay started
DEBUG loading cached fragments
DEBUG re-ranking fragment window
DEBUG replay cache size=42
DEBUG replay rank window=8
failure.path=dist/config/release-rc1.json
failure.owner=payments-platform
INFO replay finished
"""

    result = compactor.compress(
        text,
        context="Preserve `dist/config/release-rc1.json` and payments-platform exactly.",
    )

    assert "dist/config/release-rc1.json" in result.compressed
    assert "payments-platform" in result.compressed
    assert result.omitted_lines > 0


def test_verbatim_compactor_passthrough_for_short_inputs() -> None:
    compactor = VerbatimCompactor()
    text = "alpha\nbeta\ngamma\n"

    result = compactor.compress(text, context="Keep beta")

    assert result.compressed == text
    assert result.kept_lines == 3
    assert result.omitted_lines == 0
