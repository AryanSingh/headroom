"""Resolve a local seat token for header-incapable loopback clients.

Codex ChatGPT/desktop routes through the built-in ``openai`` provider via
``openai_base_url`` and cannot attach ``X-Cutctx-User-Token``. CutCtx Control
mints a token into ``~/.cutctx/control/seat.json`` (and may export
``CUTCTX_USER_TOKEN`` on the proxy process). The paid seat gate can then
accept that pre-provisioned token for trusted loopback traffic only.

Tokens still expire (leak-limiting TTL), but the proxy remints automatically
for trusted loopback when the local seat is missing or expired — no human
``cutctx license token`` step required.
"""

from __future__ import annotations

import getpass
import ipaddress
import json
import os
import time
from pathlib import Path

__all__ = [
    "LOCAL_SEAT_TTL_SECONDS",
    "control_seat_path",
    "is_trusted_local_seat_connection",
    "load_control_seat_token",
    "remint_local_seat_token",
    "resolve_local_user_token",
    "resolve_seat_subject",
    "save_control_seat_token",
]

#: Default lifetime for auto-reminted / CLI-minted local seats. Long enough
#: that overnight Codex/Cursor sessions survive without a remint storm; short
#: enough that a leaked ``ctu1`` token still dies on its own. The paid seat
#: gate remints on expiry for trusted loopback, so this is a soft interval.
LOCAL_SEAT_TTL_SECONDS = 72 * 60 * 60


def is_trusted_local_seat_connection(
    *,
    bind_host: str | None,
    host_header: str | None,
    client_host: str | None,
) -> bool:
    """Require loopback bind, Host header, and an explicit loopback peer.

    ``testclient`` is Starlette's exact in-process test sentinel. Every other
    non-IP or missing peer fails closed.
    """

    from cutctx.proxy.loopback_guard import is_loopback_host, is_loopback_host_header

    if not bind_host or not is_loopback_host(bind_host):
        return False
    if not is_loopback_host_header(host_header):
        return False
    if client_host == "testclient":
        return True
    if not client_host:
        return False
    try:
        address = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_loopback
    return address.is_loopback


def control_seat_path(home: Path | None = None) -> Path:
    root = home if home is not None else Path.home()
    return root / ".cutctx" / "control" / "seat.json"


def resolve_seat_subject() -> str:
    """Stable per-user identity a seat is leased to (not per-process)."""
    try:
        return getpass.getuser() or "cutctx-user"
    except Exception:
        return os.environ.get("USER") or os.environ.get("USERNAME") or "cutctx-user"


def load_control_seat_token(home: Path | None = None) -> str | None:
    """Return a ``ctu1…`` token from Control's seat file, if present."""
    path = control_seat_path(home)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str):
        return None
    token = token.strip()
    if not token.startswith("ctu1."):
        return None
    return token


def save_control_seat_token(
    token: str,
    subject: str,
    *,
    home: Path | None = None,
    issued_at_unix: int | None = None,
) -> Path:
    """Persist a seat token in the Control schema (mode ``0600``)."""
    if not token.startswith("ctu1."):
        raise ValueError("seat token must be a ctu1 user token")
    if not subject:
        raise ValueError("seat subject is required")
    path = control_seat_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "subject": subject,
        "token": token,
        "issued_at_unix": int(time.time() if issued_at_unix is None else issued_at_unix),
    }
    data = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    # Atomic-ish replace with private perms (Control writes the same shape).
    tmp = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def remint_local_seat_token(
    *,
    secret: str,
    license_key: str,
    subject: str | None = None,
    home: Path | None = None,
    ttl_seconds: float | None = None,
) -> str:
    """Mint a fresh ``ctu1`` token, write ``seat.json``, and refresh process env."""
    from cutctx_ee.user_tokens import issue_user_token

    seat_subject = subject or resolve_seat_subject()
    token = issue_user_token(
        seat_subject,
        secret,
        license_key,
        ttl_seconds=LOCAL_SEAT_TTL_SECONDS if ttl_seconds is None else ttl_seconds,
    )
    save_control_seat_token(token, seat_subject, home=home)
    os.environ["CUTCTX_USER_TOKEN"] = token
    return token


def resolve_local_user_token(
    *,
    home: Path | None = None,
    secret: str | None = None,
    license_key: str | None = None,
) -> str | None:
    """Prefer ``CUTCTX_USER_TOKEN`` env, then Control ``seat.json``.

    When ``secret`` and ``license_key`` are provided, skip candidates that fail
    verification so a stale env token does not permanently beat a fresher
    ``seat.json`` (common after Control remints without restarting the proxy).
    If every candidate fails, return the first one so the caller can remint.
    """
    candidates: list[str] = []
    from_env = (os.environ.get("CUTCTX_USER_TOKEN") or "").strip()
    if from_env.startswith("ctu1."):
        candidates.append(from_env)
    from_file = load_control_seat_token(home)
    if from_file and from_file not in candidates:
        candidates.append(from_file)
    if not candidates:
        return None
    if not secret or not license_key:
        return candidates[0]

    from cutctx_ee.user_tokens import UserTokenError, verify_user_token

    first: str | None = None
    for token in candidates:
        if first is None:
            first = token
        try:
            verify_user_token(token, secret, license_key)
            return token
        except UserTokenError:
            continue
    return first
