#!/usr/bin/env python3
"""Copy a Vite dashboard build into the Python package deterministically.

The proxy serves ``cutctx/dashboard`` directly from the installed wheel.  A
source-only dashboard build is therefore insufficient: release artifacts must
replace the previous content-hashed JS/CSS assets before Maturin packages them.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def sync_dashboard_assets(source: Path, destination: Path) -> None:
    """Replace packaged JavaScript and CSS assets with the current Vite build."""
    source = source.resolve()
    destination = destination.resolve()
    source_assets = source / "assets"
    entry_assets = [*source_assets.glob("index-*.js"), *source_assets.glob("index-*.css")]
    if not entry_assets:
        raise FileNotFoundError(f"No Vite entry assets found in {source_assets}")
    asset_files = [*source_assets.glob("*.js"), *source_assets.glob("*.css")]

    destination.mkdir(parents=True, exist_ok=True)
    destination_assets = destination / "assets"
    destination_assets.mkdir(exist_ok=True)

    for name in ("index.html", "favicon.svg", "icons.svg"):
        source_file = source / name
        if source_file.is_file():
            shutil.copy2(source_file, destination / name)

    for stale in [*destination_assets.glob("*.js"), *destination_assets.glob("*.css")]:
        stale.unlink()
    for asset in asset_files:
        shutil.copy2(asset, destination_assets / asset.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync built dashboard assets into cutctx package")
    parser.add_argument("--source", type=Path, default=Path("dashboard/dist"))
    parser.add_argument("--destination", type=Path, default=Path("cutctx/dashboard"))
    args = parser.parse_args()
    sync_dashboard_assets(args.source, args.destination)


if __name__ == "__main__":
    main()
