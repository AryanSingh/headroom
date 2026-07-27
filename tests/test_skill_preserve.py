"""Tests for skill/instruction detection and preservation markers."""

from __future__ import annotations

from cutctx.transforms.skill_preserve import (
    SkillPreserveConfig,
    annotate_messages_for_skill_preserve,
    is_skill_or_instruction_content,
)


def test_detects_skill_frontmatter_and_body() -> None:
    text = "---\nname: cutctx\ndescription: compress bulky tool output\n---\n# Cutctx\nUse cutctx_compress on large logs."
    assert is_skill_or_instruction_content(text) is True


def test_detects_agents_md_style_instructions() -> None:
    text = "# AGENTS\n\nWhen running shell commands, always prefix with `rtk`."
    assert is_skill_or_instruction_content(text) is True


def test_ignores_ordinary_tool_log() -> None:
    text = "INFO starting\n" + ("error line\n" * 200)
    assert is_skill_or_instruction_content(text) is False


def test_annotate_marks_system_and_skill_messages() -> None:
    messages = [
        {"role": "system", "content": "You are a coding agent. Follow SKILL.md rules."},
        {
            "role": "user",
            "content": "---\nname: db-safety\ndescription: never drop tables\n---\nNever run DROP TABLE.",
        },
        {"role": "user", "content": "please fix the flaky test"},
    ]
    out = annotate_messages_for_skill_preserve(
        messages, config=SkillPreserveConfig(enabled=True)
    )
    assert out[0].get("metadata", {}).get("cutctx_skill_preserve") is True
    assert out[1].get("metadata", {}).get("cutctx_skill_preserve") is True
    assert out[2].get("metadata", {}).get("cutctx_skill_preserve") is not True


def test_disabled_config_is_noop() -> None:
    messages = [{"role": "system", "content": "Follow SKILL.md"}]
    out = annotate_messages_for_skill_preserve(
        messages, config=SkillPreserveConfig(enabled=False)
    )
    assert out == messages


def test_tool_role_not_protected_by_mcp_tool_name_markers() -> None:
    """Tool logs mentioning cutctx_compress must not skip compression."""
    messages = [
        {
            "role": "tool",
            "content": "cutctx_compress returned 42% savings on server.log",
        },
        {
            "role": "tool",
            "content": "cutctx_retrieve id=abc123 restored 500 tokens",
        },
    ]
    out = annotate_messages_for_skill_preserve(
        messages, config=SkillPreserveConfig(enabled=True)
    )
    assert out[0].get("metadata", {}).get("cutctx_skill_preserve") is not True
    assert out[1].get("metadata", {}).get("cutctx_skill_preserve") is not True


def test_user_message_needs_explicit_skill_block_not_rtk_marker() -> None:
    """Substring markers like rtk instructions must not protect ordinary user text."""
    messages = [
        {
            "role": "user",
            "content": "Please run cutctx_compress and always prefix with `rtk`.",
        },
    ]
    out = annotate_messages_for_skill_preserve(
        messages, config=SkillPreserveConfig(enabled=True)
    )
    assert out[0].get("metadata", {}).get("cutctx_skill_preserve") is not True
