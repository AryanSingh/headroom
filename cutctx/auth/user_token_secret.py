"""Machine-local HMAC secret shared by the user-token issuer and verifier.

Paid provider traffic must carry ``X-Cutctx-User-Token``, an HMAC-signed
assertion of *which user* a request belongs to, so the seat gate can lease a
seat against a subject that a client cannot spoof. Signing and verification
therefore need the same secret.

Until now only the verifier existed. ``CUTCTX_USER_TOKEN_HMAC_SECRET`` had to
be set by hand, nothing issued a matching token, and no client sent the
header — so a licensed proxy rejected every request with a 503 telling the
operator to configure a variable that would not have helped on its own. This
module supplies the shared secret both halves need.

The secret is machine-local and self-provisioning: the first caller creates
it, everyone else reads it. That is the right scope because the issuer
(``cutctx wrap`` / ``cutctx license token``) and the verifier (the loopback
proxy) run as the same user on the same host. A deployment that terminates
traffic somewhere else should set ``CUTCTX_USER_TOKEN_HMAC_SECRET``
explicitly, which always wins over the file.

Security notes:

* The file is created with mode ``0600`` via ``O_CREAT | O_EXCL``, so a
  concurrent creator loses the race harmlessly and falls back to reading.
* This secret is not a licence and grants nothing on its own. It binds a
  local user identity to a seat request; entitlement still comes from the
  licence and the Supabase seat service.
* Never log the value. Callers wanting to show state should report presence
  and path only.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from cutctx import paths as _paths

ENV_VAR = "CUTCTX_USER_TOKEN_HMAC_SECRET"

#: 32 bytes hex — matches the HMAC-SHA256 block the tokens are signed with.
_SECRET_BYTES = 32

_FILE_NAME = "user_token_secret"


def secret_path() -> Path:
    """Return the path of the machine-local user-token secret."""
    return _paths.config_dir() / _FILE_NAME


def _read_secret(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def load_secret() -> str | None:
    """Return the configured secret without creating one.

    Order: ``CUTCTX_USER_TOKEN_HMAC_SECRET``, then the machine-local file.
    Returns ``None`` when neither is present — callers on the verifying side
    use this so an unconfigured proxy reports honestly rather than silently
    minting a secret the client half has never seen.
    """
    from_env = os.environ.get(ENV_VAR)
    if from_env and from_env.strip():
        return from_env.strip()
    return _read_secret(secret_path())


def load_or_create_secret() -> str:
    """Return the shared secret, provisioning it on first use.

    Used by both halves so a fresh install works without the operator having
    to invent and distribute a secret by hand.
    """
    existing = load_secret()
    if existing:
        return existing

    path = secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = secrets.token_hex(_SECRET_BYTES)
    try:
        # O_EXCL so two concurrent starts cannot end up with different
        # secrets: the loser reads what the winner wrote.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return _read_secret(path) or candidate
    except OSError:
        # Read-only home or similar. Return an ephemeral secret rather than
        # failing: it still works for a single process that both signs and
        # verifies, and the caller surfaces the unconfigured state.
        return candidate
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(candidate + "\n")
    except OSError:
        return candidate
    return candidate


__all__ = ["ENV_VAR", "load_or_create_secret", "load_secret", "secret_path"]
