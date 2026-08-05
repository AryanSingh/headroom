"""H6 regression: credentials must never reach a log/history sink in cleartext.

The audit found the admin API key written in cleartext to
``~/.cutctx/logs/request_history.jsonl`` (445 MB, mode 0644).

Covers each credential shape, plus the file-permission and rotation fixes on
``RequestLogger``.
"""

from __future__ import annotations

import json
import os
import stat

import pytest

from cutctx.proxy.models import RequestLog
from cutctx.proxy.request_logger import RequestLogger
from cutctx.security.redaction import (
    REDACTED,
    clear_registered_secrets,
    is_secret_key_name,
    redact_structure,
    redact_text,
    register_secret_value,
)


@pytest.fixture(autouse=True)
def _clean_secrets():
    clear_registered_secrets()
    yield
    clear_registered_secrets()


def make_log(**overrides) -> RequestLog:
    """Build a RequestLog with all required fields defaulted."""
    fields = {
        "request_id": "req-1",
        "timestamp": "2026-08-04T00:00:00+00:00",
        "provider": "openai",
        "model": "gpt-4",
        "input_tokens_original": 100,
        "input_tokens_optimized": 80,
        "output_tokens": 20,
        "tokens_saved": 20,
        "savings_percent": 20.0,
        "optimization_latency_ms": 1.0,
        "total_latency_ms": 10.0,
        "tags": {},
        "cache_hit": False,
        "transforms_applied": [],
    }
    fields.update(overrides)
    return RequestLog(**fields)


# --------------------------------------------------------------------------
# Value-shape redaction, one test per credential shape
# --------------------------------------------------------------------------


def test_redacts_openai_provider_key():
    out = redact_text("using sk-abcdefghijklmnopqrstuvwxyz012345 now")
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in out
    assert REDACTED in out


def test_redacts_anthropic_provider_key():
    out = redact_text("key=sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF")
    assert "sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF" not in out


def test_redacts_bearer_authorization_header():
    out = redact_text("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in out
    assert "Bearer" in out  # keep the scheme so logs stay diagnosable


def test_redacts_basic_authorization_header():
    out = redact_text("authorization: Basic dXNlcjpwYXNzd29yZDEyMzQ1")
    assert "dXNlcjpwYXNzd29yZDEyMzQ1" not in out


def test_redacts_license_key_shape():
    out = redact_text("license hlk_" + "9f3c" * 10)
    assert "9f3c9f3c" not in out


def test_redacts_secret_assignment_forms():
    out = redact_text('CUTCTX_ADMIN_API_KEY=supersecretvalue123 and "token": "abcdefgh12345678"')
    assert "supersecretvalue123" not in out
    assert "abcdefgh12345678" not in out


def test_registered_admin_key_is_redacted_despite_having_no_shape():
    """The admin key is operator-chosen — no regex can match it."""
    admin_key = "correct-horse-battery-staple-42"
    assert redact_text(f"x-cutctx-admin-key: {admin_key}") != REDACTED
    register_secret_value(admin_key)
    out = redact_text(f"x-cutctx-admin-key: {admin_key}")
    assert admin_key not in out
    assert REDACTED in out


def test_register_ignores_short_values():
    """Registering a tiny string must not corrupt unrelated log content."""
    register_secret_value("abc")
    assert redact_text("abc def") == "abc def"


# --------------------------------------------------------------------------
# Key-name redaction
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "admin-key",
        "x-cutctx-admin-key",
        "client_api_key",
        "license_key",
        "authorization",
        "password",
        "credential",
        "refresh_token",
        # Infix cases the suffix-only helper in proxy/helpers.py misses:
        "admin-key-v2",
        "x-cutctx-credential",
    ],
)
def test_secret_key_names_detected(key):
    assert is_secret_key_name(key) is True


@pytest.mark.parametrize("key", ["model", "duration_ms", "monkey", "tokens_saved"])
def test_ordinary_key_names_not_flagged(key):
    assert is_secret_key_name(key) is False


def test_redact_structure_walks_nested_containers():
    payload = {
        "tags": {"admin-key": "s3cret-admin-value", "route": "openai"},
        "items": [{"authorization": "Bearer abcdefghijklmnop"}, "sk-aaaaaaaaaaaaaaaaaaaa"],
        "model": "gpt-4",
    }
    out = redact_structure(payload)
    assert out["tags"]["admin-key"] == REDACTED
    assert out["tags"]["route"] == "openai"
    assert out["items"][0]["authorization"] == REDACTED
    assert "sk-aaaaaaaaaaaaaaaaaaaa" not in out["items"][1]
    assert out["model"] == "gpt-4"
    # input untouched
    assert payload["tags"]["admin-key"] == "s3cret-admin-value"


# --------------------------------------------------------------------------
# RequestLogger integration — the actual sink from the audit
# --------------------------------------------------------------------------


def _read_lines(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_request_logger_does_not_write_admin_key_to_jsonl(tmp_path):
    """The exact H6 finding: admin key under tags/admin-key in the history."""
    log_file = tmp_path / "request_history.jsonl"
    rl = RequestLogger(log_file=str(log_file))
    admin_key = "operator-chosen-admin-key-value"
    register_secret_value(admin_key)

    rl.log(make_log(tags={"admin-key": admin_key, "route": "openai"}))

    raw = log_file.read_text(encoding="utf-8")
    assert admin_key not in raw
    record = _read_lines(log_file)[0]
    assert record["tags"]["admin-key"] == REDACTED
    assert record["tags"]["route"] == "openai"


def test_request_logger_redacts_provider_key_in_error_field(tmp_path):
    log_file = tmp_path / "request_history.jsonl"
    rl = RequestLogger(log_file=str(log_file))
    rl.log(make_log(error="401 from sk-abcdefghijklmnopqrstuv"))
    raw = log_file.read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuv" not in raw


def test_request_logger_creates_file_0600(tmp_path):
    """H6: the audited file was mode 0644 — world readable."""
    log_file = tmp_path / "logs" / "request_history.jsonl"
    rl = RequestLogger(log_file=str(log_file))
    rl.log(make_log())

    mode = stat.S_IMODE(os.stat(log_file).st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"
    dir_mode = stat.S_IMODE(os.stat(log_file.parent).st_mode)
    assert dir_mode == 0o700, f"expected 0700 on log dir, got {oct(dir_mode)}"


def test_request_logger_tightens_permissions_on_existing_world_readable_file(tmp_path):
    """An already-0644 log must be tightened, not left as-is.

    os.open()'s mode argument only applies at creation, which is why the
    implementation must fchmod the descriptor.
    """
    log_file = tmp_path / "request_history.jsonl"
    log_file.write_text("", encoding="utf-8")
    os.chmod(log_file, 0o644)
    assert stat.S_IMODE(os.stat(log_file).st_mode) == 0o644

    rl = RequestLogger(log_file=str(log_file))
    rl.log(make_log())

    assert stat.S_IMODE(os.stat(log_file).st_mode) == 0o600


def test_request_logger_rotates_when_oversized(tmp_path, monkeypatch):
    """H6: the audited file had grown to 445 MB with no cap."""
    monkeypatch.setenv("CUTCTX_REQUEST_LOG_MAX_BYTES", "512")
    log_file = tmp_path / "request_history.jsonl"
    rl = RequestLogger(log_file=str(log_file))

    for _ in range(40):
        rl.log(make_log(model="gpt-4-with-a-reasonably-long-model-name"))

    rotated = tmp_path / "request_history.jsonl.1"
    assert rotated.exists(), "expected a rotated generation"
    assert log_file.stat().st_size < 512 * 4
    assert stat.S_IMODE(os.stat(rotated).st_mode) == 0o600


def test_rotation_disabled_when_max_bytes_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_REQUEST_LOG_MAX_BYTES", "0")
    log_file = tmp_path / "request_history.jsonl"
    rl = RequestLogger(log_file=str(log_file))
    for _ in range(20):
        rl.log(make_log())
    assert not (tmp_path / "request_history.jsonl.1").exists()


def test_admin_key_from_env_is_registered_by_request_logger(tmp_path, monkeypatch):
    """H6 end-to-end: the shapeless admin key from the environment must not
    reach the JSONL even when it appears somewhere the key-name filter
    does not cover (here, free text in the error field)."""
    admin_key = "zzz-operator-chosen-admin-secret-zzz"
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", admin_key)
    log_file = tmp_path / "request_history.jsonl"
    rl = RequestLogger(log_file=str(log_file))

    rl.log(make_log(error=f"upstream rejected admin credential {admin_key}"))

    raw = log_file.read_text(encoding="utf-8")
    assert admin_key not in raw
    assert REDACTED in raw
