from __future__ import annotations

from cutctx.proxy.savings_metadata import merge_savings_metadata


def test_tool_surface_and_schema_savings_are_additive() -> None:
    metadata = merge_savings_metadata(
        {"api_surface_slimming": {"tokens": 120}},
        {"tool_schema_compaction": {"tokens": 45}},
    )

    assert metadata["api_surface_slimming"]["tokens"] == 120
    assert metadata["tool_schema_compaction"]["tokens"] == 45
