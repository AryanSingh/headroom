# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Headroom Labs.
"""Share prompt generator for headroom learn.

After a successful `headroom learn --apply`, generates a Twitter-ready
share card showing the number of corrections applied.
"""

from __future__ import annotations

import urllib.parse


def format_twitter_text(n_corrections: int, agent: str, top_fix: str) -> str:
    """Format a tweet-ready summary of learn corrections."""
    if n_corrections == 1:
        return (
            f"\U0001f916 {agent} made a mistake.\n"
            f"headroom learn auto-fixed it in CLAUDE.md:\n\n"
            f'\u2705 "{top_fix}"\n\n'
            f"#headroom #AIagents github.com/headroomlabs/headroom"
        )
    return (
        f"\U0001f916 {agent} just made the same mistake for the {n_corrections}th time.\n"
        f"headroom learn auto-fixed it in CLAUDE.md:\n\n"
        f'\u2705 "{top_fix}"\n\n'
        f"+ {n_corrections - 1} other corrections \u2014 automatically.\n"
        f"#headroom #AIagents github.com/headroomlabs/headroom"
    )


def print_share_prompt(n: int, agent: str, top_fix: str) -> None:
    """Print a Twitter intent URL for sharing learn results."""
    text = format_twitter_text(n, agent, top_fix)
    url = "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(text)
    print(f"\n\U0001f4ac Share this win:\n{url}\n")
