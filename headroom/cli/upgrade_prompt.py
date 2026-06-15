"""
In-CLI upgrade prompt for CutCtx.

Shows a one-time-per-day upgrade nudge when Builder tier users exceed
500K compressed tokens in a month.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

_PROMPT_DIR = Path(os.environ.get("CUTCTX_DATA_DIR", os.path.expanduser("~/.cutctx")))
_PROMPTED_FILE = _PROMPT_DIR / "prompted_today"


def _get_today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _already_prompted_today() -> bool:
    """Check if we've already shown the upgrade prompt today."""
    if not _PROMPTED_FILE.exists():
        return False
    try:
        stored_key = _PROMPTED_FILE.read_text().strip()
        return stored_key == _get_today_key()
    except Exception:
        return False


def _mark_prompted() -> None:
    """Record that we showed the prompt today."""
    try:
        _PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        _PROMPTED_FILE.write_text(_get_today_key())
    except Exception:
        pass


def maybe_show_upgrade_prompt(tokens_compressed: int, tier: str) -> None:
    """
    Show an upgrade prompt if:
    - tier == 'builder' AND tokens_compressed > 500_000 this month
    - OR if compression fails due to entitlement check

    Prints a one-line message. Only shows once per day.
    """
    if tier.lower() != "builder":
        return

    if tokens_compressed < 500_000:
        return

    if _already_prompted_today():
        return

    print(
        f"\033[33m💡 You've compressed {tokens_compressed:,} tokens this month.\n"
        f"   Upgrade to CutCtx Team for unlimited compression + analytics.\n"
        f"   → cutctx billing checkout --tier team\033[0m"
    )
    _mark_prompted()
