"""Keep the proxy-served dashboard HTML in sync with the Vite output."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_embedded_dashboard_references_an_existing_built_script() -> None:
    html = (ROOT / "cutctx" / "dashboard" / "index.html").read_text(encoding="utf-8")
    match = re.search(r'src="/assets/([^"/]+\.js)"', html)

    assert match, "embedded dashboard must reference a built JavaScript asset"
    assert (ROOT / "cutctx" / "dashboard" / "assets" / match.group(1)).is_file()


def test_embedded_dashboard_matches_vite_output_when_available() -> None:
    """A CI dashboard build must be copied byte-for-byte into the proxy bundle."""
    dist = ROOT / "dashboard" / "dist"
    if not dist.is_dir():
        return

    embedded_html = (ROOT / "cutctx" / "dashboard" / "index.html").read_text(encoding="utf-8")
    vite_html = (dist / "index.html").read_text(encoding="utf-8")
    embedded_assets = set(re.findall(r'(?:src|href)="/assets/([^"/]+\.(?:js|css))"', embedded_html))
    vite_assets = set(re.findall(r'(?:src|href)="/assets/([^"/]+\.(?:js|css))"', vite_html))

    assert embedded_assets == vite_assets
    for asset in vite_assets:
        assert (ROOT / "cutctx" / "dashboard" / "assets" / asset).read_bytes() == (
            dist / "assets" / asset
        ).read_bytes()


def test_dashboard_does_not_depend_on_remote_fonts() -> None:
    """The operator console must render in offline and restricted networks."""
    source_css = (ROOT / "dashboard" / "src" / "index.css").read_text(encoding="utf-8")
    embedded_css = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "cutctx" / "dashboard" / "assets").glob("*.css")
    )

    for css in (source_css, embedded_css):
        assert "fonts.googleapis.com" not in css
        assert "fonts.gstatic.com" not in css
