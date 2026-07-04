from __future__ import annotations

from pathlib import Path


def test_user_docs_describe_routing_as_appropriate_not_best() -> None:
    files = [
        Path("docs/components/marketing.tsx"),
        Path("docs/content/docs/quickstart.mdx"),
        Path("docs/content/docs/shared-context.mdx"),
    ]

    for path in files:
        text = path.read_text()
        assert "most appropriate compressor" in text, (
            f"{path} should describe routing as selecting the most appropriate "
            "compressor rather than making an absolute best-compressor claim."
        )
        assert "best compressor" not in text


def test_marketing_component_does_not_ship_hardcoded_live_stats() -> None:
    text = Path("docs/components/marketing.tsx").read_text()
    assert "const liveStats" not in text
    assert "export function LiveStats" not in text
    assert "$176.6K" not in text


def test_installation_docs_describe_voice_extra_truthfully() -> None:
    text = Path("docs/content/docs/installation.mdx").read_text()
    assert "Voice ML extras" in text
    assert "Audio API routes still proxy pass-through" in text
    assert "Voice/audio support" not in text


def test_community_stats_docs_do_not_claim_realtime_fetch() -> None:
    files = [
        Path("docs/lib/telemetry.ts"),
        Path("docs/components/live-stats.tsx"),
        Path("docs/components/community-stats-header.tsx"),
        Path("docs/content/docs/community-savings.mdx"),
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
