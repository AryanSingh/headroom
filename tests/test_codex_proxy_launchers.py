from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_codex_launcher_waits_for_readyz_and_fails_closed() -> None:
    script = Path.home() / ".local/bin/codex-cutctx-lib.sh"
    source = script.read_text()

    assert 'local url="http://127.0.0.1:${port}/readyz"' in source
    assert 'deadline=$(( $(date +%s) + 180 ))' in source
    launcher = source[source.index("codex_cutctx_ensure_proxy"):]
    assert "return 1" in launcher
    assert "continuing anyway" not in launcher


def test_manual_restart_waits_for_readyz_and_exits_on_timeout() -> None:
    source = (ROOT / "restart-proxy.sh").read_text()

    assert "/readyz" in source
    assert "seq 1 180" in source
    assert "exit 1" in source
    assert "READY!" in source


def test_launch_agent_guard_checks_import_without_building_a_second_app() -> None:
    guard = Path.home() / ".cutctx-proxy-guard.sh"
    source = guard.read_text()

    assert 'from cutctx.proxy.server import create_app' in source
    assert "create_app()" not in source
