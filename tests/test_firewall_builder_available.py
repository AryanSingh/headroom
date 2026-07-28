"""Builder path: local firewall scan works without an EE license."""

from __future__ import annotations


def test_firewall_scan_available_without_license() -> None:
    from cutctx.security.firewall import FirewallConfig, FirewallScanner

    # Local regex firewall is usable offline without EE; enable explicitly
    # (default is off via env — Builder flips CUTCTX_FIREWALL_ENABLED=1).
    findings = FirewallScanner(FirewallConfig(enabled=True)).scan_text("SSN 111-22-3333")
    assert findings
