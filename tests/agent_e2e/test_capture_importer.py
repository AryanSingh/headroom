from __future__ import annotations

import json
import stat
from pathlib import Path

from cutctx.capture.agent_fixture import import_capture_file
from cutctx.capture.fixture_safety import assert_fixture_safe


def test_importer_accepts_mitm_jsonl_sanitizes_and_deletes_private_source(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(mode=0o700)
    raw = raw_dir / "claude.jsonl"
    raw.write_text(
        json.dumps(
            {
                "lane": "direct",
                "method": "POST",
                "url": "https://api.anthropic.com/v1/messages?api_key=sk-ant-private",
                "request_headers": {"x-api-key": "sk-ant-private"},
                "request_json": {
                    "model": "claude-test",
                    "messages": [{"role": "user", "content": "private prompt"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    raw.chmod(0o600)
    output = tmp_path / "sanitized.json"

    records = import_capture_file(raw, output=output, delete_source=True)

    assert not raw.exists()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert records[0]["request_headers"]["x-api-key"] == "<redacted>"
    assert "private prompt" not in output.read_text(encoding="utf-8")
    assert_fixture_safe(json.loads(output.read_text(encoding="utf-8")))


def test_importer_accepts_codex_wire_and_debug_400_json(tmp_path: Path) -> None:
    for name, payload in {
        "wire.json": {
            "headers": {"authorization": "Bearer sk-private"},
            "body": {"model": "gpt-5.4", "input": "private prompt", "stream": True},
        },
        "debug.json": {
            "request_headers": {"authorization": "Bearer sk-ant-private"},
            "request_body": {
                "model": "claude-test",
                "messages": [{"role": "user", "content": "private prompt"}],
            },
            "status_code": 400,
        },
    }.items():
        source = tmp_path / name
        source.write_text(json.dumps(payload), encoding="utf-8")
        records = import_capture_file(source)
        assert len(records) == 1
        assert_fixture_safe(records)
