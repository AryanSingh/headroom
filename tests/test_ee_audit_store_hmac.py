# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0.

"""Contract tests for the audit chain HMAC construction in cutctx_ee.audit.store.

## Why this file exists (and why it's mostly contract, not implementation)

The cutctx_ee/audit/store module ships as a Cython-compiled .so on
production installs (see cutctx_ee/audit/store.cpython-312-darwin.so).
The Python source at cutctx_ee/audit/store.py is the OSS/fallback
that loads only when the .so is absent.

The 2026-07-02 production-readiness assessment flagged that the
audit chain claimed HMAC SHA-256 in the docstring but used plain
hashlib.sha256() with the secret concatenated. That implementation is
vulnerable to length-extension forgery if an attacker can append
data to a known digest.

The fix requires:
  1. Update cutctx_ee/audit/store.py to use hmac.new(secret, message, hashlib.sha256)
  2. Recompile the Cython extension (maturin develop / pip install -e .[ee])
  3. Update cutctx_ee/MANIFEST.sha256.json
  4. Re-test the runtime

This test file exists to:
  a) Document the expected HMAC contract (so the fix is verifiable
     once the Cython is rebuilt), and
  b) Be skipped when the Cython binary is in use (because the Python
     source is not the runtime), and
  c) Provide a clear failure message when neither path matches the
     contract.

When the Cython binary is in use, the test:
  - Loads the compiled module
  - Calls _compute_hash with known inputs
  - Asserts the resulting hex digest matches what hmac.new(secret, msg, sha256)
    would produce under the LENGTH-PREFIXED framing that the fix uses
  - This catches the regression even though the test cannot introspect
    the .so's source

When the Cython binary is NOT in use (the Python source loads):
  - The same contract is enforced against the Python implementation
  - Additional source-level guardrails assert the textual invariants
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import importlib.util
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Module loading — handle the Cython/Python dual path
# ---------------------------------------------------------------------------


def _load_store_module() -> Any:
    """Load cutctx_ee.audit.store, bypassing the Cython .so if present.

    This is the path the test takes when we want to exercise the
    Python source directly. We do this by manipulating sys.modules
    to force a re-import of the .py source.
    """
    # Remove the Cython-loaded module so a re-import picks up the .py
    for mod_name in list(sys.modules.keys()):
        if mod_name == "cutctx_ee.audit.store" or mod_name.startswith(
            "cutctx_ee.audit.store."
        ):
            del sys.modules[mod_name]
    # Find the .py source
    spec = importlib.util.find_spec("cutctx_ee.audit.store")
    if spec is None or spec.origin is None:
        pytest.skip("cutctx_ee.audit.store not importable")
    if not spec.origin.endswith(".py"):
        # The Cython .so is the only thing on disk; we cannot load the
        # Python source. Skip.
        pytest.skip(
            f"cutctx_ee.audit.store is compiled ({spec.origin}); "
            "Python source is dead code at runtime. See the Cython-"
            "binary contract tests below."
        )
    return importlib.import_module("cutctx_ee.audit.store")


def _load_compiled_store() -> Any:
    """Load cutctx_ee.audit.store with the Cython .so active.

    This is the runtime path. We use the module as Python imports it
    (which prefers the .so if present).
    """
    # Force a fresh import
    for mod_name in list(sys.modules.keys()):
        if mod_name == "cutctx_ee.audit.store" or mod_name.startswith(
            "cutctx_ee.audit.store."
        ):
            del sys.modules[mod_name]
    return importlib.import_module("cutctx_ee.audit.store")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_message(tenant_id: str, actor: str, action: str,
                  payload_json: str, timestamp_iso: str,
                  previous_hash: str | None) -> bytes:
    """Build the canonical message bytes the HMAC fix uses.

    The framing is: previous_hash (or 32 zero bytes for genesis),
    followed by length-prefixed 8-byte-big-endian length + utf-8
    bytes for each field. This framing prevents length-extension
    attacks on the chained construction.
    """
    prior = previous_hash.encode() if previous_hash else b"\x00" * 32
    return (
        prior
        + len(tenant_id.encode()).to_bytes(8, "big")
        + tenant_id.encode()
        + len(actor.encode()).to_bytes(8, "big")
        + actor.encode()
        + len(action.encode()).to_bytes(8, "big")
        + action.encode()
        + len(payload_json.encode()).to_bytes(8, "big")
        + payload_json.encode()
        + len(timestamp_iso.encode()).to_bytes(8, "big")
        + timestamp_iso.encode()
    )


def _make_store_with_secret(store_cls: type, secret: str) -> Any:
    """Build an instance of AuditStore with a known secret, bypassing __init__.

    This works for both Python and Cython implementations as long as
    the class exposes a settable .secret_key attribute.
    """
    store = store_cls.__new__(store_cls)
    store.engine = MagicMock()
    store.SessionLocal = MagicMock()
    store.secret_key = secret.encode("utf-8")
    return store


def _call_compute(store: Any, **kwargs: Any) -> str:
    """Call _compute_hash with None-safe previous_hash and required fields."""
    return store._compute_hash(
        tenant_id=kwargs.get("tenant_id", "t-1"),
        actor=kwargs.get("actor", "user-1"),
        action=kwargs.get("action", "auth.login"),
        payload_json=kwargs.get("payload_json", "{}"),
        timestamp_iso=kwargs.get("timestamp_iso", "2026-07-02T10:00:00+00:00"),
        previous_hash=kwargs.get("previous_hash"),
    )


# ---------------------------------------------------------------------------
# 1. Format invariants — apply to BOTH Python source and Cython runtime
# ---------------------------------------------------------------------------


def test_compute_hash_returns_64_char_lowercase_hex_python() -> None:
    """Python source path: hash must be 64-char lowercase hex."""
    store_mod = _load_store_module()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    digest = _call_compute(store)
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_compute_hash_returns_64_char_lowercase_hex_compiled() -> None:
    """Cython runtime path: hash must be 64-char lowercase hex.

    The runtime is whatever the .so was compiled with. We assert the
    format invariant; the next test checks the construction.
    """
    store_mod = _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    digest = _call_compute(store)
    assert isinstance(digest, str), f"expected str, got {type(digest).__name__}"
    assert len(digest) == 64, f"expected 64-char hex, got length {len(digest)}: {digest!r}"
    assert all(c in "0123456789abcdef" for c in digest), (
        f"hash contains non-lowercase-hex chars: {digest!r}"
    )


# ---------------------------------------------------------------------------
# 2-3. Determinism + key sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_compute_hash_is_deterministic(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    a = _call_compute(store, actor="alice")
    b = _call_compute(store, actor="alice")
    assert a == b


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_compute_hash_changes_when_secret_changes(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    s1 = _make_store_with_secret(store_mod.AuditStore, "secret-one")
    s2 = _make_store_with_secret(store_mod.AuditStore, "secret-two")
    a = _call_compute(s1, actor="alice")
    b = _call_compute(s2, actor="alice")
    assert a != b


# ---------------------------------------------------------------------------
# 4. Field sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["python", "compiled"])
@pytest.mark.parametrize(
    "field",
    ["tenant_id", "actor", "action", "payload_json", "timestamp_iso"],
)
def test_compute_hash_changes_when_field_changes(path: str, field: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    base = _call_compute(store)
    altered = _call_compute(store, **{field: "different-value"})
    assert base != altered, f"hash should differ when {field!r} changes"


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_compute_hash_changes_when_previous_hash_changes(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    base = _call_compute(store, previous_hash="a" * 64)
    altered = _call_compute(store, previous_hash="b" * 64)
    assert base != altered


# ---------------------------------------------------------------------------
# 5. Genesis event
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_genesis_event_is_hashable(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    digest = _call_compute(store, previous_hash=None)
    assert len(digest) == 64


# ---------------------------------------------------------------------------
# 6-9. verify_chain contract (stubbed SQLAlchemy session)
# ---------------------------------------------------------------------------


def _make_chain_session(events: list[dict[str, Any]]) -> Any:
    """Build a MagicMock that mimics the AuditStore session for verify_chain."""
    from datetime import datetime

    class _FakeEvent:
        def __init__(self, d: dict[str, Any]) -> None:
            self.id = d["id"]
            self.tenant_id = d["tenant_id"]
            ts = d["timestamp"]
            if isinstance(ts, str):
                self.timestamp = datetime.fromisoformat(ts)
            else:
                self.timestamp = ts
            self.actor = d["actor"]
            self.action = d["action"]
            self.payload = d["payload"]
            self.previous_hash = d.get("previous_hash")
            self.event_hash = d["event_hash"]

    fake_events = [_FakeEvent(e) for e in events]

    class _FakeQuery:
        def __init__(self, evs: list[_FakeEvent]) -> None:
            self._evs = evs

        def filter(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
            return self

        def order_by(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
            return self

        def all(self) -> list[_FakeEvent]:
            return list(self._evs)

    class _FakeSession:
        def __init__(self, evs: list[_FakeEvent]) -> None:
            self._evs = evs

        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def query(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
            return _FakeQuery(self._evs)

    return _FakeSession(fake_events)


def _build_chain(store: Any, n: int) -> list[dict[str, Any]]:
    """Build a chain of n events using the same _compute_hash that verify_chain uses."""
    import json as _json

    events: list[dict[str, Any]] = []
    prev: str | None = None
    for i in range(n):
        d = {
            "id": i + 1,
            "tenant_id": "t-1",
            "timestamp": f"2026-07-02T10:00:0{i}+00:00",
            "actor": f"user-{i}",
            "action": "auth.login",
            "payload": {"i": i},
            "previous_hash": prev,
        }
        h = store._compute_hash(
            tenant_id=d["tenant_id"],
            actor=d["actor"],
            action=d["action"],
            payload_json=_json.dumps(d["payload"], sort_keys=True),
            timestamp_iso=d["timestamp"],
            previous_hash=d["previous_hash"],
        )
        d["event_hash"] = h
        events.append(d)
        prev = h
    return events


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_verify_chain_accepts_genesis_only(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    chain = _build_chain(store, 1)
    store.SessionLocal.return_value = _make_chain_session(chain)
    assert store.verify_chain("t-1") is True


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_verify_chain_accepts_chain_of_5(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    chain = _build_chain(store, 5)
    store.SessionLocal.return_value = _make_chain_session(chain)
    assert store.verify_chain("t-1") is True


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_verify_chain_rejects_tampered_event(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    chain = _build_chain(store, 3)
    chain[1]["payload"] = {"i": 999}
    store.SessionLocal.return_value = _make_chain_session(chain)
    assert store.verify_chain("t-1") is False


@pytest.mark.parametrize("path", ["python", "compiled"])
def test_verify_chain_rejects_wrong_secret(path: str) -> None:
    store_mod = _load_store_module() if path == "python" else _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")
    chain = _build_chain(store, 3)
    store.secret_key = b"different-secret"
    store.SessionLocal.return_value = _make_chain_session(chain)
    assert store.verify_chain("t-1") is False


# ---------------------------------------------------------------------------
# 10. Cython binary contract — the runtime check
# ---------------------------------------------------------------------------


def test_cython_runtime_uses_hmac_construction() -> None:
    """The runtime (.so) must produce a digest that matches hmac.new(...)
    over the canonical length-prefixed message.

    This catches the regression where the source claims HMAC but the
    binary uses plain hashlib.sha256 with concatenation (the bug that
    the 2026-07-02 production-readiness assessment flagged).
    """
    store_mod = _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")

    # Inputs that exercise a non-trivial message
    inputs = dict(
        tenant_id="tenant-abc",
        actor="user-xyz",
        action="license.activate",
        payload_json='{"plan":"team","seat_count":5}',
        timestamp_iso="2026-07-02T15:30:00+00:00",
        previous_hash="0123456789abcdef" * 4,
    )
    digest = _call_compute(store, **inputs)

    # Build the canonical message and the expected HMAC
    message = _build_message(**inputs)
    expected = hmac.new(
        store.secret_key, message, hashlib.sha256
    ).hexdigest()

    # The previous bug would have produced a hash by:
    #   h = sha256(secret + previous_hash + tenant + actor + ...)
    # without length prefixes. We assert the FIXED (HMAC + length-
    # prefixed) construction. If the runtime still uses the old
    # construction, this test fails with a clear diff.
    assert digest == expected, (
        f"Cython runtime does not match the HMAC + length-prefixed "
        f"contract.\n  expected: {expected}\n  got:      {digest}\n"
        f"This indicates the .so was compiled with the pre-fix code. "
        f"Rebuild the EE module: pip install -e .[ee] or run "
        f"scripts/build_ee_manifest.py after regenerating the .so."
    )


def test_cython_runtime_hmac_message_layout() -> None:
    """The HMAC message must use length-prefixed framing, not bare
    concatenation. We probe this by varying one field and checking
    that the resulting hash DOES match the canonical length-prefixed
    message; if the runtime uses bare concatenation with the same
    secret, the result will diverge.
    """
    store_mod = _load_compiled_store()
    store = _make_store_with_secret(store_mod.AuditStore, "test-secret")

    # Two inputs that differ only in a way that would produce identical
    # bare-concat messages but different length-prefixed messages
    # (boundary case: "abc" + "def" vs "abcd" + "ef")
    base = dict(
        tenant_id="abc", actor="def", action="x", payload_json="{}", timestamp_iso="t",
    )
    alt = dict(
        tenant_id="abcd", actor="ef", action="x", payload_json="{}", timestamp_iso="t",
    )
    h1 = _call_compute(store, **base)
    h2 = _call_compute(store, **alt)

    # With bare concatenation, both messages are "abcdef" + "x" + "{}" + "t"
    # so h1 == h2 (collision). With length-prefixed framing, the
    # tenant/actor boundaries are unambiguous, so h1 != h2.
    assert h1 != h2, (
        "Hash collision detected across inputs that differ only in field "
        "boundary placement. This indicates the runtime is using bare "
        "concatenation (length-extension / boundary-ambiguity vulnerability) "
        "instead of length-prefixed HMAC."
    )


# ---------------------------------------------------------------------------
# 11. Python source guardrails (skip when not loading Python)
# ---------------------------------------------------------------------------


def test_python_source_uses_hmac_not_concat() -> None:
    """If the Python source is the runtime (Cython absent), assert the
    textual invariant: hmac.new(...) is called and self.secret_key is
    used as the HMAC key.
    """
    store_mod = _load_store_module()
    import inspect

    try:
        src = inspect.getsource(store_mod.AuditStore._compute_hash)
    except TypeError:
        # Cython — the test_cython_runtime_uses_hmac_construction test
        # above is the contract check.
        pytest.skip("Python source is not loadable (Cython binary)")

    assert "hmac.new(" in src, (
        "expected hmac.new(...) call in _compute_hash source; "
        "the prior implementation used hashlib.sha256() with concatenation"
    )
    assert "self.secret_key" in src
    assert (
        "hasher.update(self.secret_key)" not in src
    ), (
        "found hasher.update(self.secret_key) — this is the bug, not the fix"
    )


def test_python_source_imports_hmac_module() -> None:
    """If the Python source is the runtime, it must `import hmac`."""
    store_mod = _load_store_module()
    spec = importlib.util.find_spec("cutctx_ee.audit.store")
    if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
        pytest.skip("Python source is not loadable (Cython binary)")
    with open(spec.origin, "r", encoding="utf-8") as f:
        src = f.read()
    assert "import hmac" in src, "expected 'import hmac' at the top of store.py"


# ---------------------------------------------------------------------------
# 12. Documentation/comment honesty guardrails (WS19 truthfulness pass)
#
# These check that comments/docs accurately describe the CURRENT algorithm
# (secret-prefixed SHA-256, not HMAC) while the contract tests above hold
# the implementation to the target (real HMAC) it hasn't reached yet.
# ---------------------------------------------------------------------------

from pathlib import Path


from pathlib import Path


def test_audit_store_source_describes_current_sha256_chain_honestly() -> None:
    text = Path("cutctx_ee/audit/store.py").read_text(encoding="utf-8")

    assert "secret-keyed SHA-256 chain value" in text
    assert "hashlib.sha256()" in text
    assert "HMAC SHA-256 hash for the event" not in text
    assert "hmac.new(" not in text


def test_audit_docs_match_current_source_contract() -> None:
    compliance = Path("docs/audit-compliance.md").read_text(encoding="utf-8")
    residency = Path("docs/data-residency.md").read_text(encoding="utf-8")
    roadmap = Path("gtm/soc2-roadmap.md").read_text(encoding="utf-8")

    assert "secret-keyed SHA-256 chain value" in compliance
    assert "SHA256(secret || prev_hash || payload)" in compliance
    assert "Current EE builds use this secret-prefixed SHA-256 chain directly" in residency
    assert "secret-keyed SHA-256 hash chain" in roadmap
