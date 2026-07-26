# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from __future__ import annotations

from cutctx_ee import billing


def test_ee_checkout_is_a_cutctx_pricing_deep_link(monkeypatch):
    monkeypatch.setattr(billing, "CUTCTX_SITE_URL", "https://billing.example")
    monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

    assert billing.get_checkout_url("studio", "buyer@example.com", "annual") == (
        "https://billing.example/pricing/?product=cutctx&plan=studio"
        "&billing=annual&email=buyer%40example.com"
    )


def test_ee_portal_is_the_cutctx_license_portal(monkeypatch):
    monkeypatch.setattr(billing, "CUTCTX_SITE_URL", "https://billing.example")
    monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

    assert billing.get_portal_url("buyer@example.com") == (
        "https://billing.example/licenses/?email=buyer%40example.com"
    )
