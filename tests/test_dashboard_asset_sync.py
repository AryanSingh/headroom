"""Regression tests for dashboard source-to-package synchronization."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_sync_module():
    path = Path(__file__).parents[1] / "scripts" / "sync_dashboard_assets.py"
    spec = importlib.util.spec_from_file_location("dashboard_asset_sync", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_replaces_stale_hashed_assets_and_copies_entrypoint(tmp_path: Path) -> None:
    sync = _load_sync_module()
    source = tmp_path / "dist"
    source_assets = source / "assets"
    source_assets.mkdir(parents=True)
    (source / "index.html").write_text('<script src="/assets/index-new.js"></script>')
    (source / "favicon.svg").write_text("new-favicon")
    (source_assets / "index-new.js").write_text("new-js")
    (source_assets / "index-new.css").write_text("new-css")

    destination = tmp_path / "package-dashboard"
    stale_assets = destination / "assets"
    stale_assets.mkdir(parents=True)
    (stale_assets / "index-old.js").write_text("old-js")
    (stale_assets / "index-old.css").write_text("old-css")
    (stale_assets / "keep.txt").write_text("keep")

    sync.sync_dashboard_assets(source, destination)

    assert (destination / "index.html").read_text() == '<script src="/assets/index-new.js"></script>'
    assert (destination / "favicon.svg").read_text() == "new-favicon"
    assert (stale_assets / "index-new.js").read_text() == "new-js"
    assert (stale_assets / "index-new.css").read_text() == "new-css"
    assert not (stale_assets / "index-old.js").exists()
    assert not (stale_assets / "index-old.css").exists()
    assert (stale_assets / "keep.txt").exists()


def test_sync_requires_vite_entry_assets(tmp_path: Path) -> None:
    sync = _load_sync_module()
    source = tmp_path / "dist"
    (source / "assets").mkdir(parents=True)

    try:
        sync.sync_dashboard_assets(source, tmp_path / "package-dashboard")
    except FileNotFoundError as exc:
        assert "No Vite entry assets" in str(exc)
    else:
        raise AssertionError("expected missing entry assets to fail")


def test_release_and_container_builds_prepare_dashboard_assets() -> None:
    root = Path(__file__).parents[1]
    for workflow in ("ci.yml", "release.yml"):
        content = (root / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "name: Build dashboard package assets" in content
        assert "npm --prefix dashboard run build" in content
        assert "python scripts/sync_dashboard_assets.py" in content

    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM node:20-bookworm-slim AS dashboard-builder" in dockerfile
    assert "COPY --from=dashboard-builder /dashboard/dist/assets/ cutctx/dashboard/assets/" in dockerfile
