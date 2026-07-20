"""Tests for the MCP compression gateway and Desktop config wrapping."""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path

import pytest

from cutctx.mcp_gateway import CompressedText, MCPGateway
from cutctx.mcp_registry.claude_desktop import (
    CONFIG_FILENAME,
    ClaudeDesktopRegistrar,
    _is_gateway_entry,
    _unwrap_entry,
    _wrap_entry,
)

# ----------------------------------------------------------------------
# Frame processing
# ----------------------------------------------------------------------

BIG_TEXT = "x" * 5000


def _fake_compress(content: str) -> CompressedText:
    return CompressedText(
        text="<compressed>", hash="abc123def456", original_tokens=1000, compressed_tokens=100
    )


def _gateway(**kwargs) -> MCPGateway:
    kwargs.setdefault("compress_fn", _fake_compress)
    return MCPGateway(["fake-server"], name="test", **kwargs)


def _tool_call(req_id, tool="search") -> bytes:
    return (
        json.dumps(
            {"jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": {"name": tool}}
        ).encode()
        + b"\n"
    )


def _tool_result(req_id, text) -> bytes:
    return (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        ).encode()
        + b"\n"
    )


def test_compresses_large_tool_result() -> None:
    gw = _gateway()
    gw.track_client_frame(_tool_call(1))
    out = json.loads(gw.process_upstream_frame(_tool_result(1, BIG_TEXT)))
    text = out["result"]["content"][0]["text"]
    assert text.startswith("<compressed>")
    assert "cutctx_retrieve hash=abc123def456" in text
    assert "search" in text  # tool name in the annotation


def test_small_results_pass_through_unchanged() -> None:
    gw = _gateway()
    gw.track_client_frame(_tool_call(1))
    raw = _tool_result(1, "tiny")
    assert gw.process_upstream_frame(raw) == raw


def test_non_tool_responses_pass_through() -> None:
    gw = _gateway()
    # initialize response — id never registered as a tools/call
    raw = json.dumps({"jsonrpc": "2.0", "id": 99, "result": {"capabilities": {}}}).encode() + b"\n"
    assert gw.process_upstream_frame(raw) == raw


def test_notifications_and_garbage_pass_through() -> None:
    gw = _gateway()
    notification = b'{"jsonrpc":"2.0","method":"notifications/progress"}\n'
    assert gw.process_upstream_frame(notification) == notification
    garbage = b"not json at all\n"
    assert gw.process_upstream_frame(garbage) == garbage
    gw.track_client_frame(garbage)  # must not raise


def test_error_responses_pass_through() -> None:
    gw = _gateway()
    gw.track_client_frame(_tool_call(1))
    raw = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "boom"}}).encode()
        + b"\n"
    )
    assert gw.process_upstream_frame(raw) == raw


def test_pending_id_consumed_once() -> None:
    gw = _gateway()
    gw.track_client_frame(_tool_call(7))
    first = gw.process_upstream_frame(_tool_result(7, BIG_TEXT))
    assert b"<compressed>" in first
    # A duplicate response with the same id is no longer treated as a tool call.
    raw = _tool_result(7, BIG_TEXT)
    assert gw.process_upstream_frame(raw) == raw


def test_compression_failure_forwards_original() -> None:
    def broken(content: str) -> CompressedText:
        raise RuntimeError("pipeline exploded")

    gw = _gateway(compress_fn=broken)
    gw.track_client_frame(_tool_call(1))
    raw = _tool_result(1, BIG_TEXT)
    assert gw.process_upstream_frame(raw) == raw


def test_compress_fn_declining_keeps_original() -> None:
    gw = _gateway(compress_fn=lambda _: None)
    gw.track_client_frame(_tool_call(1))
    raw = _tool_result(1, BIG_TEXT)
    assert gw.process_upstream_frame(raw) == raw


def test_string_ids_supported() -> None:
    gw = _gateway()
    gw.track_client_frame(_tool_call("req-abc"))
    out = gw.process_upstream_frame(_tool_result("req-abc", BIG_TEXT))
    assert b"<compressed>" in out


# ----------------------------------------------------------------------
# End-to-end relay over a real subprocess
# ----------------------------------------------------------------------

FAKE_SERVER = textwrap.dedent(
    """
    import json, sys
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("method") == "tools/call":
            result = {"content": [{"type": "text", "text": "y" * 5000}]}
        else:
            result = {"ok": True}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\\n")
        sys.stdout.flush()
    """
)


def test_relay_end_to_end(tmp_path: Path) -> None:
    server = tmp_path / "fake_server.py"
    server.write_text(FAKE_SERVER)

    async def scenario() -> list[dict]:
        gw = MCPGateway([sys.executable, str(server)], name="e2e", compress_fn=_fake_compress)
        proc = await asyncio.create_subprocess_exec(
            *gw._upstream_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        frames = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "big"}}
            ),
        ]
        responses = []
        for frame in frames:
            raw = frame.encode() + b"\n"
            gw.track_client_frame(raw)
            proc.stdin.write(raw)
            await proc.stdin.drain()
            line = await proc.stdout.readline()
            responses.append(json.loads(gw.process_upstream_frame(line)))
        proc.stdin.close()
        await proc.wait()
        return responses

    init_resp, tool_resp = asyncio.run(scenario())
    assert init_resp["result"] == {"ok": True}  # untouched
    text = tool_resp["result"]["content"][0]["text"]
    assert text.startswith("<compressed>")
    assert "hash=abc123def456" in text


# ----------------------------------------------------------------------
# Desktop config wrap / unwrap
# ----------------------------------------------------------------------


def _write_config(tmp_path: Path, servers: dict) -> Path:
    path = tmp_path / CONFIG_FILENAME
    path.write_text(json.dumps({"mcpServers": servers, "theme": "dark"}))
    return path


def test_wrap_and_unwrap_roundtrip(tmp_path: Path) -> None:
    servers = {
        "slack": {"command": "npx", "args": ["-y", "slack-mcp"], "env": {"TOKEN": "t"}},
        "cutctx": {"command": "/opt/bin/cutctx", "args": ["mcp", "serve"]},
        "remote": {"url": "https://example.com/mcp"},
    }
    path = _write_config(tmp_path, servers)
    reg = ClaudeDesktopRegistrar(config_dir=tmp_path)

    statuses = reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")
    assert statuses == {
        "slack": "wrapped",
        "cutctx": "skipped (cutctx)",
        "remote": "skipped (not stdio)",
    }
    data = json.loads(path.read_text())
    slack = data["mcpServers"]["slack"]
    assert slack["command"] == "/opt/bin/cutctx"
    assert slack["args"] == ["mcp", "gateway", "--name", "slack", "--", "npx", "-y", "slack-mcp"]
    assert slack["env"] == {"TOKEN": "t"}
    assert data["mcpServers"]["cutctx"]["args"] == ["mcp", "serve"]  # untouched
    assert data["theme"] == "dark"

    # Idempotent
    assert reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")["slack"] == "already"

    # Reversible
    assert reg.unwrap_gateway_servers() == ["slack"]
    data = json.loads(path.read_text())
    assert data["mcpServers"]["slack"] == {
        "command": "npx",
        "args": ["-y", "slack-mcp"],
        "env": {"TOKEN": "t"},
    }


def test_wrap_backs_up_config_before_editing(tmp_path: Path) -> None:
    path = _write_config(tmp_path, {"slack": {"command": "npx", "args": ["slack-mcp"]}})
    original = path.read_text()
    reg = ClaudeDesktopRegistrar(config_dir=tmp_path)

    reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")

    assert reg.last_backup_path is not None
    assert reg.last_backup_path.exists()
    # Backup holds the pre-edit content; live config was changed.
    assert reg.last_backup_path.read_text() == original
    assert path.read_text() != original


def test_wrap_no_backup_when_nothing_to_change(tmp_path: Path) -> None:
    # Only cutctx present → nothing wrapped → no backup churn.
    _write_config(tmp_path, {"cutctx": {"command": "/c", "args": ["mcp", "serve"]}})
    reg = ClaudeDesktopRegistrar(config_dir=tmp_path)
    reg.wrap_servers_with_gateway(cutctx_command="/c")
    assert reg.last_backup_path is None


def test_unwrap_noop_when_nothing_wrapped(tmp_path: Path) -> None:
    _write_config(tmp_path, {"slack": {"command": "npx", "args": ["slack-mcp"]}})
    reg = ClaudeDesktopRegistrar(config_dir=tmp_path)
    assert reg.unwrap_gateway_servers() == []


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"command": "cutctx", "args": ["mcp", "gateway", "--", "npx", "s"]}, True),
        ({"command": "cutctx", "args": ["mcp", "serve"]}, False),
        ({"command": "npx", "args": []}, False),
        ({"url": "https://x"}, False),
    ],
)
def test_is_gateway_entry(entry: dict, expected: bool) -> None:
    assert _is_gateway_entry(entry) is expected


def test_wrap_entry_without_args_or_env() -> None:
    wrapped = _wrap_entry({"command": "server-bin"}, "/bin/cutctx", "db")
    assert wrapped == {
        "command": "/bin/cutctx",
        "args": ["mcp", "gateway", "--name", "db", "--", "server-bin"],
    }
    assert _unwrap_entry(wrapped) == {"command": "server-bin"}


def test_unwrap_malformed_entry_returns_none() -> None:
    assert _unwrap_entry({"command": "cutctx", "args": ["mcp", "gateway"]}) is None
    assert _unwrap_entry({"command": "cutctx", "args": ["mcp", "gateway", "--"]}) is None
