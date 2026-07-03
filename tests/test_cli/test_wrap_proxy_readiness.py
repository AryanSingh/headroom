from __future__ import annotations

from pathlib import Path

from cutctx.cli import wrap as wrap_mod


def test_start_proxy_waits_for_readyz_before_returning(
    monkeypatch,
    tmp_path: Path,
) -> None:
    readiness_checks: list[int] = []
    popen_kwargs: dict[str, object] = {}

    class FakeProc:
        returncode = None

        def poll(self) -> None:
            return None

    def fake_popen(*args: object, **kwargs: object) -> FakeProc:
        popen_kwargs.update(kwargs)
        return FakeProc()

    states = iter([False, False, True])

    monkeypatch.setattr(wrap_mod, "_get_log_path", lambda: tmp_path / "proxy.log")
    monkeypatch.setattr(
        "cutctx.paths.request_history_path",
        lambda: tmp_path / "request_history.jsonl",
    )
    monkeypatch.setattr(wrap_mod, "_resolve_wrap_proxy_timeout_seconds", lambda: 3)
    monkeypatch.setattr(wrap_mod.time, "sleep", lambda _: None)
    monkeypatch.setattr(wrap_mod.subprocess, "Popen", fake_popen)

    def fake_ready(port: int, timeout_seconds: float = 1.0) -> bool:
        readiness_checks.append(port)
        return next(states)

    monkeypatch.setattr(wrap_mod, "_check_proxy_ready", fake_ready)

    proc = wrap_mod._start_proxy(8787, agent_type="codex")

    assert isinstance(proc, FakeProc)
    assert readiness_checks == [8787, 8787, 8787]
    assert popen_kwargs["env"]["CUTCTX_LOG_FILE"] == str(
        tmp_path / "request_history.jsonl"
    )
