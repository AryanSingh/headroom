"""Asynchronous episodic memory extractor.

Extracts session insights from agent transcripts using a cheap LLM
(claude-3-haiku or equivalent). Designed to run asynchronously after
session termination — never on the hot path.

Usage:
    from headroom.memory.extractor import extract_session_insights

    insights = await extract_session_insights(messages=[
        {"role": "user", "content": "Add dark mode to the dashboard"},
        {"role": "assistant", "content": "I'll create a ThemeContext..."},
        {"role": "user", "content": "Make the toggle animated"},
    ])
    # insights = "## Session Insights\\n- User requested dark mode...\\n..."
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# System prompt for the extraction LLM
_EXTRACTION_SYSTEM_PROMPT = """You are an episodic memory summarizer for an AI coding agent. Review the following agent session transcript and extract concise, actionable insights.

Extract exactly 3 categories:
1. **Key Design Decisions** — architectural choices, technology selections, pattern decisions
2. **Reusable Code Patterns** — specific implementations, configurations, or approaches discovered
3. **Mistakes & Corrections** — errors the agent made and how they were resolved

Format as concise markdown bullet points. Each bullet should be a single, self-contained statement. Be specific (mention file names, function names, library choices). Max 10 bullets total.

If the transcript is too short or contains no meaningful content, return exactly: "No significant insights from this session." """

# Fallback: if no API client is available, do heuristic extraction
_HEURISTIC_SYSTEM_PROMPT = """Extract key facts from this conversation as markdown bullet points."""


def _filter_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter messages to keep only useful content.

    Drops:
    - Tool errors and failed tool outputs
    - Empty messages
    - System messages (these are instructions, not content)
    - Messages that are just thinking blocks
    """
    filtered = []
    for msg in messages:
        role = msg.get("role", "")

        # Skip system messages
        if role == "system":
            continue

        content = msg.get("content", "")

        # Handle string content
        if isinstance(content, str):
            if content.strip():
                filtered.append({"role": role, "content": content.strip()})
            continue

        # Handle list content (Anthropic format)
        if isinstance(content, list):
            text_parts = []
            has_tool_error = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")

                # Skip tool errors
                if block_type == "tool_result" and block.get("is_error"):
                    has_tool_error = True
                    continue

                # Skip thinking blocks
                if block_type == "thinking":
                    continue

                # Extract text content
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "tool_result":
                    # Include successful tool results (they contain useful output)
                    result_content = block.get("content", "")
                    if isinstance(result_content, str) and result_content.strip():
                        text_parts.append(f"[Tool output]: {result_content[:500]}")
                    elif isinstance(result_content, list):
                        for part in result_content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(
                                    f"[Tool output]: {part.get('text', '')[:500]}"
                                )

            if text_parts and not has_tool_error:
                combined = "\n".join(text_parts)
                if combined.strip():
                    filtered.append({"role": role, "content": combined.strip()})

    return filtered


def _format_transcript(messages: list[dict[str, Any]], max_chars: int = 8000) -> str:
    """Format messages into a transcript string for the LLM.

    Truncates to max_chars to keep extraction cost low.
    """
    parts = []
    total = 0

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        prefix = "User" if role == "user" else "Assistant"
        block = f"{prefix}: {content}\n"

        if total + len(block) > max_chars:
            # Truncate to fit
            remaining = max_chars - total
            if remaining > 100:
                parts.append(block[:remaining] + "...[truncated]")
            break

        parts.append(block)
        total += len(block)

    return "\n".join(parts)


async def extract_session_insights(
    messages: list[dict[str, Any]],
    *,
    model: str = "claude-3-haiku-20240307",
    api_key: str | None = None,
    base_url: str | None = None,
    max_chars: int = 8000,
) -> str:
    """Extract episodic memory insights from a session transcript.

    Uses a cheap LLM to analyze the transcript and produce concise
    markdown bullet points covering design decisions, code patterns,
    and mistakes.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        model: Model to use for extraction (default: claude-3-haiku).
        api_key: API key (falls back to ANTHROPIC_API_KEY env var).
        base_url: Optional base URL for the API.
        max_chars: Max characters of transcript to send to the LLM.

    Returns:
        Markdown string with extracted insights, or empty string on failure.
    """
    if not messages:
        return ""

    # Filter to useful messages
    filtered = _filter_messages(messages)
    if not filtered:
        logger.debug("EpisodicExtractor: no useful messages after filtering")
        return ""

    # Format transcript
    transcript = _format_transcript(filtered, max_chars=max_chars)
    if not transcript.strip():
        return ""

    # Try LLM extraction
    try:
        insights = await _llm_extract(
            transcript,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        if insights:
            return insights
    except Exception as e:
        logger.warning("EpisodicExtractor: LLM extraction failed: %s", e)

    # Fallback: heuristic extraction
    return _heuristic_extract(filtered)


async def _llm_extract(
    transcript: str,
    *,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> str:
    """Call the LLM API to extract insights."""
    import httpx

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.debug("EpisodicExtractor: no API key available")
        return ""

    url = (base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"

    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": _EXTRACTION_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": transcript}],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()

        data = resp.json()
        content_blocks = data.get("content", [])
        text_parts = [
            b.get("text", "") for b in content_blocks if b.get("type") == "text"
        ]
        return "\n".join(text_parts).strip()


def _heuristic_extract(messages: list[dict[str, Any]]) -> str:
    """Fallback heuristic extraction when no LLM is available.

    Extracts simple patterns: file mentions, error messages, user requests.
    """
    insights: list[str] = []
    user_requests: list[str] = []
    file_mentions: list[str] = []
    errors: list[str] = []

    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "")

        # Extract user requests (simple heuristic: messages starting with verbs)
        if role == "user":
            first_word = content.split()[0].lower() if content.split() else ""
            if first_word in ("add", "create", "fix", "update", "change", "make", "implement", "remove", "delete", "set", "configure"):
                user_requests.append(content[:200])

        # Extract file mentions
        import re
        file_matches = re.findall(r'[\w/.-]+\.(?:py|rs|js|ts|jsx|tsx|go|java|rb|css|html|json|yaml|yml|toml|md)', content)
        file_mentions.extend(file_matches[:5])

        # Extract error-related content
        if role == "assistant" and ("error" in content.lower() or "fix" in content.lower()):
            # Get the first sentence mentioning error/fix
            sentences = content.split(". ")
            for s in sentences:
                if "error" in s.lower() or "fix" in s.lower():
                    errors.append(s[:200])
                    break

    # Format output
    output_parts = ["## Session Insights\n"]

    if user_requests:
        output_parts.append("**Key Requests:**")
        for req in user_requests[:5]:
            output_parts.append(f"- {req}")
        output_parts.append("")

    if file_mentions:
        unique_files = list(dict.fromkeys(file_mentions))  # dedupe preserving order
        output_parts.append(f"**Files Modified:** {', '.join(unique_files[:10])}")
        output_parts.append("")

    if errors:
        output_parts.append("**Issues Resolved:**")
        for err in errors[:3]:
            output_parts.append(f"- {err}")
        output_parts.append("")

    if len(output_parts) == 1:
        return ""

    return "\n".join(output_parts)


def format_memory_block(insights: str, project_path: str = "") -> str:
    """Format extracted insights as a memory block for injection.

    Wraps insights in the ``[SYSTEM: Past Session Memories]`` tag that
    the Rust classifier detects for CCR compression.

    Args:
        insights: Markdown insights from extract_session_insights.
        project_path: Optional project path for metadata.

    Returns:
        Formatted memory block string.
    """
    if not insights or not insights.strip():
        return ""

    header = "[SYSTEM: Past Session Memories]"
    meta = "<!-- source: episodic_extractor -->"
    if project_path:
        meta = f"<!-- source: episodic_extractor, project: {project_path} -->"

    return f"{header}\n{meta}\n\n{insights.strip()}\n"
