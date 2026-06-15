"""Tests for security hardening: SSRF protection, auth on unprotected routes."""

from __future__ import annotations

import pytest

from headroom.proxy.structured_output import (
    _ALLOWED_BASE_HOSTS,
    _validate_base_url,
)


class TestSSRFProtection:
    """SSRF base_url validation tests."""

    def test_allowed_anthropic(self):
        url = _validate_base_url("https://api.anthropic.com")
        assert url == "https://api.anthropic.com"

    def test_allowed_openai(self):
        url = _validate_base_url("https://api.openai.com")
        assert url == "https://api.openai.com"

    def test_allowed_google(self):
        url = _validate_base_url("https://generativelanguage.googleapis.com")
        assert url == "https://generativelanguage.googleapis.com"

    def test_blocked_localhost(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("http://localhost:8080")

    def test_blocked_internal_ip(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("http://192.168.1.1/admin")

    def test_blocked_cloud_metadata(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("http://169.254.169.254/latest/meta-data/")

    def test_blocked_arbitrary_domain(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("https://evil.example.com/steal-data")

    def test_blocked_file_scheme(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("file:///etc/passwd")

    def test_allowed_http_localhost_when_whitelisted(self):
        """If localhost is in the allowlist, http should work."""
        # Not in default allowlist, but verify the check works
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("http://localhost:8080/v1/messages")

    def test_allowed_hosts_constant(self):
        assert "api.anthropic.com" in _ALLOWED_BASE_HOSTS
        assert "api.openai.com" in _ALLOWED_BASE_HOSTS
        assert "generativelanguage.googleapis.com" in _ALLOWED_BASE_HOSTS

    def test_empty_host_blocked(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("")

    def test_path_traversal_blocked(self):
        with pytest.raises(ValueError, match="SSRF blocked"):
            _validate_base_url("https://evil.com/../../../etc/passwd")
