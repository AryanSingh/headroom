"""Generates a shareable summary card after CutCtx learn completes."""

from __future__ import annotations

import urllib.parse


def format_twitter_text(n_corrections: int, agent: str, top_fix: str) -> str:
    """Format a tweet-ready summary of learn corrections."""
    if n_corrections == 1:
        return (
            f"\U0001f916 {agent} made a mistake.\n"
            f"cutctx learn auto-fixed it in CLAUDE.md:\n\n"
            f"\u2705 \"{top_fix}\"\n\n"
            f"#cutctx #AIagents github.com/AryanSingh/cutctx"
        )
    return (
        f"\U0001f916 {agent} just made the same mistake for the {n_corrections}th time.\n"
        f"cutctx learn auto-fixed it in CLAUDE.md:\n\n"
        f"\u2705 \"{top_fix}\"\n\n"
        f"+ {n_corrections - 1} other corrections \u2014 automatically.\n"
        f"#cutctx #AIagents github.com/AryanSingh/cutctx"
    )


def print_share_prompt(n: int, agent: str, top_fix: str) -> None:
    """Print a Twitter intent URL for sharing learn results."""
    text = format_twitter_text(n, agent, top_fix)
    url = "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(text)
    print(f"\n\U0001f4ac Share this win:\n{url}\n")
