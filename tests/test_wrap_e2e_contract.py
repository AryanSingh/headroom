"""Contracts required by the hermetic wrap E2E container."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAP_E2E_RUNNER = ROOT / "e2e" / "wrap" / "run.py"


def test_wrap_e2e_seeds_client_auth_without_requiring_an_os_keyring() -> None:
    content = WRAP_E2E_RUNNER.read_text(encoding="utf-8")

    assert '"CUTCTX_API_KEY": "test-client-key"' in content
    assert '"CUTCTX_ADMIN_API_KEY": "test-key"' in content
