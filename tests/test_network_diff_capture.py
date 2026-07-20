from __future__ import annotations

import base64
import importlib.util
import json
import sys
import types
from pathlib import Path

from click.testing import CliRunner

from cutctx.capture.network_diff import (
    compare_captures,
    exchange_from_record,
    load_capture_file,
    render_markdown_report,
)
from cutctx.cli.main import main


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def _body(payload: dict[str, object]) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def test_network_diff_redacts_and_reports_body_json_deltas(tmp_path: Path) -> None:
    direct_path = tmp_path / "direct.jsonl"
    cutctx_path = tmp_path / "cutctx.jsonl"
    _write_jsonl(
        direct_path,
        [
            {
                "lane": "direct",
                "method": "POST",
                "url": "https://api.anthropic.com/v1/messages?api_key=secret",
                "request_headers": {
                    "authorization": "Bearer secret",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "deferred-tools",
                },
                "request_body_b64": _body(
                    {"model": "claude", "messages": [{"content": "hi"}], "tools": []}
                ),
                "response_status": 200,
            }
        ],
    )
    _write_jsonl(
        cutctx_path,
        [
            {
                "lane": "cutctx",
                "method": "POST",
                "url": "https://api.anthropic.com/v1/messages?api_key=secret",
                "request_headers": {
                    "authorization": "Bearer other",
                    "anthropic-version": "2023-06-01",
                    "x-cutctx-mode": "optimize",
                },
                "request_body_b64": _body(
                    {
                        "model": "claude",
                        "messages": [{"content": "hello"}],
                        "metadata": {},
                        "tools": [{"name": "ctx_execute", "input_schema": {"type": "object"}}],
                    }
                ),
                "response_status": 200,
            }
        ],
    )

    direct = load_capture_file(direct_path, fallback_lane="direct")
    cutctx = load_capture_file(cutctx_path, fallback_lane="cutctx")

    assert direct[0].url == "https://api.anthropic.com/v1/messages?api_key=%3Credacted%3E"
    assert direct[0].request_headers["authorization"] == "<redacted>"

    diff = compare_captures(direct, cutctx)
    assert diff.direct_count == 1
    assert diff.cutctx_count == 1
    paired = diff.paired[0]
    assert paired["headers"]["only_cutctx"] == ["x-cutctx-mode"]
    assert "$.metadata" in paired["json"]["only_cutctx"]
    assert "$.messages[0].content" in paired["json"]["changed"]
    assert paired["anthropic"]["direct"]["tools_count"] == 0
    assert paired["anthropic"]["cutctx"]["tools_count"] == 1

    markdown = render_markdown_report(diff)
    assert "Differential Network Capture Report" in markdown
    assert "POST api.anthropic.com/v1/messages?api_key=%3Credacted%3E" in markdown
    assert "tools=0->1" in markdown


def test_network_diff_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    direct_path = tmp_path / "direct.jsonl"
    cutctx_path = tmp_path / "cutctx.jsonl"
    markdown_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"
    record = {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "request_headers": {},
        "request_body_b64": _body({"model": "claude"}),
        "response_status": 200,
    }
    _write_jsonl(direct_path, [record])
    _write_jsonl(cutctx_path, [record])

    result = CliRunner().invoke(
        main,
        [
            "capture",
            "network-diff",
            "--direct",
            str(direct_path),
            "--cutctx",
            str(cutctx_path),
            "--output",
            str(markdown_path),
            "--json-output",
            str(json_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Wrote Markdown report" in result.output
    assert "Differential Network Capture Report" in markdown_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["direct_count"] == 1
    assert payload["cutctx_count"] == 1


def test_exchange_from_record_never_exposes_raw_request_content() -> None:
    record = {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "request_headers": {"x-api-key": "sk-ant-secret"},
        "request_json": {
            "model": "claude-test",
            "messages": [
                {
                    "role": "user",
                    "content": "private prompt from person@example.com at /Users/alice/repo",
                }
            ],
            "metadata": {"user_id": "person@example.com"},
        },
        "request_body": '{"messages":[{"content":"private prompt"}]}',
    }

    exchange = exchange_from_record(record, fallback_lane="direct", sequence=1)

    serialized = json.dumps(exchange.request_json, sort_keys=True)
    assert "private prompt" not in serialized
    assert "person@example.com" not in serialized
    assert "/Users/alice" not in serialized
    assert exchange.request_headers["x-api-key"] == "<redacted>"
    assert exchange.request_body_preview is None


def test_mitm_addon_sanitizes_json_and_never_persists_raw_body() -> None:
    addon_path = (
        Path(__file__).parents[1] / "docker" / "differential-network-capture" / "mitm_capture.py"
    )
    source = addon_path.read_text(encoding="utf-8")
    assert '"request_body_b64"' not in source

    fake_http = types.SimpleNamespace(Headers=object, HTTPFlow=object)
    fake_mitm = types.ModuleType("mitmproxy")
    fake_mitm.http = fake_http
    previous = sys.modules.get("mitmproxy")
    sys.modules["mitmproxy"] = fake_mitm
    try:
        spec = importlib.util.spec_from_file_location("test_mitm_capture", addon_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        private_image = base64.b64encode(b"private image bytes").decode()
        sanitized = module._sanitize_json(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "private prompt at person@example.com in /Users/alice/repo",
                    }
                ],
                "metadata": {"user_id": "person@example.com"},
                "tools": [{"name": "fixture_tool", "description": "private description"}],
                "image": {
                    "source": {"type": "base64", "data": private_image},
                    "image_url": f"data:image/png;base64,{private_image}",
                },
            }
        )
    finally:
        if previous is None:
            sys.modules.pop("mitmproxy", None)
        else:
            sys.modules["mitmproxy"] = previous

    serialized = json.dumps(sanitized, sort_keys=True)
    assert "private prompt" not in serialized
    assert "person@example.com" not in serialized
    assert "/Users/alice" not in serialized
    assert private_image not in serialized
    assert sanitized["tools"][0]["name"] == "fixture_tool"
