"""Unit tests for local seat-token resolution (Codex loopback fallback)."""

from __future__ import annotations

import base64
import json
import os
import time

from cutctx.auth.local_seat import (
    LOCAL_SEAT_TTL_SECONDS,
    control_seat_path,
    is_trusted_local_seat_connection,
    load_control_seat_token,
    remint_local_seat_token,
    resolve_local_user_token,
    save_control_seat_token,
)
from cutctx_ee.user_tokens import issue_user_token, verify_user_token


def test_load_control_seat_token_reads_ctu1(tmp_path) -> None:
    path = control_seat_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"subject": "aryan", "token": "ctu1.payload.sig", "issued_at_unix": 1}),
        encoding="utf-8",
    )
    assert load_control_seat_token(tmp_path) == "ctu1.payload.sig"


def test_load_control_seat_token_rejects_non_ctu1(tmp_path) -> None:
    path = control_seat_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"token": "sk-not-a-seat"}), encoding="utf-8")
    assert load_control_seat_token(tmp_path) is None


def test_resolve_prefers_env_over_seat_file(tmp_path, monkeypatch) -> None:
    path = control_seat_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"token": "ctu1.from.file"}), encoding="utf-8")
    monkeypatch.setenv("CUTCTX_USER_TOKEN", "ctu1.from.env")
    assert resolve_local_user_token(home=tmp_path) == "ctu1.from.env"


def test_resolve_falls_back_to_seat_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_USER_TOKEN", raising=False)
    path = control_seat_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"token": "ctu1.from.file"}), encoding="utf-8")
    assert resolve_local_user_token(home=tmp_path) == "ctu1.from.file"


def test_resolve_skips_expired_env_for_fresher_seat_file(tmp_path, monkeypatch) -> None:
    secret = "s3cret"
    license_key = "cutctx_lic"
    expired = issue_user_token("aryan", secret, license_key, ttl_seconds=-1)
    fresh = issue_user_token("aryan", secret, license_key, ttl_seconds=3600)
    monkeypatch.setenv("CUTCTX_USER_TOKEN", expired)
    save_control_seat_token(fresh, "aryan", home=tmp_path)
    assert resolve_local_user_token(home=tmp_path, secret=secret, license_key=license_key) == fresh


def test_save_control_seat_token_writes_private_schema(tmp_path) -> None:
    path = save_control_seat_token("ctu1.payload.sig", "aryan", home=tmp_path, issued_at_unix=42)
    assert path == control_seat_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "subject": "aryan",
        "token": "ctu1.payload.sig",
        "issued_at_unix": 42,
    }
    assert path.stat().st_mode & 0o777 == 0o600


def test_remint_local_seat_token_persists_and_exports_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_USER_TOKEN", raising=False)
    secret = "s3cret"
    license_key = "cutctx_lic"
    before = time.time()
    token = remint_local_seat_token(
        secret=secret,
        license_key=license_key,
        subject="aryan",
        home=tmp_path,
    )
    assert verify_user_token(token, secret, license_key) == "aryan"
    assert os.environ["CUTCTX_USER_TOKEN"] == token
    assert load_control_seat_token(tmp_path) == token
    payload_b64 = token.split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    assert (
        before + LOCAL_SEAT_TTL_SECONDS - 5 <= payload["exp"] <= before + LOCAL_SEAT_TTL_SECONDS + 5
    )


def test_local_seat_connection_requires_an_explicit_loopback_peer() -> None:
    assert is_trusted_local_seat_connection(
        bind_host="127.0.0.1",
        host_header="127.0.0.1:8787",
        client_host="127.0.0.1",
    )
    assert is_trusted_local_seat_connection(
        bind_host="127.0.0.1",
        host_header="localhost:8787",
        client_host="testclient",
    )
    assert not is_trusted_local_seat_connection(
        bind_host="127.0.0.1",
        host_header="127.0.0.1:8787",
        client_host=None,
    )
    assert not is_trusted_local_seat_connection(
        bind_host="127.0.0.1",
        host_header="127.0.0.1:8787",
        client_host="made-up-peer",
    )
    assert not is_trusted_local_seat_connection(
        bind_host="0.0.0.0",
        host_header="127.0.0.1:8787",
        client_host="127.0.0.1",
    )
