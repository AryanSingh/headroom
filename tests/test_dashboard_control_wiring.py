"""Release contracts for dashboard controls that were previously inert."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dashboard"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_global_search_reaches_capabilities_and_replay() -> None:
    app = _read("src/App.jsx")
    replay = _read("src/pages/Replay.jsx")

    assert '<Capabilities searchQuery={searchQuery}' in app
    assert 'searchQuery={searchQuery} setSearchQuery={setSearchQuery}' in app
    assert "export default function Replay({ searchQuery" in replay


def test_new_contract_and_trend_bars_are_actionable() -> None:
    studio = _read("src/components/routing-studio/RoutingStudio.jsx")
    overview = _read("src/pages/Overview.jsx")

    assert "onNew={() =>" in studio
    assert "setDraft(newDraft())" in studio
    assert 'className={`trend-bar ' in overview
    assert 'type="button"' in overview
    assert "onKeyDown={moveTrendFocus}" in overview


def test_playground_dev_proxy_uses_admin_key_header() -> None:
    vite = _read("vite.config.js")
    playground = _read("src/pages/Playground.jsx")

    assert "headers['x-cutctx-admin-key'] = adminKey" in vite
    assert "'x-cutctx-admin-key': adminKey.trim()" in playground
