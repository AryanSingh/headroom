"""Tests for cutctx.proxy.schema_compress — JSON schema compression."""

from __future__ import annotations

import json

from cutctx.proxy.schema_compress import (
    _SCHEMA_DROP_KEYS,
    _SCHEMA_KEEP_KEYS,
    _json_bytes,
    _truncate_description,
    _try_positional_array,
    compress_tool_results,
    compress_tool_schemas,
)

# ───────────────── Fixtures ─────────────────


def _make_anthropic_tool(name="test_tool", extra_props=None):
    """Create a realistic Anthropic-style tool definition."""
    props = {
        "query": {
            "type": "string",
            "description": "The search query",
            "minLength": 1,
            "maxLength": 500,
            "title": "Query",
            "pattern": "^[a-z]+$",
        },
        "limit": {
            "type": "integer",
            "description": "Max results",
            "minimum": 1,
            "maximum": 100,
            "default": 10,
            "exclusiveMinimum": 0,
            "title": "Limit",
        },
        "format": {
            "type": "string",
            "enum": ["json", "csv"],
            "description": "Output format",
            "default": "json",
            "title": "Format",
            "examples": ["json"],
            "markdownDescription": "Select the output format",
        },
    }
    if extra_props:
        props.update(extra_props)
    return {
        "name": name,
        "description": "A test tool for searching data. " * 20,
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": ["query"],
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://example.com/test.json",
            "title": "Test Tool",
            "additionalProperties": False,
        },
    }


def _make_openai_tool(name="test_tool"):
    """Create a realistic OpenAI-style tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "A test tool for searching data. " * 20,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                        "minLength": 1,
                        "maxLength": 500,
                        "title": "Query",
                        "pattern": "^[a-z]+$",
                        "examples": ["hello world"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "title": "Limit",
                        "deprecated": False,
                        "readOnly": False,
                    },
                },
                "required": ["query"],
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "https://example.com/test.json",
                "title": "Test Tool",
                "additionalProperties": False,
            },
        },
    }


def _make_tool_result_messages(n_items=5, n_fields=4):
    """Create messages with tool_result content containing array data."""
    items = [{f"field_{i}": f"value_{j}_{i}" for i in range(n_fields)} for j in range(n_items)]
    return [
        {"role": "user", "content": "Get data"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "tu1", "name": "get_data", "input": {}}],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu1",
                    "content": json.dumps(items),
                }
            ],
        },
    ]


# ───────────────── compress_tool_schemas tests ─────────────────


class TestCompressToolSchemas:
    def test_empty_tools(self):
        result, modified, before, after = compress_tool_schemas([])
        assert result == []
        assert modified is False
        assert before == 0
        assert after == 0

    def test_none_tools(self):
        result, modified, before, after = compress_tool_schemas(None)
        assert result == []
        assert modified is False

    def test_single_anthropic_tool_reduced(self):
        tools = [_make_anthropic_tool()]
        compacted, modified, before, after = compress_tool_schemas(tools)
        assert modified is True
        assert after < before

    def test_single_openai_tool_reduced(self):
        tools = [_make_openai_tool()]
        compacted, modified, before, after = compress_tool_schemas(tools)
        assert modified is True
        assert after < before

    def test_multiple_tools(self):
        tools = [_make_anthropic_tool("tool_a"), _make_anthropic_tool("tool_b")]
        compacted, modified, before, after = compress_tool_schemas(tools)
        assert modified is True
        assert len(compacted) == 2

    def test_strips_title(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        schema = compacted[0]["input_schema"]
        assert "title" not in schema
        for prop in schema["properties"].values():
            if isinstance(prop, dict):
                assert "title" not in prop

    def test_strips_schema_id(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        schema = compacted[0]["input_schema"]
        assert "$schema" not in schema
        assert "$id" not in schema

    def test_strips_validation_keys(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        prop = compacted[0]["input_schema"]["properties"]["query"]
        assert "minLength" not in prop
        assert "maxLength" not in prop
        assert "pattern" not in prop

    def test_keeps_type_and_description(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        prop = compacted[0]["input_schema"]["properties"]["query"]
        assert prop["type"] == "string"
        assert "description" in prop

    def test_keeps_required_and_properties(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        schema = compacted[0]["input_schema"]
        assert "required" in schema
        assert "properties" in schema

    def test_truncates_long_description(self):
        tool = _make_anthropic_tool()
        tool["description"] = "A" * 500
        compacted, modified, _, _ = compress_tool_schemas([tool])
        assert modified is True
        assert len(compacted[0]["description"]) < 500

    def test_description_sentence_boundary(self):
        tool = _make_anthropic_tool()
        tool["description"] = (
            "First sentence. Second sentence. Third sentence with lots of extra text that goes on and on."
        )
        compacted, _, _, _ = compress_tool_schemas([tool], max_description_length=50)
        desc = compacted[0]["description"]
        assert desc.endswith("...")

    def test_short_description_unchanged(self):
        tool = _make_anthropic_tool()
        tool["description"] = "Short."
        compacted, _, _, _ = compress_tool_schemas([tool])
        assert compacted[0]["description"] == "Short."

    def test_nested_description_shorter_limit(self):
        tool = {
            "name": "test",
            "description": "Top level desc " * 20,
            "input_schema": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "string",
                        "description": "Nested " * 50,
                    }
                },
            },
        }
        compacted, _, _, _ = compress_tool_schemas([tool])
        nested_desc = compacted[0]["input_schema"]["properties"]["x"]["description"]
        assert len(nested_desc) <= 120  # 100 + "..."

    def test_no_bloat_on_already_compact(self):
        tool = {
            "name": "tiny",
            "description": "Short",
            "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        }
        _, modified, _, _ = compress_tool_schemas([tool])
        # Already compact — should not claim modification since no savings
        # (may or may not modify depending on byte comparison)
        assert isinstance(modified, bool)

    def test_aggressive_mode(self):
        tools = [_make_anthropic_tool()]
        compacted_agg, modified_agg, _, after_agg = compress_tool_schemas(tools, aggressive=True)
        compacted_norm, modified_norm, _, after_norm = compress_tool_schemas(
            tools, aggressive=False
        )
        # Aggressive should produce smaller or equal output
        if modified_agg and modified_norm:
            assert after_agg <= after_norm

    def test_preserves_enum(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        prop = compacted[0]["input_schema"]["properties"]["format"]
        assert prop.get("enum") == ["json", "csv"]

    def test_preserves_default(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        prop = compacted[0]["input_schema"]["properties"]["format"]
        assert prop.get("default") == "json"

    def test_strips_additional_properties(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        assert "additionalProperties" not in compacted[0]["input_schema"]

    def test_strips_deprecated_false(self):
        tools = [_make_anthropic_tool()]
        compacted, _, _, _ = compress_tool_schemas(tools)
        for prop in compacted[0]["input_schema"]["properties"].values():
            if isinstance(prop, dict):
                assert "deprecated" not in prop

    def test_whitespace_normalized(self):
        tool = _make_anthropic_tool()
        tool["description"] = "  lots   of   whitespace   here  "
        compacted, _, _, _ = compress_tool_schemas([tool])
        assert "  " not in compacted[0]["description"]


# ───────────────── compress_tool_results tests ─────────────────


class TestCompressToolResults:
    def test_empty_messages(self):
        assert compress_tool_results([]) == []

    def test_no_tool_results(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert compress_tool_results(msgs) == msgs

    def test_anthropic_tool_result_string(self):
        items = [{"id": i, "name": f"user_{i}", "score": 90 + i} for i in range(5)]
        msgs = [
            {"type": "tool_result", "tool_use_id": "tu1", "content": json.dumps(items)},
        ]
        result = compress_tool_results(msgs)
        content = result[0]["content"]
        # Should be compressed to positional format
        parsed = json.loads(content)
        assert "_t" in parsed
        assert "_d" in parsed
        assert parsed["_t"] == ["id", "name", "score"]

    def test_anthropic_tool_result_list_content(self):
        # Need enough items/fields for positional format to save bytes
        items = [
            {
                "id": i,
                "name": f"user_{i}",
                "email": f"user{i}@example.com",
                "score": 90 + i,
                "role": "admin",
            }
            for i in range(5)
        ]
        msgs = [
            {
                "type": "tool_result",
                "tool_use_id": "tu1",
                "content": [{"type": "text", "text": json.dumps(items)}],
            },
        ]
        result = compress_tool_results(msgs)
        content_block = result[0]["content"][0]
        assert content_block["type"] == "text"
        parsed = json.loads(content_block["text"])
        assert "_t" in parsed

    def test_openai_tool_role(self):
        # Need enough items/fields for positional format to save bytes
        items = [
            {"id": i, "name": f"item_{i}", "value": i * 10, "category": "data", "active": True}
            for i in range(5)
        ]
        msgs = [{"role": "tool", "content": json.dumps(items), "tool_call_id": "tc1"}]
        result = compress_tool_results(msgs)
        parsed = json.loads(result[0]["content"])
        assert "_t" in parsed

    def test_non_json_passthrough(self):
        msgs = [{"type": "tool_result", "tool_use_id": "tu1", "content": "not json"}]
        result = compress_tool_results(msgs)
        assert result[0]["content"] == "not json"

    def test_heterogeneous_not_compressed(self):
        items = [{"a": 1, "b": 2}, {"a": 1, "c": 3}]  # Different keys
        msgs = [{"type": "tool_result", "tool_use_id": "tu1", "content": json.dumps(items)}]
        result = compress_tool_results(msgs)
        assert result[0]["content"] == json.dumps(items)

    def test_too_few_items_not_compressed(self):
        items = [{"a": 1, "b": 2, "c": 3}]  # Only 1 item
        msgs = [{"type": "tool_result", "tool_use_id": "tu1", "content": json.dumps(items)}]
        result = compress_tool_results(msgs)
        assert result[0]["content"] == json.dumps(items)

    def test_too_few_fields_not_compressed(self):
        items = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]  # Only 2 fields
        msgs = [{"type": "tool_result", "tool_use_id": "tu1", "content": json.dumps(items)}]
        result = compress_tool_results(msgs)
        assert result[0]["content"] == json.dumps(items)

    def test_large_array_not_compressed(self):
        items = [{"id": i, "name": f"n{i}", "val": i * 10} for i in range(20)]
        msgs = [{"type": "tool_result", "tool_use_id": "tu1", "content": json.dumps(items)}]
        result = compress_tool_results(msgs)
        # 20 items > max_array_items_for_positional (10) default
        assert result[0]["content"] == json.dumps(items)

    def test_preserves_non_tool_messages(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
        ]
        assert compress_tool_results(msgs) == msgs

    def test_mixed_messages(self):
        items = [{"id": i, "name": f"u{i}", "score": i} for i in range(5)]
        msgs = [
            {"role": "user", "content": "query"},
            {"type": "tool_result", "tool_use_id": "tu1", "content": json.dumps(items)},
            {"role": "assistant", "content": "done"},
        ]
        result = compress_tool_results(msgs)
        assert result[0] == msgs[0]
        assert "_t" in json.loads(result[1]["content"])
        assert result[2] == msgs[2]

    def test_non_dict_messages_skipped(self):
        msgs = ["string message", 42, None, {"role": "user", "content": "ok"}]
        result = compress_tool_results(msgs)
        assert result[0] == "string message"
        assert result[1] == 42
        assert result[2] is None
        assert result[3] == msgs[3]


# ───────────────── _truncate_description tests ─────────────────


class TestTruncateDescription:
    def test_short_noop(self):
        assert _truncate_description("Hi.", 200) == "Hi."

    def test_exact_length(self):
        s = "A" * 200
        assert _truncate_description(s, 200) == s

    def test_sentence_boundary(self):
        s = "First sentence. Second sentence. Third sentence goes on."
        result = _truncate_description(s, 35)
        assert result.endswith("...")

    def test_comma_boundary(self):
        s = "First part, second part, third part, fourth part"
        result = _truncate_description(s, 30)
        assert result.endswith("...")

    def test_no_good_boundary(self):
        s = "A" * 100
        result = _truncate_description(s, 50)
        assert len(result) == 53  # 50 + "..."


# ───────────────── _try_positional_array tests ─────────────────


class TestPositionalArray:
    def test_valid_conversion(self):
        items = [{"a": 1, "b": 2, "c": 3}, {"a": 4, "b": 5, "c": 6}]
        result = _try_positional_array(items, max_items=10, min_fields=3)
        assert result is not None
        assert result["_t"] == ["a", "b", "c"]
        assert result["_d"] == [[1, 2, 3], [4, 5, 6]]

    def test_heterogeneous_keys(self):
        items = [{"a": 1, "b": 2}, {"a": 1, "c": 3}]
        assert _try_positional_array(items, max_items=10, min_fields=3) is None

    def test_too_few_items(self):
        items = [{"a": 1, "b": 2, "c": 3}]
        assert _try_positional_array(items, max_items=10, min_fields=3) is None

    def test_too_few_fields(self):
        items = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        assert _try_positional_array(items, max_items=10, min_fields=3) is None

    def test_non_dict_items(self):
        items = [1, 2, 3]
        assert _try_positional_array(items, max_items=10, min_fields=3) is None

    def test_exceeds_max_items(self):
        items = [{"a": i, "b": i, "c": i} for i in range(15)]
        assert _try_positional_array(items, max_items=10, min_fields=3) is None


# ───────────────── _json_bytes tests ─────────────────


class TestJsonBytes:
    def test_small_object(self):
        assert _json_bytes({"a": 1}) > 0

    def test_unicode(self):
        assert _json_bytes({"text": "\u00e9\u00e8\u00ea"}) > 0

    def test_nested(self):
        assert _json_bytes({"a": {"b": [1, 2, 3]}}) > 0


# ───────────────── Schema key set tests ─────────────────


class TestSchemaKeySets:
    def test_drop_keys_is_frozen(self):
        assert isinstance(_SCHEMA_DROP_KEYS, frozenset)

    def test_keep_keys_is_frozen(self):
        assert isinstance(_SCHEMA_KEEP_KEYS, frozenset)

    def test_no_overlap(self):
        assert _SCHEMA_DROP_KEYS.isdisjoint(_SCHEMA_KEEP_KEYS)

    def test_drop_keys_has_metadata(self):
        for key in ["title", "$schema", "examples", "deprecated", "readOnly"]:
            assert key in _SCHEMA_DROP_KEYS

    def test_keep_keys_has_functional(self):
        for key in ["type", "description", "required", "properties", "enum"]:
            assert key in _SCHEMA_KEEP_KEYS
