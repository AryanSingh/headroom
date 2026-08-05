"""Deterministic offline Product Atlas SDK compatibility evidence."""

from __future__ import annotations


SUPPORTED_REQUEST_FIELDS = {"tenant_id", "account_id", "include_usage"}
REQUIRED_RESPONSE_FIELDS = {"account_id", "plan", "usage"}


def validate_request(request: dict[str, object]) -> None:
    unknown = set(request) - SUPPORTED_REQUEST_FIELDS
    if unknown:
        raise ValueError(f"unsupported request fields: {sorted(unknown)}")
    if request.get("tenant_id") != "atlas-a":
        raise PermissionError("tenant binding rejected")
    if not isinstance(request.get("account_id"), str):
        raise ValueError("account_id is required")


def decode_v1_response(response: dict[str, object]) -> dict[str, object]:
    missing = REQUIRED_RESPONSE_FIELDS - set(response)
    if missing:
        raise ValueError(f"missing compatible response fields: {sorted(missing)}")
    return {field: response[field] for field in sorted(REQUIRED_RESPONSE_FIELDS)}


def main() -> None:
    request = {"tenant_id": "atlas-a", "account_id": "acct-100", "include_usage": True}
    validate_request(request)
    decoded = decode_v1_response(
        {"account_id": "acct-100", "plan": "pro", "usage": 42, "new_field": "ignored"}
    )
    assert decoded == {"account_id": "acct-100", "plan": "pro", "usage": 42}

    try:
        validate_request({"tenant_id": "atlas-b", "account_id": "acct-100"})
    except PermissionError as error:
        assert str(error) == "tenant binding rejected"
    else:
        raise AssertionError("cross-tenant request was accepted")

    try:
        decode_v1_response({"account_id": "acct-100", "usage": 42})
    except ValueError as error:
        assert "plan" in str(error)
    else:
        raise AssertionError("removed required field was accepted")

    print("SDK_COMPATIBILITY_FIXTURE_PASS additive-safe tenant-bound breaking-change-blocked")


if __name__ == "__main__":
    main()
