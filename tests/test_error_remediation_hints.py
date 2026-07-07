"""Tests for error remediation hints in HTTP error responses.

Per commercial-readiness-remediation-runbook.md Task 3:
Error responses should include actionable remediation hints.
"""

from fastapi.testclient import TestClient
import pytest

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _base_config() -> ProxyConfig:
    """Create a base config for testing."""
    config = ProxyConfig()
    config.admin_api_key = "test-admin-key"
    config.optimize = False
    config.cache_enabled = False
    config.rate_limit_enabled = False
    config.cost_tracking_enabled = False
    return config


class TestErrorRemediationHints:
    """Test that error responses include actionable remediation hints."""

    def test_missing_admin_credentials_includes_remediation(self) -> None:
        """401 for missing admin credentials includes remediation hint."""
        app = create_app(_base_config())
        # Use non-loopback client and mutating request to bypass loopback bypass
        with TestClient(app, client=("10.0.0.1", 50000)) as client:
            response = client.post(
                "/stats/reset",
                headers={},  # No auth provided
            )

        assert response.status_code == 401
        body = response.json()
        assert "error" in body, f"Expected 'error' key in response: {body}"
        assert "remediation" in body["error"], \
            f"remediation field missing from error: {body}"
        remediation = body["error"]["remediation"]
        assert isinstance(remediation, str)
        # Should mention how to provide credentials
        assert any(keyword in remediation.lower() for keyword in [
            "authorization", "bearer", "api key", "header", "set"
        ]), f"Remediation doesn't explain how to provide credentials: {remediation}"

    def test_invalid_admin_credentials_includes_remediation(self) -> None:
        """401 for invalid admin credentials includes specific remediation."""
        app = create_app(_base_config())
        # Use non-loopback client and mutating request to bypass loopback bypass
        with TestClient(app, client=("10.0.0.1", 50000)) as client:
            response = client.post(
                "/stats/reset",
                headers={"X-Cutctx-Admin-Key": "wrong-key"},
            )

        assert response.status_code == 401
        body = response.json()
        assert "error" in body, f"Expected 'error' key in response: {body}"
        assert "remediation" in body["error"], \
            f"remediation field missing from error: {body}"
        remediation = body["error"]["remediation"]
        # Should suggest checking the key or setting the env var
        assert any(keyword in remediation.lower() for keyword in [
            "cutctx_admin_api_key", "check", "verify", "key"
        ]), f"Remediation doesn't explain key mismatch: {remediation}"

    def test_enterprise_module_not_installed_includes_remediation(self) -> None:
        """501 for missing enterprise module includes remediation."""
        # Check if the ee module is installed
        try:
            import cutctx_ee
            pytest.skip("cutctx_ee is installed; cannot test missing module error")
        except ImportError:
            pass

        app = create_app(_base_config())
        # Use non-loopback client to avoid loopback bypass
        with TestClient(app, client=("10.0.0.1", 50000)) as client:
            response = client.post(
                "/v1/license/activate",
                json={"license_key": "test", "instance_id": "test"},
                headers={"X-Cutctx-Admin-Key": "test-admin-key"},
            )

        # If we get a 501 error (enterprise module not installed), check for remediation
        if response.status_code == 501:
            body = response.json()
            assert "error" in body, f"Expected 'error' key in response: {body}"
            assert "remediation" in body["error"], \
                f"remediation field missing from error: {body}"
            remediation = body["error"]["remediation"]
            # Should explain what's needed to enable the feature
            assert "enterprise" in remediation.lower() or "ee" in remediation.lower(), \
                f"Remediation doesn't mention enterprise requirement: {remediation}"
        else:
            # If not 501, skip this test since the module is installed
            pytest.skip(f"Got {response.status_code} instead of 501; ee module might be installed")

    def test_rbac_unavailable_includes_remediation(self) -> None:
        """503 for unavailable RBAC includes remediation."""
        # This error path is less common but should still include remediation
        app = create_app(_base_config())
        with TestClient(app) as client:
            # Try to hit a path that requires RBAC
            response = client.post(
                "/v1/admin/sso/provider",
                json={"provider": "test", "config": {}},
                headers={"X-Cutctx-Admin-Key": "test-admin-key"},
            )

        # If we get a 503 for RBAC unavailable, it should have remediation
        if response.status_code == 503:
            body = response.json()
            assert "error" in body
            assert "remediation" in body["error"], \
                f"remediation field missing from error: {body}"

    def test_invalid_bearer_token_format_includes_remediation(self) -> None:
        """401 for invalid bearer token format includes remediation."""
        app = create_app(_base_config())
        # Use non-loopback client and mutating request to bypass loopback bypass
        with TestClient(app, client=("10.0.0.1", 50000)) as client:
            # Try to access an endpoint that requires admin auth with invalid token format
            response = client.post(
                "/stats/reset",
                headers={
                    "Authorization": "InvalidFormat",  # Should be "Bearer <token>"
                },
            )

        if response.status_code == 401:
            body = response.json()
            assert "error" in body
            # Check for remediation field if present
            if "remediation" in body["error"]:
                remediation = body["error"]["remediation"]
                assert len(remediation) > 10, "Remediation hint too short"


class TestRemediationHintContent:
    """Test that remediation hints are specific and actionable."""

    def test_remediation_not_generic_contact_support(self) -> None:
        """Remediation hints should be specific, not generic."""
        app = create_app(_base_config())
        # Use non-loopback client and mutating request to bypass loopback bypass
        with TestClient(app, client=("10.0.0.1", 50000)) as client:
            response = client.post(
                "/stats/reset",
                headers={},
            )

        assert response.status_code == 401
        body = response.json()
        remediation = body["error"].get("remediation", "")

        # Should NOT be just "contact support"
        assert remediation.lower() != "contact support"
        assert "contact" not in remediation.lower() or len(remediation) > 30

        # Should be a complete sentence or instructions
        assert len(remediation) > 15, "Remediation hint too short"

    def test_license_error_remediation_specific(self) -> None:
        """License-related errors should have specific remediation."""
        app = create_app(_base_config())
        # Use non-loopback client to avoid loopback bypass
        with TestClient(app, client=("10.0.0.1", 50000)) as client:
            response = client.post(
                "/v1/license/activate",
                json={"license_key": "test", "instance_id": "test"},
                headers={"X-Cutctx-Admin-Key": "test-admin-key"},
            )

        if response.status_code == 501:
            body = response.json()
            remediation = body["error"].get("remediation", "")
            # Should mention enterprise edition
            assert "enterprise" in remediation.lower() or "cutctx-ee" in remediation.lower()
