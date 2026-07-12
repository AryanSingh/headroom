from __future__ import annotations

from pathlib import Path

from cutctx.evals.release_manifest import (
    build_release_manifest,
    require_clean_checkout,
    write_release_manifest,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    require_clean_checkout(root)
    fixtures = [
        root / "cutctx" / "evals" / "datasets.py",
        root / "cutctx" / "evals" / "benchmark_runner.py",
        root / "cutctx" / "transforms" / "content_router.py",
        root / "cutctx" / "transforms" / "verbatim_compactor.py",
    ]
    payload = build_release_manifest(
        root=root,
        checkpoint_id="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        seed=42,
        fixture_paths=fixtures,
        provider_arms={
            "raw_passthrough": "available",
            "provider_native_cache_or_compaction": "unavailable",
        },
    )
    write_release_manifest(root / "artifacts" / "benchmark-release-manifest.json", payload)


if __name__ == "__main__":
    main()
