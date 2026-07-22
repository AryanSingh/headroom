from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT_DIR = ROOT / "docs" / "pilot"

REQUIRED_DOCS = {
    "environment-worksheet.md": ("CUTCTX_PROXY_API_KEY", "OpenAI", "Anthropic"),
    "onboarding-checklist.md": ("cutctx config-check", "cutctx mcp status"),
    "customer-acceptance-test.md": ("/readyz", "X-Cutctx-Proxy-Key", "rollback"),
    "support-and-escalation.md": ("Critical", "response target"),
    "incident-response.md": ("containment", "customer communication"),
    "backup-restore.md": ("integrity_check", "restore"),
    "upgrade-rollback.md": ("kubectl rollout undo", "previous image"),
    "license-billing-handoff.md": ("payment", "license", "redact"),
    "known-limitations.md": ("Claude Desktop", "Windows", "OpenAI", "Anthropic"),
}


def test_pilot_operating_kit_contains_required_contracts() -> None:
    for filename, needles in REQUIRED_DOCS.items():
        text = (PILOT_DIR / filename).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text


def test_pilot_index_links_each_required_document() -> None:
    index = (PILOT_DIR / "README.md").read_text(encoding="utf-8")
    for filename in REQUIRED_DOCS:
        assert f"]({filename})" in index


def test_acceptance_test_covers_supported_clients_and_removal() -> None:
    acceptance = (PILOT_DIR / "customer-acceptance-test.md").read_text(encoding="utf-8")

    for required in (
        "Codex",
        "Claude Code",
        "Claude Desktop",
        "OpenAI",
        "Anthropic",
        "cutctx mcp uninstall",
    ):
        assert required in acceptance
