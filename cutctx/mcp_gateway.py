"""Cutctx MCP gateway: a transparent stdio proxy that compresses tool results.

Some MCP hosts (most notably the Claude Desktop app) run against a hosted
model endpoint that cannot be repointed at ``cutctx proxy``. But every MCP
server such a host launches comes from a config entry we control. The gateway
interposes at the *MCP layer* instead of the *model layer*::

    host (Claude Desktop)
      └─ spawns:  cutctx mcp gateway --name slack -- npx slack-mcp
                    └─ spawns:  npx slack-mcp

The gateway relays JSON-RPC frames verbatim in both directions, except for
``tools/call`` responses, whose text content it compresses before the host
adds it to model context. Originals are stored in the shared compression
store so the model can recover them via ``cutctx_retrieve`` (available when
the cutctx MCP server is also installed).

Framing: the MCP stdio transport is newline-delimited JSON. Frames we cannot
parse are forwarded untouched — the gateway must never break a session it
cannot improve.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: Below this size, compression overhead isn't worth it.
DEFAULT_MIN_CHARS = 2000

#: Keep originals retrievable for a session.
GATEWAY_TTL_SECONDS = 3600

#: Forwarded-frame read limit — tool results can be megabytes.
STREAM_LIMIT = 32 * 1024 * 1024

#: Require at least this relative saving to swap in the compressed text.
MIN_SAVINGS_RATIO = 0.10

#: Cap on in-flight tool-call ids we remember. A well-behaved server answers
#: every request, but a crashing or buggy one may not — without a bound the
#: map would leak one entry per unanswered call for the life of the process.
MAX_PENDING_TOOL_CALLS = 4096


@dataclass
class CompressedText:
    """Outcome of compressing one text block."""

    text: str
    hash: str
    original_tokens: int
    compressed_tokens: int


def _default_compress(content: str) -> CompressedText | None:
    """Compress via the Cutctx pipeline and store the original.

    Returns ``None`` when compression is not worthwhile. Heavy imports are
    deferred so the gateway starts fast and tests can inject a fake.
    """
    from cutctx.cache.compression_store import get_compression_store
    from cutctx.compress import compress

    result = compress([{"role": "tool", "content": content}], model="claude-sonnet-4-5-20250929")
    compressed = result.messages[0].get("content", content)
    if not isinstance(compressed, str):
        compressed = json.dumps(compressed)
    if result.tokens_before <= 0:
        return None
    saved = result.tokens_before - result.tokens_after
    if saved / result.tokens_before < MIN_SAVINGS_RATIO:
        return None

    hash_key = get_compression_store().store(
        original=content,
        compressed=compressed,
        original_tokens=result.tokens_before,
        compressed_tokens=result.tokens_after,
        compression_strategy="mcp_gateway",
        ttl=GATEWAY_TTL_SECONDS,
    )
    return CompressedText(
        text=compressed,
        hash=hash_key,
        original_tokens=result.tokens_before,
        compressed_tokens=result.tokens_after,
    )


class MCPGateway:
    """Bidirectional stdio relay with tool-result compression.

    Args:
        upstream_cmd: Command + args of the wrapped MCP server.
        name: Label used in log lines and annotations.
        min_chars: Only text blocks at least this long are compressed.
        compress_fn: Injectable compressor (test seam). Takes the text,
            returns :class:`CompressedText` or ``None`` to keep the original.
    """

    def __init__(
        self,
        upstream_cmd: list[str],
        *,
        name: str | None = None,
        min_chars: int = DEFAULT_MIN_CHARS,
        compress_fn: Callable[[str], CompressedText | None] | None = None,
    ) -> None:
        if not upstream_cmd:
            raise ValueError("upstream_cmd must not be empty")
        self._upstream_cmd = upstream_cmd
        self._name = name or upstream_cmd[0]
        self._min_chars = min_chars
        self._compress_fn = compress_fn or _default_compress
        #: request id -> tool name, for in-flight ``tools/call`` requests.
        self._pending_tool_calls: dict[Any, str] = {}
        #: Set once ``run()`` is active; lets callers request a clean shutdown.
        self._stop: asyncio.Event | None = None

    def request_stop(self) -> None:
        """Ask an active :meth:`run` loop to shut down cleanly (idempotent)."""
        if self._stop is not None:
            self._stop.set()

    # ------------------------------------------------------------------
    # Frame processing (pure-ish, unit-testable)
    # ------------------------------------------------------------------

    def track_client_frame(self, raw: bytes) -> None:
        """Inspect a client→server frame; remember ``tools/call`` ids."""
        try:
            msg = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(msg, dict) or "id" not in msg:
            return
        if msg.get("method") == "tools/call":
            params = msg.get("params")
            tool = params.get("name", "?") if isinstance(params, dict) else "?"
            # Bound the map: evict the oldest id if we're at capacity. dicts
            # preserve insertion order, so the first key is the oldest.
            if len(self._pending_tool_calls) >= MAX_PENDING_TOOL_CALLS:
                self._pending_tool_calls.pop(next(iter(self._pending_tool_calls)), None)
            self._pending_tool_calls[msg["id"]] = tool

    def process_upstream_frame(self, raw: bytes) -> bytes:
        """Rewrite a server→client frame if it answers a ``tools/call``.

        Anything unparseable or uninteresting is returned unchanged. Note that
        JSON-RPC *batch* frames (a top-level array) fall through the
        ``isinstance(msg, dict)`` guard below and are forwarded verbatim — the
        gateway does not compress batched results, it just never corrupts them.
        """
        try:
            msg = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return raw
        if not isinstance(msg, dict) or "id" not in msg:
            return raw

        tool = self._pending_tool_calls.pop(msg["id"], None)
        if tool is None or "result" not in msg:
            return raw

        result = msg.get("result")
        if not isinstance(result, dict):
            return raw
        content = result.get("content")
        if not isinstance(content, list):
            return raw

        changed = False
        for item in content:
            if not (isinstance(item, dict) and item.get("type") == "text"):
                continue
            text = item.get("text")
            if not isinstance(text, str) or len(text) < self._min_chars:
                continue
            compressed = self._safe_compress(text)
            if compressed is None:
                continue
            item["text"] = (
                f"{compressed.text}\n\n"
                f"[cutctx: compressed {compressed.original_tokens}→"
                f"{compressed.compressed_tokens} tokens. Full {tool} output: "
                f"cutctx_retrieve hash={compressed.hash}]"
            )
            changed = True
            self._log(
                f"{tool}: {compressed.original_tokens} → "
                f"{compressed.compressed_tokens} tokens (hash={compressed.hash[:12]})"
            )

        if not changed:
            return raw
        return json.dumps(msg, separators=(",", ":")).encode() + b"\n"

    def _safe_compress(self, text: str) -> CompressedText | None:
        """Compression must never take down the relay."""
        try:
            return self._compress_fn(text)
        except Exception as exc:  # noqa: BLE001 — deliberate catch-all
            self._log(f"compression failed, forwarding original: {exc}")
            return None

    def _log(self, message: str) -> None:
        print(f"[cutctx gateway:{self._name}] {message}", file=sys.stderr, flush=True)

    # ------------------------------------------------------------------
    # Relay loops
    # ------------------------------------------------------------------

    def _spawn_stdin_pump(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[bytes],
        stdin: Any,
    ) -> None:
        """Feed ``stdin`` into ``queue`` from a daemon thread.

        ``loop.connect_read_pipe`` is unavailable on Windows' Proactor loop and
        flaky when stdin is a regular file, so we read with a blocking thread
        that works on every platform. The thread is a daemon so a stuck
        ``readline`` can never block interpreter shutdown. An empty bytes value
        signals EOF.
        """

        def reader() -> None:
            while True:
                try:
                    line = stdin.readline()
                except (ValueError, OSError):
                    line = b""  # stdin closed under us
                loop.call_soon_threadsafe(queue.put_nowait, line)
                if not line:
                    break

        threading.Thread(target=reader, name="cutctx-gw-stdin", daemon=True).start()

    async def _terminate(self, proc: asyncio.subprocess.Process) -> None:
        """Stop the child: SIGTERM, then SIGKILL after a short grace period."""
        if proc.returncode is not None:
            return
        try:
            proc.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()

    async def run(self, *, stdin: Any = None, stdout: Any = None) -> int:
        """Relay until the upstream server exits or we're asked to stop.

        ``stdin``/``stdout`` default to the process's real binary streams;
        tests inject pipes. Returns the upstream exit code. Guarantees: the
        child is always reaped (terminated then killed on timeout), a stop
        signal (SIGINT/SIGTERM) unwinds cleanly, and neither direction can
        wedge the other — when the server closes its stdout, we stop pumping
        stdin.
        """
        in_stream = stdin if stdin is not None else sys.stdin.buffer
        out_stream = stdout if stdout is not None else sys.stdout.buffer

        proc = await asyncio.create_subprocess_exec(
            *self._upstream_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,  # inherit — upstream logs stay visible to the host
            limit=STREAM_LIMIT,
        )
        assert proc.stdin is not None and proc.stdout is not None

        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        self._stop = stop
        for sig in (signal.SIGINT, signal.SIGTERM):
            # add_signal_handler is POSIX-only and requires the main thread.
            with contextlib.suppress(NotImplementedError, ValueError, RuntimeError):
                loop.add_signal_handler(sig, stop.set)

        queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._spawn_stdin_pump(loop, queue, in_stream)

        async def client_to_upstream() -> None:
            try:
                while True:
                    line = await queue.get()
                    if not line:
                        break  # host closed stdin
                    self.track_client_frame(line)
                    proc.stdin.write(line)
                    await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass  # child went away; upstream loop will end the session
            finally:
                if proc.stdin.can_write_eof():
                    with contextlib.suppress(OSError):
                        proc.stdin.write_eof()

        async def upstream_to_client() -> None:
            out = out_stream
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break  # server closed stdout — it's exiting
                # Compression may be slow; run off the event loop.
                frame = await loop.run_in_executor(None, self.process_upstream_frame, line)
                out.write(frame)
                out.flush()

        client_task = asyncio.create_task(client_to_upstream())
        upstream_task = asyncio.create_task(upstream_to_client())
        stop_task = asyncio.create_task(stop.wait())

        # Finish when the server closes stdout OR we're signalled to stop.
        await asyncio.wait({upstream_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if stop.is_set():
            self._log("stop requested; shutting down")

        await self._terminate(proc)
        for task in (client_task, upstream_task, stop_task):
            task.cancel()
        await asyncio.gather(client_task, upstream_task, stop_task, return_exceptions=True)
        return await proc.wait()


async def run_gateway(
    upstream_cmd: list[str],
    *,
    name: str | None = None,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> int:
    """Entry point used by ``cutctx mcp gateway``."""
    gateway = MCPGateway(upstream_cmd, name=name, min_chars=min_chars)
    return await gateway.run()
