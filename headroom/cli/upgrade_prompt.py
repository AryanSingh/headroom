"""
Upgrade prompt for Builder-tier users approaching free tier limits.
Shown at most once per day to avoid spamming.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

MONTHLY_FREE_TOKENS = 500_000
_PROMPT_FLAG_DIR = Path.home() / ".cutctx"
_PROMPT_FLAG_FILE = _PROMPT_FLAG_DIR / "prompted_today"


def _was_prompted_today() -> bool:
    """Return True if we already showed the prompt today."""
    try:
        if _PROMPT_FLAG_FILE.exists():
            return _PROMPT_FLAG_FILE.read_text().strip() == str(date.today())
    except OSError:
        pass
    return False


def _mark_prompted() -> None:
    """Write today's date to the flag file."""
    try:
        _PROMPT_FLAG_DIR.mkdir(parents=True, exist_ok=True)
        _PROMPT_FLAG_FILE.write_text(str(date.today()))
    except OSError:
        pass


def maybe_show_upgrade_prompt(tokens_compressed_this_month: int, tier: str) -> None:
    """
    Show upgrade nudge if:
    - tier == 'builder' (free tier)
    - tokens_compressed_this_month >= MONTHLY_FREE_TOKENS
    - Haven't shown the prompt today

    Prints to stderr so it doesn't interfere with stdout pipeline output.
    """
    if tier.lower() != "builder":
        return
    if tokens_compressed_this_month < MONTHLY_FREE_TOKENS:
        return
    if _was_prompted_today():
        return

    _mark_prompted()

    # Use ANSI yellow if stderr is a terminal
    use_color = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    start = "\033[33m" if use_color else ""
    end = "\033[0m" if use_color else ""

    print(
        f"\n{start}💡 You've compressed {tokens_compressed_this_month:,}+ tokens this month "
        f"(free tier: {MONTHLY_FREE_TOKENS:,} tokens/month).{end}\n"
        f"   Upgrade to CutCtx Team for unlimited compression + savings analytics.\n"
        f"   → cutctx billing checkout --tier team\n",
        file=sys.stderr,
    )
