"""Deterministic contract checks for the non-dashboard product surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import CliRunner

from cutctx.cli.main import get_version, main
from cutctx.hosted import HostedCompressionClient, HostedCompressionError

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _read_json(relative_path: str) -> dict[str, Any]:
    return json.loads(_read(relative_path))


def test_click_cli_help_error_and_success_contracts() -> None:
    runner = CliRunner()

    help_result = runner.invoke(main, ["--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "wrap           Wrap CLI tools" in help_result.output
    assert "proxy" in help_result.output
    assert "mcp" in help_result.output

    error_result = runner.invoke(main, ["not-a-real-command"])
    assert error_result.exit_code == 1
    assert "is unavailable in this installation" in error_result.output

    version_result = runner.invoke(main, ["--version"])
    assert version_result.exit_code == 0, version_result.output
    assert version_result.output.strip() == f"cutctx, version {get_version()}"


def test_click_wrapper_prepare_only_success_is_provider_free() -> None:
    result = CliRunner().invoke(
        main,
        ["wrap", "claude", "--prepare-only", "--no-context-tool"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == ""


class _Response:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> Any:
        return self._payload


@pytest.mark.parametrize(
    ("base_url", "api_key", "expected_url", "expected_headers"),
    [
        (
            "http://127.0.0.1:8787/",
            None,
            "http://127.0.0.1:8787/v1/hosted/compress",
            {},
        ),
        (
            "https://api.cutctx.example/",
            "hosted-secret",
            "https://api.cutctx.example/v1/hosted/compress",
            {"Authorization": "Bearer hosted-secret"},
        ),
    ],
)
def test_python_hosted_client_local_and_hosted_contract(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    api_key: str | None,
    expected_url: str,
    expected_headers: dict[str, str],
) -> None:
    calls: list[dict[str, Any]] = []
    payload = {
        "input_kind": "text",
        "compatibility_mode": "tool_output",
        "model": "gpt-4o",
        "text": "compressed",
        "messages": [{"role": "tool", "content": "compressed"}],
        "tokens_before": 100,
        "tokens_after": 40,
        "tokens_saved": 60,
        "compression_ratio": 0.4,
        "transforms_applied": ["router:smart_crusher:0.40"],
    }

    def fake_post(url: str, **kwargs: Any) -> _Response:
        calls.append({"url": url, **kwargs})
        return _Response(200, payload)

    monkeypatch.setattr(httpx, "post", fake_post)

    result = HostedCompressionClient(base_url, api_key=api_key).compress_text(
        "long tool output",
        model="gpt-4o",
        compatibility_mode="tool_output",
        min_tokens_to_compress=10,
    )

    assert result.tokens_saved == 60
    assert result.compression_ratio == 0.4
    assert result.compatibility_mode == "tool_output"
    assert calls == [
        {
            "url": expected_url,
            "json": {
                "text": "long tool output",
                "model": "gpt-4o",
                "compatibility_mode": "tool_output",
                "min_tokens_to_compress": 10,
            },
            "headers": expected_headers,
            "timeout": 30.0,
        }
    ]


def test_python_hosted_client_preserves_structured_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *_args, **_kwargs: _Response(
            401,
            {"error": {"message": "Invalid hosted key"}},
        ),
    )

    with pytest.raises(HostedCompressionError) as raised:
        HostedCompressionClient("https://api.cutctx.example").compress_text("hello")

    assert raised.value.status_code == 401
    assert raised.value.payload == {"error": {"message": "Invalid hosted key"}}
    assert str(raised.value) == "Invalid hosted key"


def test_agent_manifests_and_mcp_contracts_match_documented_entrypoints() -> None:
    tool_names = {"cutctx_compress", "cutctx_retrieve", "cutctx_status"}

    claude = _read_json("plugins/claude-code/.claude-plugin/plugin.json")
    assert {tool["name"] for tool in claude["tools"]} == tool_names
    assert {tool["command"] for tool in claude["tools"]} == {"cutctx mcp serve"}
    claude_hooks = _read_json("plugins/claude-code/hooks/hooks.json")
    assert {"SessionStart", "PreToolUse", "PostToolUse"} <= set(claude_hooks["hooks"])

    codex = _read_json("plugins/codex/plugin.json")
    assert {tool["name"] for tool in codex["tools"]} == tool_names
    assert codex["provider"]["base_url"].endswith("/v1")
    assert codex["provider"]["env"]["OPENAI_BASE_URL"] == codex["provider"]["base_url"]

    opencode_package = _read_json("plugins/cutctx-opencode/package.json")
    opencode_source = _read("plugins/cutctx-opencode/cutctx.ts")
    assert opencode_package["main"] == "dist/cutctx.js"
    assert "build" in opencode_package["scripts"]
    assert '"tool.execute.after"' in opencode_source
    assert '"experimental.chat.messages.transform"' in opencode_source

    openclaw_package = _read_json("plugins/openclaw/package.json")
    openclaw_manifest = _read_json("plugins/openclaw/openclaw.plugin.json")
    assert openclaw_package["openclaw"]["extensions"] == ["./dist/index.js"]
    assert openclaw_manifest["id"] == "cutctx"
    assert openclaw_manifest["kind"] == "context-engine"
    assert openclaw_manifest["configSchema"]["properties"]["proxyUrl"]["type"] == "string"

    mcp_cli = _read("cutctx/cli/mcp.py")
    assert "cutctx_retrieve" in mcp_cli
    assert "cutctx_compress" in mcp_cli
    assert '@mcp.command("status")' in mcp_cli
    assert "def mcp_status" in mcp_cli
    assert "cutctx mcp install" in mcp_cli


def test_wrapper_plugin_and_sdk_docs_reference_the_supported_examples() -> None:
    root_readme = _read("README.md")
    product_guide = _read("PRODUCT_GUIDE.md")
    claude_readme = _read("plugins/claude-code/README.md")
    codex_readme = _read("plugins/codex/README.md")
    openclaw_readme = _read("plugins/openclaw/README.md")
    typescript_readme = _read("sdk/typescript/README.md")

    assert "cutctx wrap claude|codex" in root_readme
    for agent in ("claude", "codex", "opencode"):
        assert f"cutctx wrap {agent}" in product_guide
    assert "cutctx mcp install" in root_readme
    assert "cutctx_compress" in root_readme
    assert "cutctx mcp install --agent claude" in claude_readme
    assert "cutctx mcp install --agent codex" in codex_readme
    assert "cutctx wrap openclaw" in openclaw_readme
    assert "contextEngine" in openclaw_readme

    for example_text in (
        "HostedCompressionClient",
        "compressText",
        "compressMessages",
        "http://localhost:8787",
        "https://api.cutctx.ai",
    ):
        assert example_text in typescript_readme
