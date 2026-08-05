from __future__ import annotations

import sys
import threading
import time
from types import SimpleNamespace

import pytest

from cutctx.auth.operator_credentials import (
    CUTCTX_LICENSE_ACCOUNT,
    SERVICE_NAME,
    read_operator_credential,
)


def test_reads_shared_desktop_license_account(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def get_password(service: str, account: str) -> str | None:
        calls.append((service, account))
        return "cutctx-test-license"

    monkeypatch.setitem(
        sys.modules,
        "keyring",
        SimpleNamespace(get_password=get_password),
    )

    assert read_operator_credential(CUTCTX_LICENSE_ACCOUNT) == "cutctx-test-license"
    assert calls == [(SERVICE_NAME, CUTCTX_LICENSE_ACCOUNT)]


def test_keyring_hang_fails_closed_before_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    monkeypatch.setitem(
        sys.modules,
        "keyring",
        SimpleNamespace(get_password=lambda *_args: release.wait()),
    )
    started = time.monotonic()
    try:
        assert (
            read_operator_credential(
                CUTCTX_LICENSE_ACCOUNT,
                timeout_seconds=0.05,
            )
            is None
        )
        assert time.monotonic() - started < 0.5
    finally:
        release.set()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_or_missing_values_are_not_credentials(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "keyring",
        SimpleNamespace(get_password=lambda *_args: value),
    )

    assert read_operator_credential(CUTCTX_LICENSE_ACCOUNT) is None


def test_backend_errors_do_not_escape_or_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: str) -> None:
        raise RuntimeError("backend detail with secret-value")

    monkeypatch.setitem(
        sys.modules,
        "keyring",
        SimpleNamespace(get_password=fail),
    )

    assert read_operator_credential(CUTCTX_LICENSE_ACCOUNT) is None
