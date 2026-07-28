"""Unit tests for local seat-token resolution (Codex loopback fallback)."""

from __future__ import annotations

import json

from cutctx.auth.local_seat import (
    control_seat_path,
    is_trusted_local_seat_connection,
    load_control_seat_token,
    resolve_local_user_token,
)


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
