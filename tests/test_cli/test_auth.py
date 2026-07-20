from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cutctx.auth.client_credentials import (
    ClientCredentialStatus,
    normalize_proxy_origin,
)
from cutctx.cli import auth as auth_mod
from cutctx.cli.main import main


@dataclass
class MemoryStore:
    values: dict[str, str] = field(default_factory=dict)

    def get(self, proxy_origin: str) -> str | None:
        return self.values.get(normalize_proxy_origin(proxy_origin))

    def set(self, proxy_origin: str, value: str) -> None:
        self.values[normalize_proxy_origin(proxy_origin)] = value

    def delete(self, proxy_origin: str) -> bool:
        return self.values.pop(normalize_proxy_origin(proxy_origin), None) is not None


def test_login_hides_input_validates_then_stores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    monkeypatch.setattr(auth_mod, "_store", lambda: store)
    monkeypatch.setattr(
        auth_mod,
        "validate_client_credential",
        lambda origin, credential: ClientCredentialStatus("valid"),
    )

    result = CliRunner().invoke(
        main,
        ["auth", "login", "--proxy-url", "https://proxy.example"],
        input="client-secret\n",
    )

    assert result.exit_code == 0, result.output
    assert store.get("https://proxy.example") == "client-secret"
    assert "client-secret" not in result.output


def test_login_does_not_store_invalid_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    monkeypatch.setattr(auth_mod, "_store", lambda: store)
    monkeypatch.setattr(
        auth_mod,
        "validate_client_credential",
        lambda origin, credential: ClientCredentialStatus("invalid"),
    )

    result = CliRunner().invoke(
        main,
        ["auth", "login", "--proxy-url", "https://proxy.example"],
        input="bad-secret\n",
    )

    assert result.exit_code != 0
    assert store.get("https://proxy.example") is None
    assert "bad-secret" not in result.output


def test_rotate_keeps_old_key_when_replacement_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore({"https://proxy.example": "old-secret"})
    monkeypatch.setattr(auth_mod, "_store", lambda: store)
    monkeypatch.setattr(
        auth_mod,
        "validate_client_credential",
        lambda origin, credential: ClientCredentialStatus("invalid"),
    )

    result = CliRunner().invoke(
        main,
        ["auth", "rotate", "--proxy-url", "https://proxy.example"],
        input="bad-secret\n",
    )

    assert result.exit_code != 0
    assert store.get("https://proxy.example") == "old-secret"
    assert "old-secret" not in result.output
    assert "bad-secret" not in result.output


def test_status_reports_expired_without_printing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore({"https://proxy.example": "client-secret"})
    monkeypatch.setattr(auth_mod, "_store", lambda: store)
    monkeypatch.setattr(
        auth_mod,
        "validate_client_credential",
        lambda origin, credential: ClientCredentialStatus(
            "expired",
            expires_at="2026-07-20T00:00:00Z",
        ),
    )

    result = CliRunner().invoke(
        main,
        ["auth", "status", "--proxy-url", "https://proxy.example"],
    )

    assert result.exit_code != 0
    assert "expired" in result.output.lower()
    assert "2026-07-20T00:00:00Z" in result.output
    assert "client-secret" not in result.output


def test_logout_removes_only_selected_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore(
        {
            "https://proxy.example": "first-secret",
            "https://other.example": "second-secret",
        }
    )
    monkeypatch.setattr(auth_mod, "_store", lambda: store)

    result = CliRunner().invoke(
        main,
        ["auth", "logout", "--proxy-url", "https://proxy.example"],
    )

    assert result.exit_code == 0
    assert store.get("https://proxy.example") is None
    assert store.get("https://other.example") == "second-secret"
    assert "first-secret" not in result.output
    assert "second-secret" not in result.output


def test_exec_injects_key_without_putting_it_in_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    store = MemoryStore({"https://proxy.example": "client-secret"})
    monkeypatch.setattr(auth_mod, "_store", lambda: store)
    monkeypatch.setattr(
        auth_mod.subprocess,
        "run",
        lambda command, env: captured.update(command=command, env=env)
        or SimpleNamespace(returncode=0),
    )

    result = CliRunner().invoke(
        main,
        [
            "auth",
            "exec",
            "--proxy-url",
            "https://proxy.example",
            "--",
            "probe",
            "--flag",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["command"] == ("probe", "--flag")
    assert isinstance(captured["env"], dict)
    assert captured["env"]["CUTCTX_API_KEY"] == "client-secret"
    assert all("client-secret" not in arg for arg in captured["command"])
    assert "client-secret" not in result.output
