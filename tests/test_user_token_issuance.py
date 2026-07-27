"""The paid-tier seat gate needs an issuer, not just a verifier.

`verify_user_token` shipped without a counterpart: nothing minted
`X-Cutctx-User-Token` and `cutctx wrap` never sent one, so a licensed proxy
rejected every provider request with a 503 naming an environment variable
that would not have fixed it alone. These tests pin the issuer, the shared
secret, and the header injection that closes that loop.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from cutctx.auth import user_token_secret as uts
from cutctx.cli.wrap import _append_custom_header, _apply_user_token_header
from cutctx_ee.user_tokens import UserTokenError, issue_user_token, verify_user_token

_LICENSE = "cutctx_test_license"


@pytest.fixture(autouse=True)
def _isolated_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Never touch the real ~/.cutctx secret from tests."""
    monkeypatch.delenv(uts.ENV_VAR, raising=False)
    monkeypatch.setattr(uts, "secret_path", lambda: tmp_path / "user_token_secret")
    return tmp_path


# ----------------------------------------------------------------------
# Issuer / verifier round trip
# ----------------------------------------------------------------------


def test_issued_token_verifies() -> None:
    token = issue_user_token("alice", "s3cret", _LICENSE)

    assert verify_user_token(token, "s3cret", _LICENSE) == "alice"


def test_token_is_bound_to_its_license() -> None:
    """A token minted for one org must not consume another org's seats."""
    token = issue_user_token("alice", "s3cret", _LICENSE)

    with pytest.raises(UserTokenError):
        verify_user_token(token, "s3cret", "cutctx_someone_elses_license")


def test_token_is_bound_to_its_secret() -> None:
    token = issue_user_token("alice", "s3cret", _LICENSE)

    with pytest.raises(UserTokenError):
        verify_user_token(token, "different-secret", _LICENSE)


def test_expired_token_is_rejected() -> None:
    token = issue_user_token("alice", "s3cret", _LICENSE, ttl_seconds=-1)

    with pytest.raises(UserTokenError):
        verify_user_token(token, "s3cret", _LICENSE)


def test_ttl_is_honoured() -> None:
    before = time.time()
    token = issue_user_token("alice", "s3cret", _LICENSE, ttl_seconds=3600)

    verify_user_token(token, "s3cret", _LICENSE)  # not expired
    import base64
    import json

    payload_b64 = token.split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    assert before + 3500 <= payload["exp"] <= before + 3700


@pytest.mark.parametrize(
    ("subject", "secret", "license_key"),
    [("", "s", "l"), ("a", "", "l"), ("a", "s", "")],
)
def test_missing_inputs_fail_loudly(subject: str, secret: str, license_key: str) -> None:
    """Better than minting something rejected later for no obvious reason."""
    with pytest.raises(UserTokenError):
        issue_user_token(subject, secret, license_key)


# ----------------------------------------------------------------------
# Shared secret
# ----------------------------------------------------------------------


def test_secret_is_created_once_and_reused() -> None:
    first = uts.load_or_create_secret()
    second = uts.load_or_create_secret()

    assert first == second
    assert len(first) == 64  # 32 bytes hex


def test_secret_file_is_owner_only(_isolated_secret: Path) -> None:
    uts.load_or_create_secret()

    assert (uts.secret_path().stat().st_mode & 0o777) == 0o600


def test_env_var_wins_over_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deployments terminating elsewhere must be able to pin the secret."""
    uts.load_or_create_secret()
    monkeypatch.setenv(uts.ENV_VAR, "explicit-secret")

    assert uts.load_secret() == "explicit-secret"


def test_load_secret_does_not_provision() -> None:
    """The verifier must not mint a secret no client has ever seen."""
    assert uts.load_secret() is None
    assert not uts.secret_path().exists()


@pytest.mark.uses_local_license
def test_issuer_and_proxy_resolve_the_same_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole point: both halves must agree, or every request 503s."""
    from cutctx.proxy.models import _load_user_token_secret

    issued_with = uts.load_or_create_secret()
    monkeypatch.setattr("cutctx.auth.user_token_secret.secret_path", uts.secret_path)

    assert _load_user_token_secret() == issued_with
    token = issue_user_token("alice", issued_with, _LICENSE)
    assert verify_user_token(token, _load_user_token_secret(), _LICENSE) == "alice"


# ----------------------------------------------------------------------
# Header injection
# ----------------------------------------------------------------------


def test_wrap_attaches_token_when_licensed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUTCTX_LICENSE_KEY", _LICENSE)
    env: dict[str, str] = {}

    assert _apply_user_token_header(env) is True

    headers = env["ANTHROPIC_CUSTOM_HEADERS"]
    line = next(x for x in headers.splitlines() if x.startswith("X-Cutctx-User-Token:"))
    token = line.split(":", 1)[1].strip()
    assert verify_user_token(token, uts.load_or_create_secret(), _LICENSE)


def test_wrap_is_a_noop_on_builder_tier(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Free installs have no seat gate; they must not be asked for a token."""
    monkeypatch.delenv("CUTCTX_LICENSE_KEY", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr("cutctx.paths.license_cache_path", lambda: tmp_path / "nope.json")

    env: dict[str, str] = {}
    assert _apply_user_token_header(env) is False
    assert "ANTHROPIC_CUSTOM_HEADERS" not in env


def test_token_header_coexists_with_project_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUTCTX_LICENSE_KEY", _LICENSE)
    env = {"ANTHROPIC_CUSTOM_HEADERS": "X-Cutctx-Project: demo"}

    _apply_user_token_header(env)

    lines = env["ANTHROPIC_CUSTOM_HEADERS"].splitlines()
    assert "X-Cutctx-Project: demo" in lines
    assert any(x.startswith("X-Cutctx-User-Token:") for x in lines)


def test_user_supplied_header_is_never_overwritten() -> None:
    env = {"ANTHROPIC_CUSTOM_HEADERS": "x-cutctx-user-token: mine"}

    _append_custom_header(env, "X-Cutctx-User-Token", "ours")

    assert env["ANTHROPIC_CUSTOM_HEADERS"] == "x-cutctx-user-token: mine"
