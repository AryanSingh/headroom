"""Bounded reads for credentials shared with the CutCtx desktop app.

The desktop app stores operator secrets in the OS credential manager under a
stable service/account pair. Runtime consumers use this module so platform
keyring calls cannot indefinitely block proxy or CLI startup.
"""

from __future__ import annotations

import queue
import threading

SERVICE_NAME = "io.cutctx.control"
CUTCTX_LICENSE_ACCOUNT = "cutctx_license_key"
DEFAULT_TIMEOUT_SECONDS = 5.0


def read_operator_credential(
    account: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str | None:
    """Return one OS-protected operator credential without leaking failures.

    Keychain backends may prompt or wait on a locked desktop session. The
    daemon worker gives callers a hard deadline; unavailable, failed, empty,
    and timed-out reads all fail closed as ``None``.
    """

    if timeout_seconds <= 0:
        raise ValueError("Credential-store timeout must be greater than zero.")

    result: queue.Queue[object] = queue.Queue(maxsize=1)
    missing = object()

    def invoke() -> None:
        try:
            import keyring

            result.put(keyring.get_password(SERVICE_NAME, account))
        except BaseException:
            result.put(missing)

    worker = threading.Thread(
        target=invoke,
        name="cutctx-operator-keyring-read",
        daemon=True,
    )
    worker.start()
    try:
        value = result.get(timeout=timeout_seconds)
    except queue.Empty:
        return None
    if value is missing or not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


__all__ = [
    "CUTCTX_LICENSE_ACCOUNT",
    "DEFAULT_TIMEOUT_SECONDS",
    "SERVICE_NAME",
    "read_operator_credential",
]
