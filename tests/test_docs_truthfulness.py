from __future__ import annotations

from pathlib import Path

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent


def test_user_docs_describe_routing_as_appropriate_not_best() -> None:
    files = [
        _PROJECT_ROOT / "docs/components/marketing.tsx",
        _PROJECT_ROOT / "docs/content/docs/quickstart.mdx",
        _PROJECT_ROOT / "docs/content/docs/shared-context.mdx",
    ]

    for path in files:
        text = path.read_text()
        assert "most appropriate compressor" in text, (
            f"{path} should describe routing as selecting the most appropriate "
            "compressor rather than making an absolute best-compressor claim."
        )
        assert "best compressor" not in text


def test_marketing_component_does_not_ship_hardcoded_live_stats() -> None:
    text = (_PROJECT_ROOT / "docs/components/marketing.tsx").read_text()
    assert "const liveStats" not in text
    assert "export function LiveStats" not in text
    assert "$176.6K" not in text


def test_installation_docs_describe_voice_extra_truthfully() -> None:
    text = (_PROJECT_ROOT / "docs/content/docs/installation.mdx").read_text()
    assert "Voice ML extras" in text
    assert "Audio API routes still proxy pass-through" in text
    assert "Voice/audio support" not in text


def test_community_stats_docs_do_not_claim_realtime_fetch() -> None:
    files = [
        _PROJECT_ROOT / "docs/lib/telemetry.ts",
        _PROJECT_ROOT / "docs/components/live-stats.tsx",
        _PROJECT_ROOT / "docs/components/community-stats-header.tsx",
        _PROJECT_ROOT / "docs/content/docs/community-savings.mdx",
    ]

    combined = "\n".join(path.read_text() for path in files)
    assert "published community snapshot" in combined
    assert "Published aggregate snapshot" in combined
    assert "Real-time aggregate metrics" not in combined
    assert "fetches live stats from Supabase" not in combined


def test_wiki_does_not_claim_intelligent_context_manager() -> None:
    files = [
        Path("wiki/ARCHITECTURE.md"),
        Path("wiki/LIMITATIONS.md"),
        Path("wiki/api.md"),
        Path("wiki/index.md"),
        Path("wiki/strands.md"),
    ]

    for path in files:
        if path.exists():
            text = path.read_text()
            assert "IntelligentContext" not in text, (
                f"{path} still references the retired IntelligentContext manager"
            )


def test_wiki_documents_session_sticky_memory_tool_controls() -> None:
    memory_text = (_PROJECT_ROOT / "wiki/memory.md").read_text()
    config_text = (_PROJECT_ROOT / "wiki/configuration.md").read_text()

    assert "Session-Sticky Memory Tool Injection" in memory_text
    assert "CUTCTX_TOOL_INJECTION_STICKY" in memory_text
    assert "CUTCTX_TOOL_TRACKER_MAX_SESSIONS" in memory_text
    assert "CUTCTX_TOOL_TRACKER_PATH" in config_text
    assert "replays the same golden memory-tool definitions" in memory_text


def test_wiki_documents_strategy_rebranding_map() -> None:
    text = (_PROJECT_ROOT / "wiki/ARCHITECTURE.md").read_text()

    assert "Strategy Rebranding Mapping" in text
    assert "STRATEGY_DISPLAY" in text
    assert "SMART_CRUSH" in text
    assert "K-Means Compression" in text


def test_docs_site_documents_session_sticky_memory_tool_controls() -> None:
    memory_text = (_PROJECT_ROOT / "docs/content/docs/memory.mdx").read_text()
    proxy_text = (_PROJECT_ROOT / "docs/content/docs/proxy.mdx").read_text()
    config_text = (_PROJECT_ROOT / "docs/content/docs/configuration.mdx").read_text()

    assert "Session-Sticky Memory Tool Injection" in memory_text
    assert "CUTCTX_TOOL_INJECTION_STICKY" in memory_text
    assert "CUTCTX_TOOL_TRACKER_MAX_SESSIONS" in proxy_text
    assert "CUTCTX_TOOL_TRACKER_PATH" in proxy_text
    assert "CUTCTX_TOOL_TRACKER_PATH" in config_text


def test_docs_site_documents_dashboard_surface_truthfully() -> None:
    proxy_text = (_PROJECT_ROOT / "docs/content/docs/proxy.mdx").read_text()
    wiki_text = (_PROJECT_ROOT / "wiki/proxy.md").read_text()

    for text in (proxy_text, wiki_text):
        assert "Dashboard surface" in text
        assert "/dashboard" in text
        assert "/admin" in text
        assert "5 seconds" in text
        assert "60 seconds" in text


def test_docs_site_documents_dashboard_obfuscation_truthfully() -> None:
    proxy_text = (_PROJECT_ROOT / "docs/content/docs/proxy.mdx").read_text()
    wiki_text = (_PROJECT_ROOT / "wiki/proxy.md").read_text()
    report_text = (_PROJECT_ROOT / "audit/comprehensive-capability-report.md").read_text()

    for text in (proxy_text, wiki_text):
        assert "commented-out production obfuscation hook" in text
        assert "obfuscator plugin is not active" in text

    assert "Inactive placeholder" in report_text
    assert "dashboard/vite.config.js" in report_text


def test_docs_site_documents_llmlingua_optional_truthfully() -> None:
    docs_text = (_PROJECT_ROOT / "dashboard/src/pages/Docs.jsx").read_text()
    proxy_text = (_PROJECT_ROOT / "docs/content/docs/proxy.mdx").read_text()
    logs_text = (_PROJECT_ROOT / "docs/content/docs/text-and-logs.mdx").read_text()

    assert "Use LLMLingua-2 for optional plain-text compression" in docs_text
    assert "LLMLingua remains optional" in proxy_text
    assert "LLMLingua remains optional" in logs_text


def test_docs_site_documents_mode_aliases_truthfully() -> None:
    docs_text = (_PROJECT_ROOT / "docs/content/docs/configuration.mdx").read_text()
    wiki_text = (_PROJECT_ROOT / "wiki/configuration.md").read_text()
    report_text = (_PROJECT_ROOT / "audit/comprehensive-capability-report.md").read_text()

    for text in (docs_text, wiki_text):
        assert "Compatibility aliases" in text
        assert "token_mode" in text
        assert "cache_mode" in text
        assert "token_savings" in text
        assert "cost_savings" in text
        assert "token_cutctx" in text

    assert "Compatibility aliases for modes" in report_text


def test_docs_site_documents_all_bundle_truthfully() -> None:
    install_text = (_PROJECT_ROOT / "docs/content/docs/installation.mdx").read_text()

    assert "broad convenience bundle" in install_text
    assert 'not a literal "install everything" preset' in install_text
    assert "memory-stack" in install_text


def test_dashboard_docs_page_matches_runtime_configuration_terms() -> None:
    docs_text = (_PROJECT_ROOT / "dashboard/src/pages/Docs.jsx").read_text()

    assert "Compression mode: token (default) or cache" in docs_text
    assert "broad bundle — omits some heavy/proprietary extras" in docs_text
    assert "Accuracy guard" in docs_text
    assert "Use LLMLingua-2 for optional plain-text compression" in docs_text
