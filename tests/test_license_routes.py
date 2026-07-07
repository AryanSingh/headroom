"""Tests for FastAPI license management endpoints in license.py."""
import pytest
from fastapi import HTTPException
from pydantic import BaseModel


# Manually define the request class for testing
class CheckoutSeatRequest(BaseModel):
    license_key: str
    user_id: str
    lease_duration: float = 3600.0


async def test_checkout_seat_fails_when_no_seats_available(monkeypatch):
    """Test that checkout-seat rejects requests when no seats are available."""

    # Mock the license_db to simulate "no seats available" condition
    class MockLicenseDB:
        def is_revoked(self, license_key: str) -> bool:
            return False

        def checkout_seat(self, license_key: str, user_id: str, lease_duration: float) -> bool:
            # Simulate the scenario where checkout fails because no seats available
            return False

    def mock_get_license_db():
        return MockLicenseDB()

    # Patch the import in the license module at its source
    monkeypatch.setattr(
        "cutctx_ee.billing.license_db.get_license_db",
        mock_get_license_db
    )

    # Import and call the endpoint function directly
    from cutctx.proxy.routes.license import create_license_router

    router = create_license_router()

    # Get the endpoint function from the router
    checkout_seat_func = None
    for route in router.routes:
        if hasattr(route, 'path') and '/checkout-seat' in route.path:
            # Get the endpoint function
            checkout_seat_func = route.endpoint
            break

    assert checkout_seat_func is not None, "checkout_seat endpoint not found"

    # Create a test request
    req = CheckoutSeatRequest(
        license_key="test-license-key",
        user_id="test-user",
        lease_duration=3600.0
    )

    # Call the endpoint function directly
    with pytest.raises(HTTPException) as exc_info:
        await checkout_seat_func(req)

    # Should raise HTTPException with 409 status when no seats available
    assert exc_info.value.status_code == 409, f"Expected 409, got {exc_info.value.status_code}"
    detail = exc_info.value.detail
    message = detail["message"] if isinstance(detail, dict) else detail
    assert "No seats available" in message


async def test_checkout_seat_succeeds_when_seats_available(monkeypatch):
    """Test that checkout-seat succeeds when seats are available."""

    # Mock the license_db to simulate successful checkout
    class MockLicenseDB:
        def is_revoked(self, license_key: str) -> bool:
            return False

        def checkout_seat(self, license_key: str, user_id: str, lease_duration: float) -> bool:
            # Simulate successful checkout
            return True

    def mock_get_license_db():
        return MockLicenseDB()

    # Patch the import in the license module at its source
    monkeypatch.setattr(
        "cutctx_ee.billing.license_db.get_license_db",
        mock_get_license_db
    )

    # Import and call the endpoint function directly
    from cutctx.proxy.routes.license import create_license_router

    router = create_license_router()

    # Get the endpoint function from the router
    checkout_seat_func = None
    for route in router.routes:
        if hasattr(route, 'path') and '/checkout-seat' in route.path:
            checkout_seat_func = route.endpoint
            break

    assert checkout_seat_func is not None, "checkout_seat endpoint not found"

    # Create a test request
    req = CheckoutSeatRequest(
        license_key="test-license-key",
        user_id="test-user",
        lease_duration=3600.0
    )

    # Call the endpoint function - should succeed and return 200 with "seat_leased"
    result = await checkout_seat_func(req)
    assert result == {"status": "seat_leased"}


async def test_checkout_seat_rejected_when_license_revoked(monkeypatch):
    """Test that checkout-seat is rejected when license is revoked."""

    class MockLicenseDB:
        def is_revoked(self, license_key: str) -> bool:
            return True

        def checkout_seat(self, license_key: str, user_id: str, lease_duration: float) -> bool:
            # Should not be called if revoked
            raise AssertionError("checkout_seat should not be called for revoked license")

    def mock_get_license_db():
        return MockLicenseDB()

    monkeypatch.setattr(
        "cutctx_ee.billing.license_db.get_license_db",
        mock_get_license_db
    )

    # Import and call the endpoint function directly
    from cutctx.proxy.routes.license import create_license_router

    router = create_license_router()

    # Get the endpoint function from the router
    checkout_seat_func = None
    for route in router.routes:
        if hasattr(route, 'path') and '/checkout-seat' in route.path:
            checkout_seat_func = route.endpoint
            break

    assert checkout_seat_func is not None, "checkout_seat endpoint not found"

    # Create a test request
    req = CheckoutSeatRequest(
        license_key="revoked-license",
        user_id="test-user",
        lease_duration=3600.0
    )

    # Call the endpoint - should raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await checkout_seat_func(req)

    assert exc_info.value.status_code == 403
    detail = exc_info.value.detail
    message = detail["message"] if isinstance(detail, dict) else detail
    assert message == "License revoked"
