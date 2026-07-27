"""ContentRouter must honor skill_preserve and not crush skill bodies."""

from __future__ import annotations

from cutctx.providers import OpenAIProvider
from cutctx.tokenizer import Tokenizer
from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig


def _tokenizer() -> Tokenizer:
    provider = OpenAIProvider()
    return Tokenizer(provider.get_token_counter("gpt-4o"), "gpt-4o")


def test_skill_body_not_aggressively_crushed() -> None:
    skill = (
        "---\nname: cutctx\ndescription: compress bulky outputs\n---\n"
        + ("Rule: always call cutctx_retrieve before quoting.\n" * 40)
    )
    messages = [
        {"role": "system", "content": "Follow installed skills."},
        {"role": "user", "content": skill},
        {
            "role": "user",
            "content": "Summarize the build log:\n" + ("ERROR boom\n" * 200),
        },
    ]
    router = ContentRouter(
        ContentRouterConfig(
            skill_preserve=True,
            skip_user_messages=False,
            min_section_tokens=10,
            min_chars_for_block_compression=100,
        )
    )
    result = router.apply(messages, _tokenizer(), compress_user_messages=True)
    out = result.messages
    joined = "\n".join(
        m["content"] for m in out if isinstance(m, dict) and isinstance(m.get("content"), str)
    )
    assert "always call cutctx_retrieve before quoting" in joined
    assert "name: cutctx" in joined


def test_skill_preserve_config_defaults_on() -> None:
    assert ContentRouterConfig().skill_preserve is True
