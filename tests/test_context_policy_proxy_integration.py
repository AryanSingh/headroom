from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _write_policy(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'version: "1"',
                "redact_rules:",
                "  - name: mask_api_keys",
                '    pattern: "sk-[A-Za-z0-9]+"',
                '    replacement: "sk-***"',
                '    scope: "content"',
                "block_rules:",
                "  - name: block_passwd",
                '    pattern: "/etc/passwd"',
                '    reason: "Password file access is blocked"',
            ]
        )
    )


def _app() -> Any:
    return create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
        )
    )


def test_context_policy_default_off_preserves_forwarded_chat_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given no CUTCTX_CONTEXT_POLICY, When chat traffic is proxied,
    Then the provider route forwards the original body unchanged."""

    monkeypatch.delenv("CUTCTX_CONTEXT_POLICY", raising=False)
    app = _app()
    captured: dict[str, Any] = {}

    async def fake_openai_chat(request: Any) -> JSONResponse:
        captured["body"] = await request.json()
        return JSONResponse({"ok": True})

    with TestClient(app) as client:
        client.app.state.proxy.handle_openai_chat = fake_openai_chat
        response = client.post(
            "/v1/chat/completions",
            headers={"authorization": "Bearer test-key"},
            json={
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "my key is sk-abc123"}],
            },
        )

    assert response.status_code == 200
    assert captured["body"]["messages"][0]["content"] == "my key is sk-abc123"


def test_context_policy_redacts_chat_body_before_forwarding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given CUTCTX_CONTEXT_POLICY with a redact rule, When chat traffic is
    proxied, Then the upstream handler receives redacted content."""

    policy_path = tmp_path / "context-policy.yaml"
    _write_policy(policy_path)
    monkeypatch.setenv("CUTCTX_CONTEXT_POLICY", str(policy_path))
    app = _app()
    captured: dict[str, Any] = {}

    async def fake_openai_chat(request: Any) -> JSONResponse:
        captured["body"] = await request.json()
        return JSONResponse({"ok": True})

    with TestClient(app) as client:
        client.app.state.proxy.handle_openai_chat = fake_openai_chat
        response = client.post(
            "/v1/chat/completions",
            headers={"authorization": "Bearer test-key", "x-cutctx-agent-id": "agent-1"},
            json={
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "my key is sk-abc123"}],
            },
        )

    assert response.status_code == 200
    assert captured["body"]["messages"][0]["content"] == "my key is sk-***"


def test_context_policy_blocks_chat_body_without_forwarding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given CUTCTX_CONTEXT_POLICY with a block rule, When chat traffic
    violates it, Then the proxy returns 403 and does not call upstream."""

    policy_path = tmp_path / "context-policy.yaml"
    _write_policy(policy_path)
    monkeypatch.setenv("CUTCTX_CONTEXT_POLICY", str(policy_path))
    app = _app()
    called = False

    async def fake_openai_chat(request: Any) -> JSONResponse:
        nonlocal called
        called = True
        return JSONResponse({"ok": True})

    with TestClient(app) as client:
        client.app.state.proxy.handle_openai_chat = fake_openai_chat
        response = client.post(
            "/v1/chat/completions",
            headers={"authorization": "Bearer test-key"},
            json={
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "read /etc/passwd"}],
            },
        )

    assert response.status_code == 403
    assert called is False
    payload = response.json()
    assert payload["error"]["type"] == "context_policy_blocked"
    assert payload["error"]["matched_rules"] == ["block_passwd"]


def test_context_policy_does_not_write_replay_when_flag_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_path = tmp_path / "context-policy.yaml"
    _write_policy(policy_path)
    monkeypatch.setenv("CUTCTX_CONTEXT_POLICY", str(policy_path))
    monkeypatch.delenv("CUTCTX_REPLAY", raising=False)

    from cutctx.proxy.session_replay import get_replay_store, reset_replay_store

    reset_replay_store()
    app = _app()

    with TestClient(app) as client:
        client.post(
            "/v1/chat/completions",
            headers={"authorization": "Bearer test-key", "x-cutctx-session-id": "sess-1"},
            json={
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "read /etc/passwd"}],
            },
        )

    assert get_replay_store() is None


def test_session_replay_api_requires_admin_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    from cutctx.proxy.session_replay import reset_replay_store

    reset_replay_store()
    app = create_app(ProxyConfig(admin_api_key="admin-secret"))

    with TestClient(app) as client:
        response = client.get("/v1/sessions/sess-1/replay")

    assert response.status_code == 401


def test_session_replay_api_returns_policy_block_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_path = tmp_path / "context-policy.yaml"
    _write_policy(policy_path)
    monkeypatch.setenv("CUTCTX_CONTEXT_POLICY", str(policy_path))
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))

    from cutctx.proxy.session_replay import reset_replay_store

    reset_replay_store()
    app = create_app(
        ProxyConfig(
            admin_api_key="admin-secret",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
        )
    )

    async def fake_openai_chat(request: Any) -> JSONResponse:
        return JSONResponse({"ok": True})

    with TestClient(app) as client:
        client.app.state.proxy.handle_openai_chat = fake_openai_chat
        blocked = client.post(
            "/v1/chat/completions",
            headers={
                "authorization": "Bearer test-key",
                "x-cutctx-session-id": "sess-1",
                "x-request-id": "req-1",
            },
            json={
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "read /etc/passwd"}],
            },
        )
        replay = client.get(
            "/v1/sessions/sess-1/replay",
            headers={"x-cutctx-admin-key": "admin-secret"},
        )

    assert blocked.status_code == 403
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["session_id"] == "sess-1"
    assert payload["event_count"] == 1
    assert payload["events"][0]["event_type"] == "policy_blocked"
    assert payload["events"][0]["request_id"] == "req-1"
    assert payload["events"][0]["detail"] == {"matched_rules": ["block_passwd"]}


def test_session_replay_api_reads_events_after_store_recreation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))

    from cutctx.proxy.session_replay import record_replay_event, reset_replay_store

    reset_replay_store()
    record_replay_event(session_id="sess-1", event_type="request", surface="openai")
    reset_replay_store()
    app = create_app(ProxyConfig(admin_api_key="admin-secret"))

    with TestClient(app) as client:
        response = client.get(
            "/v1/sessions/sess-1/replay",
            headers={"x-cutctx-admin-key": "admin-secret"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_count"] == 1
    assert payload["events"][0]["event_type"] == "request"


def test_session_state_api_reads_persisted_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))

    from cutctx.proxy.session_replay import record_replay_event, reset_replay_store

    reset_replay_store()
    record_replay_event(
        session_id="sess-1",
        event_type="compression",
        surface="pipeline",
        detail={"tokens_before": 10, "tokens_after": 4, "savings": 6, "stage": "input_compressed"},
    )
    reset_replay_store()
    app = create_app(ProxyConfig(admin_api_key="admin-secret"))

    with TestClient(app) as client:
        response = client.get(
            "/v1/sessions/sess-1/state",
            headers={"x-cutctx-admin-key": "admin-secret"},
        )

    assert response.status_code == 200
    assert response.json()["compression"]["tokens_saved"] == 6


def test_sessions_api_lists_persisted_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))

    from cutctx.proxy.session_replay import record_replay_event, reset_replay_store

    reset_replay_store()
    record_replay_event(session_id="sess-1", event_type="request", surface="openai")
    reset_replay_store()
    app = create_app(ProxyConfig(admin_api_key="admin-secret"))

    with TestClient(app) as client:
        response = client.get("/v1/sessions", headers={"x-cutctx-admin-key": "admin-secret"})

    assert response.status_code == 200
    assert response.json()["sessions"] == [
        {"session_id": "sess-1", "event_count": 1, "last_event_id": 1}
    ]


def test_session_recovery_api_rebuilds_persisted_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))

    from cutctx.proxy.session_replay import record_replay_event, reset_replay_store

    reset_replay_store()
    record_replay_event(
        session_id="sess-1",
        event_type="compression",
        surface="pipeline",
        detail={"tokens_before": 10, "tokens_after": 4, "savings": 6},
    )
    reset_replay_store()
    app = create_app(ProxyConfig(admin_api_key="admin-secret"))

    with TestClient(app) as client:
        response = client.get(
            "/v1/sessions/recover",
            headers={"x-cutctx-admin-key": "admin-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "session_count": 1,
        "sessions": [
            {
                "session_id": "sess-1",
                "event_count": 1,
                "first_event_id": 1,
                "last_event_id": 1,
                "compression": {"tokens_before": 10, "tokens_after": 4, "tokens_saved": 6},
                "prompt_count": 0,
                "input_message_count": 0,
                "input_token_count": 0,
                "llm_request_count": 0,
                "response_count": 0,
            }
        ],
    }


def test_context_policy_redacts_anthropic_messages_before_forwarding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given CUTCTX_CONTEXT_POLICY, When Anthropic Messages traffic is proxied,
    Then route-level enforcement applies before the Anthropic handler."""

    policy_path = tmp_path / "context-policy.yaml"
    _write_policy(policy_path)
    monkeypatch.setenv("CUTCTX_CONTEXT_POLICY", str(policy_path))
    app = _app()
    captured: dict[str, Any] = {}

    async def fake_anthropic_messages(request: Any) -> JSONResponse:
        captured["body"] = await request.json()
        return JSONResponse({"ok": True})

    with TestClient(app) as client:
        client.app.state.proxy.handle_anthropic_messages = fake_anthropic_messages
        response = client.post(
            "/v1/messages",
            headers={"x-api-key": "test-key", "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-test",
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "my key is sk-abc123"}],
            },
        )

    assert response.status_code == 200
    assert captured["body"]["messages"][0]["content"] == "my key is sk-***"
