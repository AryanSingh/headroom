"""Lifecycle tests for MCPGateway.run() — the async relay loop.

These drive a real subprocess through injected stdin/stdout pipes, covering
the paths unit tests of ``process_upstream_frame`` cannot: process spawn,
bidirectional relay, EOF-driven shutdown, upstream crash, and child reaping.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

from cutctx.mcp_gateway import CompressedText, MCPGateway

# Echoes {} to non-tool calls, a 5 KB blob to tools/call, and exits 0 when
# its stdin closes (the normal MCP shutdown signal).
ECHO_SERVER = textwrap.dedent(
    """
    import json, sys
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        if msg.get("method") == "tools/call":
            result = {"content": [{"type": "text", "text": "z" * 5000}]}
        else:
            result = {}
        if "id" in msg:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\\n")
            sys.stdout.flush()
    """
)

# Exits immediately with a non-zero code without reading anything.
CRASH_SERVER = "import sys; sys.exit(3)"

# Ignores SIGTERM and never exits on its own — used to prove we escalate to kill.
HANG_SERVER = textwrap.dedent(
    """
    import signal, time
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(0.5)
    """
)


class _Collector:
    """Minimal binary sink with the write/flush surface run() expects."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def write(self, b: bytes) -> None:
        self.buf.extend(b)

    def flush(self) -> None:
        pass

    def frames(self) -> list[dict]:
        return [json.loads(line) for line in bytes(self.buf).splitlines() if line.strip()]


def _fake_compress(_: str) -> CompressedText:
    return CompressedText(text="<z>", hash="deadbeefcafe0000", original_tokens=1500, compressed_tokens=90)


def _server(tmp_path: Path, body: str, name: str = "srv.py") -> str:
    path = tmp_path / name
    path.write_text(body)
    return str(path)


async def _drive(gateway: MCPGateway, inputs: list[bytes], *, timeout: float = 10.0) -> tuple[int, _Collector]:
    """Run the gateway, feed ``inputs``, then close stdin and await exit."""
    r_fd, w_fd = os.pipe()
    stdin = os.fdopen(r_fd, "rb", buffering=0)
    out = _Collector()
    run_task = asyncio.create_task(gateway.run(stdin=stdin, stdout=out))

    writer = os.fdopen(w_fd, "wb", buffering=0)
    for frame in inputs:
        writer.write(frame)
    writer.close()  # EOF → triggers clean shutdown

    code = await asyncio.wait_for(run_task, timeout=timeout)
    return code, out


def _frame(obj: dict) -> bytes:
    return json.dumps(obj).encode() + b"\n"


def test_relay_compresses_and_exits_cleanly(tmp_path: Path) -> None:
    gw = MCPGateway([sys.executable, _server(tmp_path, ECHO_SERVER)], compress_fn=_fake_compress)

    async def scenario() -> tuple[int, _Collector]:
        return await _drive(
            gw,
            [
                _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                _frame({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "big"}}),
            ],
        )

    code, out = asyncio.run(scenario())
    assert code == 0
    frames = out.frames()
    by_id = {f["id"]: f for f in frames}
    assert by_id[1]["result"] == {}  # non-tool response untouched
    text = by_id[2]["result"]["content"][0]["text"]
    assert text.startswith("<z>")
    assert "hash=deadbeefcafe0000" in text


def test_upstream_crash_returns_exit_code(tmp_path: Path) -> None:
    gw = MCPGateway([sys.executable, _server(tmp_path, CRASH_SERVER)], compress_fn=_fake_compress)

    async def scenario() -> int:
        # No input needed; the server exits on its own. run() must not hang.
        r_fd, w_fd = os.pipe()
        stdin = os.fdopen(r_fd, "rb", buffering=0)
        try:
            return await asyncio.wait_for(gw.run(stdin=stdin, stdout=_Collector()), timeout=10.0)
        finally:
            os.close(w_fd)

    assert asyncio.run(scenario()) == 3


def test_stdin_eof_triggers_shutdown(tmp_path: Path) -> None:
    # No frames at all: closing stdin immediately must still bring the session
    # down (server sees EOF, exits 0), and run() must return without hanging.
    gw = MCPGateway([sys.executable, _server(tmp_path, ECHO_SERVER)], compress_fn=_fake_compress)
    code, _ = asyncio.run(_drive(gw, []))
    assert code == 0


def test_hanging_child_is_killed(tmp_path: Path) -> None:
    # Server ignores SIGTERM and never exits; a stop signal must still let
    # run() return by escalating to SIGKILL within the grace window.
    gw = MCPGateway([sys.executable, _server(tmp_path, HANG_SERVER)], compress_fn=_fake_compress)

    async def scenario() -> int:
        r_fd, w_fd = os.pipe()
        stdin = os.fdopen(r_fd, "rb", buffering=0)
        run_task = asyncio.create_task(gw.run(stdin=stdin, stdout=_Collector()))
        await asyncio.sleep(0.3)  # let it spin up
        gw.request_stop()  # simulate a delivered stop signal
        try:
            return await asyncio.wait_for(run_task, timeout=15.0)
        finally:
            os.close(w_fd)

    # Killed child exits with a negative signal code; the point is run() returns.
    code = asyncio.run(scenario())
    assert code != 0


def test_empty_command_rejected() -> None:
    with pytest.raises(ValueError):
        MCPGateway([])
