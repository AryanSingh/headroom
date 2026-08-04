from __future__ import annotations

import httpx
from click.testing import CliRunner

from cutctx.cli.audit import audit
from cutctx.cli.rbac import rbac


def _denied(feature: str, required_tier: str = "enterprise") -> httpx.Response:
    return httpx.Response(
        403,
        request=httpx.Request("GET", "http://127.0.0.1:8787/test"),
        json={
            "detail": {
                "error": "feature_not_available",
                "feature": feature,
                "required_tier": required_tier,
                "current_tier": "builder",
            }
        },
    )


def test_rbac_cli_preserves_typed_entitlement_denial(monkeypatch) -> None:
    monkeypatch.setattr("cutctx.cli.rbac.httpx.get", lambda *args, **kwargs: _denied("rbac"))

    result = CliRunner().invoke(rbac, ["list"])

    assert result.exit_code == 1
    assert "RBAC requires the Enterprise tier" in result.output
    assert "current tier: Builder" in result.output


def test_audit_cli_preserves_typed_entitlement_denial(monkeypatch) -> None:
    monkeypatch.setattr(
        "cutctx.cli.audit.httpx.get",
        lambda *args, **kwargs: _denied("audit_logs"),
    )

    result = CliRunner().invoke(audit, ["list"])

    assert result.exit_code == 1
    assert "Audit logs requires the Enterprise tier" in result.output
    assert "current tier: Builder" in result.output
