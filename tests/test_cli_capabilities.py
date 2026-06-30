from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import cutctx.cli.capabilities as cli_capabilities
from cutctx.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class FakeTable:
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.columns: list[str] = []
        self.rows: list[tuple[object, ...]] = []

    def add_column(self, name: str, **kwargs) -> None:  # noqa: ANN003
        self.columns.append(name)

    def add_row(self, *values: object) -> None:
        self.rows.append(values)


class FakeConsole:
    instances: list["FakeConsole"] = []

    def __init__(self) -> None:
        self.printed: list[object] = []
        FakeConsole.instances.append(self)

    def print(self, value: object) -> None:
        self.printed.append(value)


def install_fake_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeConsole.instances.clear()
    monkeypatch.setitem(sys.modules, "rich.console", SimpleNamespace(Console=FakeConsole))
    monkeypatch.setitem(sys.modules, "rich.table", SimpleNamespace(Table=FakeTable))


def test_capabilities_json_includes_audio_passthrough(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr(
        cli_capabilities,
        "_check_feature",
        lambda feature: {
            "name": feature["name"],
            "label": feature["label"],
            "available": True,
            "missing_packages": [],
            "extra": feature["extra"],
            "critical": False,
            "mode": "pass-through" if feature["name"] == "audio" else "optional",
            "install_hint": None,
            "reason": (
                "proxied unchanged; no token compression applied"
                if feature["name"] == "audio"
                else None
            ),
        },
    )

    result = runner.invoke(main, ["capabilities", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    audio = next(item for item in data if item["name"] == "audio")
    assert audio["mode"] == "pass-through"
    assert audio["reason"] == "proxied unchanged; no token compression applied"


def test_capabilities_table_shows_passthrough_status(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    install_fake_rich(monkeypatch)
    monkeypatch.setattr(
        cli_capabilities,
        "_check_feature",
        lambda feature: {
            "name": feature["name"],
            "label": feature["label"],
            "available": feature["name"] == "audio",
            "missing_packages": [] if feature["name"] == "audio" else ["graphifyy"],
            "extra": feature["extra"],
            "critical": False,
            "mode": "pass-through" if feature["name"] == "audio" else "optional",
            "install_hint": (
                None
                if feature["name"] == "audio"
                else f"pip install cutctx-ai[{feature['extra']}]"
            ),
            "reason": (
                "proxied unchanged; no token compression applied"
                if feature["name"] == "audio"
                else "graphifyy"
            ),
        },
    )

    result = runner.invoke(main, ["capabilities"])

    assert result.exit_code == 0
    console = FakeConsole.instances[-1]
    table = console.printed[0]
    assert isinstance(table, FakeTable)
    assert (
        "Audio Routes",
        "[blue]pass-through[/blue]",
        "built-in",
        "-",
    ) in table.rows
    assert (
        "Knowledge Graph (Graphify)",
        "[yellow]not installed[/yellow]",
        "knowledge-graph",
        "pip install cutctx-ai[knowledge-graph]",
    ) in table.rows
    assert "[dim]knowledge_graph:[/dim] graphifyy" in console.printed
    assert (
        "[dim]audio:[/dim] proxied unchanged; no token compression applied"
        in console.printed
    )


def test_python_m_main_capabilities_json_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cutctx.cli.main", "capabilities", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert any(item["name"] == "audio" for item in data)


def test_check_feature_llmlingua_requires_runtime_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_find_spec = cli_capabilities.importlib.util.find_spec

    def fake_find_spec(name: str):  # type: ignore[no-untyped-def]
        if name in {"llmlingua", "torch"}:
            return object()
        if name == "cutctx.transforms.llmlingua_compressor":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(cli_capabilities.importlib.util, "find_spec", fake_find_spec)

    feature = next(item for item in cli_capabilities._FEATURES if item["name"] == "llmlingua")
    result = cli_capabilities._check_feature(feature)

    assert result["available"] is False
    assert "cutctx.transforms.llmlingua_compressor" in result["missing_packages"]
