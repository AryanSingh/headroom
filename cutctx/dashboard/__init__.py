"""Cutctx Dashboard - real-time proxy monitoring UI."""

from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"


def get_dashboard_html(*, prefer_react: bool = False) -> str:
    """Load dashboard HTML for the requested runtime.

    The FastAPI server opts into the built React dashboard, while tests and
    single-file callers can keep using the self-contained fallback template by
    default.
    """
    if prefer_react:
        for react_path in (
            DASHBOARD_DIR / "index.html",
            DASHBOARD_DIR / "assets" / "index.html",
        ):
            if react_path.exists():
                return react_path.read_text(encoding="utf-8")

    template_path = TEMPLATES_DIR / "dashboard.html"
    return template_path.read_text(encoding="utf-8")
