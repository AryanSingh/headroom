"""Request logger for the Cutctx proxy.

Logs requests to an in-memory deque and optionally to a JSONL file.

Extracted from server.py for maintainability.

Phase G PR-G3 (P4-45): base64-encoded image payloads in the
``request_messages`` / ``response_content`` are redacted before
write to keep request logs small. Multi-MB base64 strings would
otherwise saturate the JSONL log and the in-memory deque.

Remediation (M2, M5): the redactor now ONLY fires inside known
image-bearing JSON paths or against strings that carry an explicit
``data:image/...;base64,`` URL prefix. The earlier "density
heuristic" over-fired on encrypted blobs, signed tokens, minified
JSON, and tool outputs. The replacement placeholder now reports
the UTF-8 byte length under a ``bytes=`` label (was character
length; for the ASCII base64 alphabet the two happen to coincide
but the label is now accurate for any future Unicode payload).
"""

from __future__ import annotations

import json
import logging
import sys
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory.tracker import ComponentStats

from cutctx.proxy.models import RequestLog

logger = logging.getLogger(__name__)

# Phase G PR-G3 — base64 redaction threshold (P4-45).
#
# Anthropic image blocks carry base64-encoded JPEGs/PNGs in
# ``source.data``; OpenAI's vision shape carries them in
# ``image_url.url`` as a ``data:image/...;base64,<payload>`` URL.
# The threshold gates "real image payload" against short base64
# strings (which can appear in arguments, signatures, etc.).
IMAGE_BASE64_REDACT_THRESHOLD_BYTES = 1024

# Phase G PR-G3 — replacement-marker format. Operators can grep the
# JSONL for ``<image:base64-redacted`` to count the redactions; the
# byte count keeps cost attribution honest even after redaction.
# M5: ``bytes=`` is the UTF-8 byte length, not the character count.
IMAGE_BASE64_REPLACEMENT_TEMPLATE = "<image:base64-redacted bytes={n}>"

# M2: JSON field names that carry image payloads in either the
# Anthropic or OpenAI shapes. Strings reached via one of these key
# names (at any depth) are eligible for the redaction heuristic.
# Anything OUTSIDE these paths is left untouched even if it looks
# base64-shaped — encrypted blobs, signed tokens, minified JSON,
# tool outputs all live elsewhere and stay verbatim.
IMAGE_BEARING_FIELD_NAMES: frozenset[str] = frozenset(
    {
        # Anthropic image-block shape: ``{"type":"image","source":{"type":"base64","data":"..."}}``.
        "data",
        # OpenAI vision shape: ``{"type":"image_url","image_url":{"url":"data:image/..."}}``.
        "url",
        # OpenAI Responses input_image: ``{"type":"input_image","image_url":"..."}``
        # — string-valued directly under the key (not nested).
        "image_url",
        # Some SDKs put the URL under ``image`` directly. Tolerated.
        "image",
        # Anthropic vision blocks sometimes wrap under ``source.data``;
        # ``source`` is a container, not a string field, so it doesn't
        # need to be in this set, but the data string itself is keyed
        # by ``data`` (already above).
    }
)

# M2: explicit data-URL MIME prefix. A string starting with this
# prefix is always treated as an image payload, regardless of where
# it lives in the JSON — operators occasionally embed data URLs in
# arbitrary fields and we want those redacted to keep logs small.
_DATA_IMAGE_URL_PREFIX = "data:image/"


# Constants for log redaction counter export (Prometheus). The
# Python proxy's ``/metrics`` exporter surfaces
# ``proxy_image_generation_call_log_redacted_total`` from this
# module-level counter. C3 remediation: the Rust proxy previously
# held a dead counter; that's been removed in favour of this
# Python-side counter, which is the natural owner.
_redactions_total: int = 0
_redactions_lock = Lock()


def redactions_total() -> int:
    """Return the running count of base64 redactions performed.

    Exposed for unit tests, the legacy Python ``/stats`` endpoint,
    and the Prometheus exporter
    (``proxy_image_generation_call_log_redacted_total``).
    """
    with _redactions_lock:
        return _redactions_total


def _is_base64_image_payload(value: str) -> bool:
    """Return True if ``value`` is an over-threshold base64 image.

    Per M2 remediation the prior bare-base64 density heuristic
    over-fired on non-image content (encrypted blobs, signed
    tokens, minified JSON, tool outputs). We now only consider a
    string an image payload when EITHER:

    1. It starts with ``data:image/`` (an explicit data URL),
       OR
    2. The caller has already established the string lives inside
       an image-bearing JSON path (see ``IMAGE_BEARING_FIELD_NAMES``)
       AND the string itself is over the byte threshold.

    Case (2) is decided by the caller (``_redact_value``) which
    threads ``in_image_path`` through the recursion; this helper
    handles case (1) on its own.
    """
    if not isinstance(value, str):
        return False
    if len(value) < IMAGE_BASE64_REDACT_THRESHOLD_BYTES:
        return False
    return value.startswith(_DATA_IMAGE_URL_PREFIX)


def _redact_value(
    value: Any,
    *,
    in_image_path: bool = False,
    local_counter: list[int] | None = None,
) -> Any:
    """Recursively redact base64-image payloads in a JSON-ish value.

    Returns a new structure with any over-threshold base64 string
    replaced by the placeholder. Non-string, non-container values
    pass through unchanged.

    ``in_image_path`` is True when the caller reached this value
    via one of the ``IMAGE_BEARING_FIELD_NAMES`` keys; once inside
    an image-bearing field, any over-threshold string is treated
    as an image payload (M2: prevents redaction of unrelated
    base64-shaped content outside known image fields).
    """
    global _redactions_total
    if isinstance(value, str):
        # Always-redact: explicit data URL, regardless of path.
        # Also redact when the caller signalled image-bearing path
        # AND the string is over threshold (no density check — the
        # path tells us it's an image).
        should_redact = _is_base64_image_payload(value) or (
            in_image_path and len(value) >= IMAGE_BASE64_REDACT_THRESHOLD_BYTES
        )
        if should_redact:
            with _redactions_lock:
                _redactions_total += 1
            if local_counter is not None:
                local_counter[0] += 1
            byte_len = len(value.encode("utf-8"))
            return IMAGE_BASE64_REPLACEMENT_TEMPLATE.format(n=byte_len)
        return value
    if isinstance(value, Mapping):
        return {
            k: _redact_value(
                v,
                in_image_path=(k in IMAGE_BEARING_FIELD_NAMES),
                local_counter=local_counter,
            )
            for k, v in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            _redact_value(
                item,
                in_image_path=in_image_path,
                local_counter=local_counter,
            )
            for item in value
        ]
    return value


def redact_image_base64(payload: Any) -> Any:
    """Public entry point for base64-image redaction.

    Walks ``payload`` (a dict, list, or string) and replaces any
    over-threshold base64 string with a size-only placeholder.
    Idempotent — applying twice yields the same structure.
    """
    redacted, _count = redact_image_base64_with_count(payload)
    return redacted


def redact_image_base64_with_count(payload: Any) -> tuple[Any, int]:
    """Redact one payload and return its per-entry redaction count."""

    counter = [0]
    redacted = _redact_value(
        payload,
        in_image_path=False,
        local_counter=counter,
    )
    return redacted, counter[0]


def _tail_lines(path: Path, n: int, chunk_size: int = 65_536) -> list[bytes]:
    """Return up to the last ``n`` non-empty lines of ``path``.

    Reads backwards in chunks so the cost is bounded by ``n`` (usually one
    chunk read) rather than growing with total file size — this is what
    lets ``get_recent`` stay cheap on a long-lived, multi-process-shared
    JSONL log that keeps growing.
    """
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            pos = f.tell()
            buffer = b""
            lines: list[bytes] = []
            while pos > 0 and len(lines) <= n:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                buffer = f.read(read_size) + buffer
                lines = [ln for ln in buffer.split(b"\n") if ln.strip()]
            return lines[-n:]
    except OSError:
        return []


class RequestLogger:
    """Log requests to JSONL file.

    Uses a deque with max 10,000 entries to prevent unbounded memory growth.
    Gracefully degrades to in-memory-only if the log file cannot be written
    (read-only filesystem, permissions error, etc.).
    """

    MAX_LOG_ENTRIES = 10_000

    def __init__(self, log_file: str | None = None, log_full_messages: bool = False):
        self.log_file = Path(log_file) if log_file else None
        self.log_full_messages = log_full_messages
        # Use deque with maxlen for automatic FIFO eviction
        self._logs: deque[RequestLog] = deque(maxlen=self.MAX_LOG_ENTRIES)

        if self.log_file:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(
                    "Cannot create log directory %s: %s — logging to memory only",
                    self.log_file.parent,
                    e,
                )
                self.log_file = None

        # Warm the in-memory deque from the durable JSONL log so that
        # get_recent() returns meaningful data immediately after a restart.
        # Only the tail is needed — we read at most MAX_LOG_ENTRIES lines
        # backwards so startup stays O(log_size) not O(file_size).
        if self.log_file and self.log_file.exists():
            self._warm_from_file()

    def _warm_from_file(self) -> None:
        """Replay the tail of the JSONL log into the in-memory deque.

        Called once at startup so get_recent() is non-empty immediately
        after a proxy restart — preventing the per-request table from
        going blank until new traffic arrives.
        """
        if not self.log_file:
            return
        try:
            # Read the last MAX_LOG_ENTRIES lines without loading the full
            # file — avoids O(file_size) memory on long-running deployments.
            from collections import deque as _deque

            tail: _deque[bytes] = _deque(maxlen=self.MAX_LOG_ENTRIES)
            with open(self.log_file, "rb") as f:
                for line in f:
                    if line.strip():
                        tail.append(line)
            for raw in tail:
                try:
                    data = json.loads(raw)
                    # Re-hydrate into a RequestLog; skip malformed entries.
                    entry = RequestLog(
                        **{k: v for k, v in data.items() if k in RequestLog.__dataclass_fields__}
                    )
                    self._logs.append(entry)
                except Exception:
                    continue
            if self._logs:
                logger.debug(
                    "Warmed request logger from %s: %d entries restored",
                    self.log_file,
                    len(self._logs),
                )
        except OSError:
            pass  # file may not exist yet on a brand-new install

    def log(self, entry: RequestLog):
        """Log a request. Oldest entries are automatically removed when limit reached.

        Phase G PR-G3 (P4-45): base64-encoded image payloads in
        ``request_messages`` / ``compressed_messages`` / ``response_content``
        are redacted before write. Redaction also applies to the in-memory
        deque so the ``/stats/recent_requests`` endpoint never serves a
        multi-MB image either.
        """
        # Redact image payloads in-place on the deque entry so memory
        # use stays bounded. We mutate the dataclass fields rather
        # than wrapping the entry to keep ``get_recent`` /
        # ``get_recent_with_messages`` unchanged.
        entry_redactions = 0
        if entry.request_messages is not None:
            entry.request_messages, count = redact_image_base64_with_count(
                entry.request_messages
            )
            entry_redactions += count
        if entry.compressed_messages is not None:
            entry.compressed_messages, count = redact_image_base64_with_count(
                entry.compressed_messages
            )
            entry_redactions += count
        if entry.response_content is not None:
            entry.response_content, count = redact_image_base64_with_count(
                entry.response_content
            )
            entry_redactions += count
        if entry_redactions > 0 and isinstance(entry.decision_receipt, dict):
            receipt = dict(entry.decision_receipt)
            observation = dict(receipt.get("observation") or {})
            observation["payload_capture"] = "redacted"
            receipt["observation"] = observation
            entry.decision_receipt = receipt

        self._logs.append(entry)

        if self.log_file:
            try:
                with open(self.log_file, "a") as f:
                    log_dict = asdict(entry)
                    if not self.log_full_messages:
                        log_dict.pop("request_messages", None)
                        log_dict.pop("compressed_messages", None)
                        log_dict.pop("response_content", None)
                    f.write(json.dumps(log_dict) + "\n")
            except OSError:
                pass  # Graceful degradation: memory-only logging continues

    def get_recent(self, n: int = 100) -> list[dict]:
        """Get recent log entries (without request/compressed messages and response_content).

        When a shared log file is configured, reads live from its tail
        rather than the in-memory deque, so this reflects requests handled
        by ANY cutctx proxy process writing to the same file — not just
        this process. Falls back to the in-memory deque (this process's
        own requests only) if no log file is configured or it can't be
        read yet.
        """
        entries = self._read_recent_from_file(n)
        if entries is None:
            entries = [asdict(e) for e in list(self._logs)[-n:]]
        return [
            {
                k: v
                for k, v in e.items()
                if k not in ("request_messages", "compressed_messages", "response_content")
            }
            for e in entries
        ]

    def _read_recent_from_file(self, n: int) -> list[dict] | None:
        """Tail-read up to ``n`` entries from the shared JSONL log, if any.

        Returns None (signalling "fall back to the in-memory deque") when
        no log file is configured, the file doesn't exist yet, or it holds
        no parseable lines.
        """
        if not self.log_file:
            return None
        try:
            raw_lines = _tail_lines(self.log_file, n)
        except OSError:
            return None
        if not raw_lines:
            return None
        entries: list[dict] = []
        for raw in raw_lines:
            try:
                entries.append(json.loads(raw))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        return entries or None

    def get_recent_with_messages(self, n: int = 20) -> list[dict]:
        """Get recent log entries including full request/response messages.

        Mirrors ``get_recent()`` by preferring the shared JSONL file when
        configured so inspector-style views can follow requests handled by any
        sibling proxy process.
        """
        entries = self._read_recent_from_file(n)
        if entries is not None:
            return entries
        return [asdict(e) for e in list(self._logs)[-n:]]

    def get_request_with_messages(self, request_id: str) -> dict | None:
        """Return one request log entry, preferring the shared JSONL file."""
        entries = self._read_recent_from_file(self.MAX_LOG_ENTRIES)
        if entries is not None:
            for entry in reversed(entries):
                if entry.get("request_id") == request_id:
                    return entry

        for entry in reversed(self._logs):
            if entry.request_id == request_id:
                return asdict(entry)
        return None

    def stats(self) -> dict:
        """Get logging statistics."""
        return {
            "total_logged": len(self._logs),
            "log_file": str(self.log_file) if self.log_file else None,
        }

    def get_memory_stats(self) -> ComponentStats:
        """Get memory statistics for the MemoryTracker.

        Returns:
            ComponentStats with current memory usage.
        """
        from ..memory.tracker import ComponentStats

        # Calculate size
        size_bytes = sys.getsizeof(self._logs)

        for log_entry in self._logs:
            size_bytes += sys.getsizeof(log_entry)
            # Add string fields
            if log_entry.request_id:
                size_bytes += len(log_entry.request_id)
            if log_entry.provider:
                size_bytes += len(log_entry.provider)
            if log_entry.model:
                size_bytes += len(log_entry.model)
            if log_entry.error:
                size_bytes += len(log_entry.error)
            # Messages and response can be large
            if log_entry.request_messages:
                size_bytes += sys.getsizeof(log_entry.request_messages)
            if log_entry.compressed_messages:
                size_bytes += sys.getsizeof(log_entry.compressed_messages)
            if log_entry.response_content:
                size_bytes += len(log_entry.response_content)

        return ComponentStats(
            name="request_logger",
            entry_count=len(self._logs),
            size_bytes=size_bytes,
            budget_bytes=None,
            hits=0,
            misses=0,
            evictions=0,
        )
