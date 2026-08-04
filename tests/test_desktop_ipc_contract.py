"""Static contract between the Tauri IPC registry and the Control frontend."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "desktop" / "cutctx-control"


def test_every_registered_desktop_command_is_reachable_from_the_frontend() -> None:
    rust = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    frontend = (ROOT / "src" / "App.tsx").read_text(encoding="utf-8")

    handler_match = re.search(r"generate_handler!\[([^]]+)]", rust, re.DOTALL)
    assert handler_match is not None
    registered = {
        name.strip()
        for name in handler_match.group(1).split(",")
        if name.strip()
    }
    invoked = set(re.findall(r"call(?:<[^>]+>)?\(\s*['\"]([^'\"]+)['\"]", frontend))

    assert registered == invoked
