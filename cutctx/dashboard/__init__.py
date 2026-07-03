"""Cutctx Dashboard - Real-time proxy monitoring UI."""

from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"


def get_dashboard_html(*, prefer_react: bool = False) -> str:
    """Load dashboard HTML for the requested runtime.

    The FastAPI server can opt into the built React dashboard when bundled
    assets are mounted. Tests and other single-file callers should keep using
    the self-contained fallback template by default.
    """
    if prefer_react:
        # cutctx/dashboard/assets/index.html — the packaged React build output.
        # (dashboard/dist/index.html, the raw Vite build directory, lives
        # outside the cutctx/ package tree and is never included when the
        # package is actually installed, e.g. into a promoted proxy venv —
        # this path must stay inside DASHBOARD_DIR to work post-install.)
        react_path = DASHBOARD_DIR / "assets" / "index.html"
        if react_path.exists():
            return react_path.read_text(encoding="utf-8")

    template_path = TEMPLATES_DIR / "dashboard.html"
    return template_path.read_text(encoding="utf-8")
