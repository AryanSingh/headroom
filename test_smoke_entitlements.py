"""Quick smoke test for entitlement changes."""
from cutctx.entitlements import EntitlementChecker, EntitlementError

c = EntitlementChecker("builder")
assert not c.is_entitled("ccr"), "Builder should not be entitled to CCR"
assert not c.is_entitled("totally_fake_xyz"), "Unknown features should be denied (fail-closed)"
assert c.is_entitled("smart_crusher"), "Builder should be entitled to core features"

try:
    c.require_entitled("sso_saml")
    assert False, "Should have raised"
except EntitlementError as e:
    msg = str(e)
    assert "Enterprise" in msg, f"Expected 'Enterprise' in error, got: {msg}"
    assert "Free" in msg, f"Expected 'Free' in error, got: {msg}"
    assert "Upgrade" in msg, f"Expected 'Upgrade' in error, got: {msg}"

print("All entitlement smoke tests passed!")
