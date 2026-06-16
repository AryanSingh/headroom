"""Tests for security/state_crypto.py — encryption, HMAC signing, file I/O."""

from __future__ import annotations

import json

import pytest

from headroom.security.state_crypto import (
    _ENCRYPTED_MARKER,
    decrypt_json,
    derive_fernet_key,
    encrypt_json,
    read_encrypted_json,
    read_hmac_json,
    sign_payload,
    verify_payload,
    write_encrypted_json,
    write_hmac_json,
)


class TestFernetKey:
    """Machine-derived Fernet key tests."""

    def test_derive_fernet_key_returns_bytes(self):
        key = derive_fernet_key()
        assert isinstance(key, bytes)

    def test_derive_fernet_key_deterministic(self):
        key1 = derive_fernet_key()
        key2 = derive_fernet_key()
        assert key1 == key2

    def test_derive_fernet_key_from_env(self, monkeypatch):
        monkeypatch.setenv("HEADROOM_STATE_ENCRYPTION_KEY", "test-key-12345678901234567890")
        key = derive_fernet_key()
        assert key == b"test-key-12345678901234567890"


class TestEncryptDecrypt:
    """Fernet encryption round-trip tests."""

    def test_roundtrip(self):
        data = {"name": "alice", "count": 42, "nested": {"key": "value"}}
        token = encrypt_json(data)
        result = decrypt_json(token)
        assert result == data

    def test_different_tokens(self):
        """Same data should produce different tokens (random IV)."""
        data = {"key": "value"}
        t1 = encrypt_json(data)
        t2 = encrypt_json(data)
        assert t1 != t2

    def test_decrypt_tampered(self):
        data = {"key": "value"}
        token = encrypt_json(data)
        # Tamper with token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            decrypt_json(tampered)

    def test_empty_dict(self):
        data = {}
        token = encrypt_json(data)
        result = decrypt_json(token)
        assert result == {}

    def test_unicode_data(self):
        data = {"name": "日本語テスト", "emoji": "🚀"}
        token = encrypt_json(data)
        result = decrypt_json(token)
        assert result == data

    def test_custom_key(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        data = {"secret": "data"}
        token = encrypt_json(data, key=key)
        result = decrypt_json(token, key=key)
        assert result == data

    def test_wrong_key_fails(self):
        from cryptography.fernet import Fernet

        key1 = Fernet.generate_key()
        key2 = Fernet.generate_key()
        data = {"secret": "data"}
        token = encrypt_json(data, key=key1)
        with pytest.raises(Exception):
            decrypt_json(token, key=key2)


class TestHMACSigning:
    """HMAC-SHA256 signature tests."""

    def test_sign_and_verify(self):
        data = {"plan": "team", "org_id": "abc123"}
        sig = sign_payload(data, secret="test-secret-key")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex digest
        assert verify_payload(data, sig, secret="test-secret-key")

    def test_verify_wrong_signature(self):
        data = {"plan": "team"}
        sig = sign_payload(data, secret="key")
        assert not verify_payload(data, "0" * 64, secret="key")

    def test_verify_tampered_data(self):
        data = {"plan": "team"}
        sig = sign_payload(data, secret="key")
        tampered = {"plan": "enterprise"}
        assert not verify_payload(tampered, sig, secret="key")

    def test_no_secret_skips(self):
        """Without a secret, signing returns empty string, verify returns True."""
        data = {"key": "value"}
        sig = sign_payload(data, secret=None)
        assert sig == ""
        assert verify_payload(data, "", secret=None)

    def test_deterministic_signature(self):
        data = {"a": 1, "b": 2}
        sig1 = sign_payload(data, secret="key")
        sig2 = sign_payload(data, secret="key")
        assert sig1 == sig2

    def test_key_order_independent(self):
        """Sorted keys means dict key order doesn't affect signature."""
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}
        sig1 = sign_payload(data1, secret="key")
        sig2 = sign_payload(data2, secret="key")
        assert sig1 == sig2


class TestEncryptedFileIO:
    """Encrypted file write/read tests."""

    def test_write_read_roundtrip(self, tmp_path):
        path = tmp_path / "state.json"
        data = {"trial": True, "seat": 1}
        write_encrypted_json(path, data)
        result = read_encrypted_json(path)
        assert result == data

    def test_file_format(self, tmp_path):
        path = tmp_path / "state.json"
        write_encrypted_json(path, {"key": "value"})
        content = path.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == _ENCRYPTED_MARKER
        assert len(lines) == 2

    def test_read_nonexistent(self, tmp_path):
        result = read_encrypted_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_read_plain_json_fallback(self, tmp_path):
        """Plain JSON files (migration path) should be read."""
        path = tmp_path / "legacy.json"
        path.write_text(json.dumps({"legacy": True}))
        result = read_encrypted_json(path)
        assert result == {"legacy": True}

    def test_read_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json at all {{{")
        result = read_encrypted_json(path)
        assert result is None

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "state.json"
        write_encrypted_json(path, {"deep": True})
        assert path.exists()


class TestHMACFileIO:
    """HMAC-signed file write/read tests."""

    def test_write_read_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HEADROOM_LICENSE_HMAC_SECRET", "test-secret-key-for-testing")
        path = tmp_path / "license.json"
        data = {"plan": "business", "expires": "2025-12-31"}
        write_hmac_json(path, data)
        result = read_hmac_json(path)
        assert result == data

    def test_file_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HEADROOM_LICENSE_HMAC_SECRET", "test-secret-key-for-testing")
        path = tmp_path / "license.json"
        write_hmac_json(path, {"plan": "team"})
        content = json.loads(path.read_text())
        assert "payload" in content
        assert "signature" in content
        assert content["payload"] == {"plan": "team"}

    def test_read_nonexistent(self, tmp_path):
        result = read_hmac_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_tampered_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HEADROOM_LICENSE_HMAC_SECRET", "test-secret-key-for-testing")
        path = tmp_path / "tampered.json"
        data = {"plan": "team"}
        write_hmac_json(path, data)
        # Tamper with payload
        content = json.loads(path.read_text())
        content["payload"]["plan"] = "enterprise"
        path.write_text(json.dumps(content))
        result = read_hmac_json(path)
        assert result is None

    def test_legacy_plain_json(self, tmp_path):
        """Legacy plain JSON without HMAC envelope should be read as-is."""
        path = tmp_path / "legacy.json"
        path.write_text(json.dumps({"legacy": True}))
        result = read_hmac_json(path)
        assert result == {"legacy": True}

    def test_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("{invalid json")
        result = read_hmac_json(path)
        assert result is None
