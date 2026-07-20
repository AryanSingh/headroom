from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "live_agent_protocol_canary.py"
SPEC = importlib.util.spec_from_file_location("live_agent_protocol_canary", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_retry_policy_never_retries_schema_failures() -> None:
    assert MODULE.is_retryable_status(400) is False
    assert MODULE.is_retryable_status(401) is False
    assert MODULE.is_retryable_status(429) is True
    assert MODULE.is_retryable_status(500) is True
    assert MODULE.is_retryable_status(503) is True


def test_codex_session_id_parser_accepts_current_jsonl_shapes() -> None:
    output = "\n".join(
        [
            '{"type":"thread.started","thread_id":"019f0000-0000-7000-8000-000000000001"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}',
        ]
    )
    assert MODULE.extract_session_id(output) == "019f0000-0000-7000-8000-000000000001"
