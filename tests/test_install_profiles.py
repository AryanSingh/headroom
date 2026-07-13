from __future__ import annotations

from cutctx.cli.capabilities import installation_profiles


def test_install_profiles_expose_explicit_missing_capabilities() -> None:
    rows = [
        {"name": "audio", "available": True},
        {"name": "feedback_loop", "available": True},
        {"name": "benchmark_cli", "available": True},
        {"name": "kompress", "available": True},
        {"name": "smart_crusher", "available": False},
        {"name": "stack_graph", "available": False},
        {"name": "code_ast", "available": False},
        {"name": "html_extractor", "available": False},
        {"name": "llmlingua", "available": False},
        {"name": "relevance", "available": False},
        {"name": "image", "available": False},
        {"name": "log_ml", "available": False},
    ]

    profiles = installation_profiles(rows)

    assert profiles["minimal"]["available"] is True
    assert profiles["proxy"]["available"] is True
    assert profiles["full"]["missing_features"] == [
        "code_ast",
        "html_extractor",
        "llmlingua",
        "relevance",
        "image",
        "log_ml",
    ]
    assert (
        profiles["enterprise"]["install_hint"]
        == "pip install cutctx-ai[proxy,ee,memory,memory-stack]"
    )
