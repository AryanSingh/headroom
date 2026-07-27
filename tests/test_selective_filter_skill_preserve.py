"""Selective filter must retain skill-preserved messages."""

from __future__ import annotations

from cutctx.transforms.selective_filter import SelectiveContextFilter, SelectiveFilterConfig
from cutctx.transforms.skill_preserve import annotate_messages_for_skill_preserve


def test_selective_filter_keeps_skill_messages_even_if_low_relevance() -> None:
    messages = annotate_messages_for_skill_preserve(
        [
            {"role": "system", "content": "You are helpful."},
            {
                "role": "user",
                "content": (
                    "---\nname: db-safety\ndescription: never drop tables\n---\n"
                    "Never run DROP TABLE in production."
                ),
            },
            {"role": "user", "content": "what is the weather in paris?"},
            {"role": "assistant", "content": "I cannot fetch weather."},
            {"role": "user", "content": "ok thanks"},
        ]
    )
    filt = SelectiveContextFilter(SelectiveFilterConfig(min_score=0.99, protect_recent=1))
    kept, _result = filt.filter(messages, query="weather in paris")
    assert any(
        isinstance(m.get("content"), str) and "DROP TABLE" in m["content"] for m in kept
    )
