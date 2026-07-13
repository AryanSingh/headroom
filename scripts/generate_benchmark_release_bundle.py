from __future__ import annotations

from pathlib import Path

from cutctx.evals.release_bundle import build_release_bundle, write_release_bundle


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_release_bundle(
        root / "artifacts" / "benchmark-release-bundle.json",
        build_release_bundle(root),
    )


if __name__ == "__main__":
    main()
