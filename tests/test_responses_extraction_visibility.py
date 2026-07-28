"""The Responses path must say what it skipped.

Codex traffic reported ~0% savings with no way to tell whether items were
skipped before reaching a compressor, compressed and rejected by the
acceptance gate, or genuinely incompressible. The per-item reasons existed but
only behind CUTCTX_CODEX_COMPRESSION_DEBUG, so production had no signal.

The scale of the blind spot: 98.2% of recorded compression episodes have
original_size = 0 — nothing measured — while the 1.8% that do reach a
compressor are accepted 99.4% of the time at a median ratio of 0.578. The
compressors work; content was not reaching them, and nothing said so.
"""

from __future__ import annotations

import json
import logging

import pytest

pytest.importorskip("fastapi")

from cutctx.proxy.server import ProxyConfig, create_app  # noqa: E402


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _payload(turns: int = 3) -> dict:
    reasoning = "Considering the failure mode in detail before dispatch. " * 200
    logs = "\n".join(
        f"2026-07-27T10:00:{i % 60:02d}Z INFO worker-{i % 8} req_{i} status=200" for i in range(300)
    )
    items: list[dict] = []
    for t in range(turns):
        items.append(
            {"type": "reasoning", "summary": [{"type": "summary_text", "text": reasoning}]}
        )
        items.append(
            {"type": "function_call", "call_id": f"c{t}", "name": "shell", "arguments": "{}"}
        )
        items.append({"type": "function_call_output", "call_id": f"c{t}", "output": logs})
    return {"model": "gpt-5.6-terra", "input": items}


def test_extraction_reports_what_it_skipped() -> None:
    proxy = create_app(
        ProxyConfig(optimize=True, cache_enabled=False, rate_limit_enabled=False)
    ).state.proxy
    handler = _Capture()
    logger = logging.getLogger("cutctx.proxy")
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.INFO)
    try:
        proxy._compress_openai_responses_live_text_units_with_router(
            _payload(), model="gpt-5.6-terra", request_id="test"
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)

    lines = [m for m in handler.messages if "responses_extraction" in m]
    assert lines, "extraction emitted no skip summary; the blind spot is back"
    line = lines[0]
    # Names the shapes, so an operator can act on it.
    assert "unsupported:reasoning" in line
    assert "eligible=" in line and "skipped=" in line


def test_protected_roles_are_not_reported_as_unsupported_types() -> None:
    """A `message` is a protected role, not an unsupported type.

    Labelling it "unsupported:message" points the reader at extraction rules
    when the real decision is unit policy — user and system are never
    rewritten, assistant only with compress_assistant. Since this tally is the
    primary diagnostic for the Responses path, a misleading reason in it sends
    somebody off widening extraction for no reason.
    """
    proxy = create_app(
        ProxyConfig(optimize=True, cache_enabled=False, rate_limit_enabled=False)
    ).state.proxy
    handler = _Capture()
    logger = logging.getLogger("cutctx.proxy")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    big = "The handler validates input before dispatch. " * 200
    payload = {
        "model": "gpt-5.6-terra",
        "input": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": big}],
            },
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": big}]},
        ],
    }
    try:
        proxy._compress_openai_responses_live_text_units_with_router(
            payload, model="gpt-5.6-terra", request_id="roles"
        )
    finally:
        logger.removeHandler(handler)

    line = next(m for m in handler.messages if "responses_extraction" in m)
    assert "protected_role:assistant" in line
    assert "protected_role:user" in line
    assert "unsupported:message" not in line


def test_skip_summary_carries_no_payload_content() -> None:
    """Counts only. This runs on every request and must never log user text."""
    proxy = create_app(
        ProxyConfig(optimize=True, cache_enabled=False, rate_limit_enabled=False)
    ).state.proxy
    handler = _Capture()
    logger = logging.getLogger("cutctx.proxy")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # The module logs under "cutctx.proxy", not __name__ — attaching to the
    # dotted module path silently captures nothing and makes absence-based
    # assertions pass for the wrong reason.
    secret = "SENTINEL-DO-NOT-LOG-7Q2"
    payload = _payload()
    payload["input"][0]["summary"][0]["text"] = secret + " " * 4000
    try:
        proxy._compress_openai_responses_live_text_units_with_router(
            payload, model="gpt-5.6-terra", request_id="test"
        )
    finally:
        logger.removeHandler(handler)

    for message in handler.messages:
        if "responses_extraction" in message:
            assert secret not in message, "skip summary leaked payload content"


def test_fully_eligible_payload_emits_nothing() -> None:
    """No noise when there is nothing to report."""
    proxy = create_app(
        ProxyConfig(optimize=True, cache_enabled=False, rate_limit_enabled=False)
    ).state.proxy
    handler = _Capture()
    logger = logging.getLogger("cutctx.proxy")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logs = "\n".join(f"2026-07-27T10:00:00Z INFO req_{i} status=200" for i in range(300))
    payload = {
        "model": "gpt-5.6-terra",
        "input": [{"type": "function_call_output", "call_id": "c0", "output": logs}],
    }
    try:
        proxy._compress_openai_responses_live_text_units_with_router(
            payload, model="gpt-5.6-terra", request_id="test"
        )
    finally:
        logger.removeHandler(handler)

    assert not [m for m in handler.messages if "responses_extraction" in m]
    assert json.dumps(payload)  # payload still serialisable
