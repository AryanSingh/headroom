from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_typescript_hosted_smoke_writes_redacted_json_and_markdown_evidence() -> None:
    script = (
        ROOT / "sdk" / "typescript" / "scripts" / "run-remote-hosted-smoke.mjs"
    ).read_text(encoding="utf-8")

    assert "remote-hosted-compression-smoke-typescript.json" in script
    assert "remote-hosted-compression-smoke-typescript.md" in script
    assert "writeFile(jsonOutput" in script
    assert "writeFile(markdownOutput" in script
    assert "API keys and payload bodies are intentionally excluded" in script
    assert "apiKey" not in script.split("const evidence", 1)[1]
