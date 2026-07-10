from __future__ import annotations

from scripts.run_staging_dashboard_smoke import (
    StagingDashboardNotConfigured,
    _redacted_location,
    staging_dashboard_config_from_env,
)


def test_staging_dashboard_requires_url_and_admin_key(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_STAGED_DASHBOARD_URL", raising=False)
    monkeypatch.delenv("CUTCTX_STAGED_PROXY_ADMIN_API_KEY", raising=False)

    try:
        staging_dashboard_config_from_env()
    except StagingDashboardNotConfigured as exc:
        assert "CUTCTX_STAGED_DASHBOARD_URL" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing staging configuration failure")


def test_staging_dashboard_artifact_location_omits_query_and_credentials() -> None:
    assert _redacted_location("https://user:secret@staging.example/dashboard?key=secret") == (
        "https://staging.example/dashboard"
    )
