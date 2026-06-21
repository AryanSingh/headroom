# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for SecretsStore and the /v1/secrets/* endpoints.

Audit-Deep-2026-06-21 Blocker 3b: the previous /v1/secrets/*
endpoints were a stub. These tests pin the new behavior.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def _tmp_key() -> bytes:
    """Return a fresh Fernet key for tests."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key()


@pytest.fixture
def tmp_store(tmp_path: Path):
    from headroom.security.secrets_store import SecretsStore

    key = _tmp_key()
    db = tmp_path / "secrets.db"
    store = SecretsStore(db_path=str(db), strict=True, encryption_key=key)
    yield store
    store.close()


class TestSecretsStore:
    def test_set_then_get(self, tmp_store):
        tmp_store.set("api_key", "sk-12345")
        s = tmp_store.get("api_key")
        assert s is not None
        assert s.value == b"sk-12345"

    def test_set_then_list(self, tmp_store):
        tmp_store.set("a", "1")
        tmp_store.set("b", "2")
        listing = tmp_store.list()
        names = {item["name"] for item in listing}
        assert names == {"a", "b"}
        # List returns metadata, NOT values
        for item in listing:
            assert "value" not in item
            assert "ciphertext" not in item

    def test_upsert_preserves_created_at(self, tmp_store):
        s1 = tmp_store.set("name", "v1")
        created = s1.created_at_ts
        s2 = tmp_store.set("name", "v2")
        assert s2.created_at_ts == created
        assert s2.updated_at_ts >= s1.updated_at_ts
        assert tmp_store.get("name").value == b"v2"

    def test_delete_returns_true_when_present(self, tmp_store):
        tmp_store.set("x", "1")
        assert tmp_store.delete("x") is True
        assert tmp_store.get("x") is None

    def test_delete_returns_false_when_absent(self, tmp_store):
        assert tmp_store.delete("missing") is False

    def test_encryption_at_rest(self, tmp_path: Path):
        """The on-disk ciphertext must not contain the plaintext."""
        from headroom.security.secrets_store import SecretsStore

        key = _tmp_key()
        db = tmp_path / "secrets.db"
        store = SecretsStore(
            db_path=str(db), strict=True, encryption_key=key
        )
        store.set("api_key", "sk-supersecretvalue")
        # Read the raw SQLite file and confirm plaintext is not present.
        with open(db, "rb") as f:
            raw = f.read()
        assert b"sk-supersecretvalue" not in raw
        store.close()

    def test_resolve_finds_stored_value(self, tmp_store):
        tmp_store.set("db_url", "postgres://localhost:5432/x")
        assert tmp_store.resolve("db_url") == b"postgres://localhost:5432/x"

    def test_resolve_falls_back_to_env(self, tmp_store, monkeypatch):
        monkeypatch.setenv("MY_SECRET_TOKEN", "env-value")
        assert tmp_store.resolve("my_secret_token") == b"env-value"

    def test_resolve_raises_keyerror(self, tmp_store):
        with pytest.raises(KeyError):
            tmp_store.resolve("not_set_anywhere")

    def test_resolve_returns_default(self, tmp_store):
        assert tmp_store.resolve("not_set", default=b"fallback") == b"fallback"

    def test_wrong_key_raises_on_decrypt(self, tmp_path: Path):
        """Re-opening with a different key must fail loudly, not silently."""
        from headroom.security.secrets_store import SecretsStore

        key_a = _tmp_key()
        key_b = _tmp_key()
        db = tmp_path / "secrets.db"
        s1 = SecretsStore(
            db_path=str(db), strict=True, encryption_key=key_a
        )
        s1.set("k", "v")
        s1.close()
        s2 = SecretsStore(
            db_path=str(db), strict=True, encryption_key=key_b
        )
        with pytest.raises(RuntimeError, match="failed to decrypt"):
            s2.get("k")

    def test_strict_refuses_unset_key(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("CUTCTX_SECRETS_KEY", raising=False)
        monkeypatch.delenv("HEADROOM_LICENSE_HMAC_SECRET", raising=False)
        from headroom.security.secrets_store import SecretsStore

        with pytest.raises(RuntimeError, match="no encryption key"):
            SecretsStore(
                db_path=str(tmp_path / "s.db"), strict=True
            )

    def test_non_strict_auto_generates_key_with_warning(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.delenv("CUTCTX_SECRETS_KEY", raising=False)
        monkeypatch.delenv("HEADROOM_LICENSE_HMAC_SECRET", raising=False)
        from headroom.security.secrets_store import SecretsStore

        store = SecretsStore(
            db_path=str(tmp_path / "s.db"), strict=False
        )
        # The store should be usable, but secrets won't survive a restart.
        store.set("a", "1")
        assert store.get("a").value == b"1"


class TestSecretsRoute:
    def test_create_then_list(self, tmp_path: Path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from headroom.proxy.routes.secrets import create_secrets_router
        from headroom.security.secrets_store import SecretsStore

        key = _tmp_key()
        store = SecretsStore(
            db_path=str(tmp_path / "secrets.db"),
            strict=True,
            encryption_key=key,
        )

        app = FastAPI()
        app.include_router(create_secrets_router(secrets_store=store))
        client = TestClient(app)
        # Create
        resp = client.post(
            "/v1/secrets/", json={"name": "alpha", "value": "first"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["name"] == "alpha"
        # List (no value)
        resp = client.get("/v1/secrets/")
        assert resp.status_code == 200
        listing = resp.json()
        assert len(listing) == 1
        assert listing[0]["name"] == "alpha"
        assert "value" not in listing[0]
        # Update via PUT
        resp = client.put(
            "/v1/secrets/alpha", json={"value": "second"}
        )
        assert resp.status_code == 200
        # Delete
        resp = client.delete("/v1/secrets/alpha")
        assert resp.status_code == 200
        # Now empty
        assert client.get("/v1/secrets/").json() == []
        # Delete of missing returns 404
        resp = client.delete("/v1/secrets/alpha")
        assert resp.status_code == 404
