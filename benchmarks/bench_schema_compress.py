#!/usr/bin/env python3
"""Benchmark: JSON schema compression for LLM tool definitions.

Measures token savings from Cutctx schema compression on realistic tool schemas.
Compares against uncompressed baseline and old 10-key OpenAI drop list.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cutctx.proxy.schema_compress import (
    _SCHEMA_DROP_KEYS,
    compress_tool_results,
    compress_tool_schemas,
)

# ─── Realistic tool schemas (from production APIs) ───

ANTHROPIC_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a given location. Returns temperature, humidity, wind speed, and conditions. Supports both metric and imperial units. Includes sunrise/sunset times and UV index when available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                    "minLength": 2,
                    "maxLength": 200,
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit",
                    "default": "celsius",
                    "title": "Temperature Unit",
                    "examples": ["celsius", "fahrenheit"],
                    "markdownDescription": "Select the temperature unit for display",
                },
                "include_forecast": {
                    "type": "boolean",
                    "description": "Whether to include a 5-day forecast",
                    "default": False,
                    "title": "Include Forecast",
                    "deprecated": False,
                    "readOnly": False,
                },
            },
            "required": ["location"],
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://example.com/weather.json",
            "title": "Weather Request",
            "additionalProperties": False,
        },
    },
    {
        "name": "search_documents",
        "description": "Search through a document corpus using semantic search. Returns ranked results with relevance scores and context snippets. Supports filtering by date range, document type, and author. Maximum 100 results per query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                    "minLength": 1,
                    "maxLength": 1000,
                    "pattern": "^[a-zA-Z0-9 ]+$",
                    "title": "Search Query",
                    "examples": ["quarterly revenue report"],
                    "markdownDescription": "Enter your search terms",
                },
                "filters": {
                    "type": "object",
                    "description": "Optional filters to narrow results",
                    "properties": {
                        "date_from": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Start of date range (ISO 8601)",
                            "title": "Start Date",
                        },
                        "date_to": {
                            "type": "string",
                            "format": "date-time",
                            "description": "End of date range (ISO 8601)",
                            "title": "End Date",
                        },
                        "doc_type": {
                            "type": "string",
                            "enum": ["pdf", "docx", "txt", "md", "html"],
                            "description": "Filter by document type",
                            "title": "Document Type",
                            "examples": ["pdf", "docx"],
                        },
                        "author": {
                            "type": "string",
                            "description": "Filter by author name",
                            "minLength": 2,
                            "maxLength": 100,
                            "title": "Author Filter",
                        },
                    },
                    "additionalProperties": False,
                    "minProperties": 1,
                    "maxProperties": 10,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "title": "Max Results",
                    "exclusiveMinimum": 0,
                    "exclusiveMaximum": 200,
                },
                "include_snippets": {
                    "type": "boolean",
                    "description": "Include context snippets in results",
                    "default": True,
                    "title": "Include Snippets",
                },
            },
            "required": ["query"],
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://example.com/search.json",
            "title": "Document Search",
            "anyOf": [{"required": ["query"]}, {"required": ["filters"]}],
        },
    },
    {
        "name": "create_ticket",
        "description": "Create a new support ticket in the ticketing system. Assigns priority, category, and optional SLA based on severity level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Brief description of the issue",
                    "minLength": 5,
                    "maxLength": 200,
                    "title": "Subject",
                },
                "body": {
                    "type": "string",
                    "description": "Detailed description of the issue including steps to reproduce",
                    "minLength": 20,
                    "maxLength": 10000,
                    "title": "Body",
                    "markdownDescription": "Provide a detailed description of the issue",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Issue priority level",
                    "default": "medium",
                    "title": "Priority",
                    "examples": ["high", "critical"],
                    "deprecated": False,
                },
                "category": {
                    "type": "string",
                    "enum": ["bug", "feature", "question", "incident"],
                    "description": "Issue category",
                    "title": "Category",
                    "readOnly": False,
                },
                "assignee": {
                    "type": "string",
                    "description": "Email of the person to assign the ticket to",
                    "format": "email",
                    "title": "Assignee",
                    "writeOnly": False,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 50},
                    "description": "Tags for categorization",
                    "maxItems": 10,
                    "uniqueItems": True,
                    "title": "Tags",
                },
            },
            "required": ["subject", "body", "priority"],
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://example.com/ticket.json",
            "title": "Create Ticket",
        },
    },
    {
        "name": "analyze_code",
        "description": "Perform static analysis on a code snippet. Checks for bugs, style issues, security vulnerabilities, and performance problems.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The source code to analyze",
                    "minLength": 1,
                    "maxLength": 50000,
                    "title": "Source Code",
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript", "go", "rust", "java"],
                    "description": "Programming language of the code",
                    "title": "Language",
                    "examples": ["python", "typescript"],
                    "markdownDescription": "Select the language for analysis",
                },
                "checks": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["bugs", "style", "security", "performance", "complexity"],
                    },
                    "description": "Which analysis checks to run",
                    "minItems": 1,
                    "maxItems": 5,
                    "default": ["bugs", "security"],
                    "title": "Analysis Checks",
                    "deprecated": False,
                },
                "severity_threshold": {
                    "type": "string",
                    "enum": ["info", "warning", "error", "critical"],
                    "description": "Minimum severity level to report",
                    "default": "warning",
                    "title": "Severity Threshold",
                    "readOnly": False,
                    "writeOnly": False,
                },
            },
            "required": ["code", "language"],
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://example.com/analyze.json",
            "title": "Code Analysis",
        },
    },
]


OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Retrieve the current stock price for a given ticker symbol. Returns price, volume, market cap, and 24h change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., AAPL, GOOGL, MSFT)",
                        "pattern": "^[A-Z]{1,5}$",
                        "title": "Ticker Symbol",
                        "examples": ["AAPL", "GOOGL"],
                        "minLength": 1,
                        "maxLength": 5,
                    },
                    "include_history": {
                        "type": "boolean",
                        "description": "Include 30-day price history",
                        "default": False,
                        "title": "Include History",
                        "deprecated": False,
                    },
                    "currency": {
                        "type": "string",
                        "enum": ["USD", "EUR", "GBP", "JPY"],
                        "description": "Output currency",
                        "default": "USD",
                        "title": "Currency",
                        "markdownDescription": "Select output currency",
                        "readOnly": False,
                    },
                },
                "required": ["ticker"],
                "additionalProperties": False,
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "https://example.com/stock.json",
                "title": "Stock Price Request",
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email via the configured SMTP server. Supports plain text and HTML content. Can include CC/BCC recipients and file attachments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string", "format": "email"},
                        "description": "Recipient email addresses",
                        "minItems": 1,
                        "maxItems": 50,
                        "title": "Recipients",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                        "minLength": 1,
                        "maxLength": 998,
                        "title": "Subject",
                        "examples": ["Weekly Report", "Meeting Reminder"],
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text or HTML)",
                        "minLength": 1,
                        "maxLength": 100000,
                        "title": "Body",
                        "markdownDescription": "Email content in plain text or HTML format",
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string", "format": "email"},
                        "description": "CC recipients",
                        "maxItems": 50,
                        "title": "CC",
                        "deprecated": False,
                        "writeOnly": False,
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "description": "Email priority",
                        "default": "normal",
                        "title": "Priority",
                    },
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "https://example.com/email.json",
                "title": "Send Email",
            },
        },
    },
]


# ─── Old OpenAI 10-key drop list (for comparison) ───

_OLD_DROP_KEYS = {
    "$id",
    "$schema",
    "$comment",
    "deprecated",
    "examples",
    "example",
    "markdownDescription",
    "readOnly",
    "title",
    "writeOnly",
}


def _apply_old_drop(tools):
    """Simulate the OLD OpenAI tool schema compaction (10-key drop only)."""

    def _drop(obj):
        if isinstance(obj, list):
            return [_drop(x) for x in obj]
        if not isinstance(obj, dict):
            return obj
        return {k: _drop(v) for k, v in obj.items() if k not in _OLD_DROP_KEYS}

    return _drop(tools)


def _json_bytes(obj):
    return len(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _estimate_tokens(obj):
    """Rough token estimate: chars / 4."""
    return _json_bytes(obj) // 4


def run_benchmark():
    print("=" * 80)
    print("Cutctx JSON Schema Compression Benchmark")
    print("=" * 80)

    # ─── Benchmark 1: Anthropic tools ───
    print("\n─── Anthropic Tool Schemas (4 tools) ───")
    before = _json_bytes(ANTHROPIC_TOOLS)
    after_old = _json_bytes(_apply_old_drop(ANTHROPIC_TOOLS))
    compacted, modified, _, after_new = compress_tool_schemas(ANTHROPIC_TOOLS)

    print(f"  Original:     {before:>6} bytes  (~{_estimate_tokens(ANTHROPIC_TOOLS):>4} tokens)")
    print(
        f"  Old (10-key): {after_old:>6} bytes  (~{_estimate_tokens(_apply_old_drop(ANTHROPIC_TOOLS)):>4} tokens)  ({(1 - after_old / before) * 100:.1f}% savings)"
    )
    if modified:
        print(
            f"  New (30-key): {after_new:>6} bytes  (~{_estimate_tokens(compacted):>4} tokens)  ({(1 - after_new / before) * 100:.1f}% savings)"
        )
    else:
        print("  New (30-key): no change")

    # ─── Benchmark 2: OpenAI tools ───
    print("\n─── OpenAI Tool Schemas (2 tools) ───")
    before = _json_bytes(OPENAI_TOOLS)
    after_old = _json_bytes(_apply_old_drop(OPENAI_TOOLS))
    compacted, modified, _, after_new = compress_tool_schemas(OPENAI_TOOLS)

    print(f"  Original:     {before:>6} bytes  (~{_estimate_tokens(OPENAI_TOOLS):>4} tokens)")
    print(
        f"  Old (10-key): {after_old:>6} bytes  (~{_estimate_tokens(_apply_old_drop(OPENAI_TOOLS)):>4} tokens)  ({(1 - after_old / before) * 100:.1f}% savings)"
    )
    if modified:
        print(
            f"  New (30-key): {after_new:>6} bytes  (~{_estimate_tokens(compacted):>4} tokens)  ({(1 - after_new / before) * 100:.1f}% savings)"
        )
    else:
        print("  New (30-key): no change")

    # ─── Benchmark 3: Combined (realistic agent call) ───
    print("\n─── Combined: 4 Anthropic + 2 OpenAI tools ───")
    all_tools = ANTHROPIC_TOOLS + OPENAI_TOOLS
    before = _json_bytes(all_tools)
    after_old = _json_bytes(_apply_old_drop(all_tools))
    compacted, modified, _, after_new = compress_tool_schemas(all_tools)

    print(f"  Original:     {before:>6} bytes  (~{_estimate_tokens(all_tools):>4} tokens)")
    print(
        f"  Old (10-key): {after_old:>6} bytes  (~{_estimate_tokens(_apply_old_drop(all_tools)):>4} tokens)  ({(1 - after_old / before) * 100:.1f}% savings)"
    )
    if modified:
        print(
            f"  New (30-key): {after_new:>6} bytes  (~{_estimate_tokens(compacted):>4} tokens)  ({(1 - after_new / before) * 100:.1f}% savings)"
        )

    # ─── Benchmark 4: Tool results compression ───
    print("\n─── Tool Results: Homogeneous Array Compression ───")
    for n_items, n_fields in [(5, 4), (10, 6), (20, 8)]:
        items = [{f"field_{j}": f"value_{i}_{j}" for j in range(n_fields)} for i in range(n_items)]
        items_json = json.dumps(items)
        msgs = [{"type": "tool_result", "tool_use_id": "tu1", "content": items_json}]
        result = compress_tool_results(msgs)
        compressed_json = result[0]["content"]
        original_bytes = len(items_json.encode("utf-8"))
        compressed_bytes = len(compressed_json.encode("utf-8"))
        if compressed_bytes < original_bytes:
            print(
                f"  {n_items} items × {n_fields} fields: {original_bytes:>5} → {compressed_bytes:>5} bytes ({(1 - compressed_bytes / original_bytes) * 100:.1f}% savings)"
            )
        else:
            print(
                f"  {n_items} items × {n_fields} fields: {original_bytes:>5} → {compressed_bytes:>5} bytes (no savings — overhead exceeds savings)"
            )

    # ─── Benchmark 5: Throughput ───
    print("\n─── Throughput ───")
    n_iter = 1000
    t0 = time.perf_counter()
    for _ in range(n_iter):
        compress_tool_schemas(ANTHROPIC_TOOLS)
    elapsed = time.perf_counter() - t0
    print(
        f"  Schema compression: {n_iter / elapsed:.0f} calls/sec ({elapsed / n_iter * 1000:.2f} ms/call)"
    )

    t0 = time.perf_counter()
    for _ in range(n_iter):
        compress_tool_schemas(OPENAI_TOOLS)
    elapsed = time.perf_counter() - t0
    print(
        f"  OpenAI tools:       {n_iter / elapsed:.0f} calls/sec ({elapsed / n_iter * 1000:.2f} ms/call)"
    )

    # ─── Summary ───
    print("\n─── Key Metrics ───")
    print(f"  Drop keys: {len(_SCHEMA_DROP_KEYS)} (vs old: {len(_OLD_DROP_KEYS)})")
    print("  Description truncation: 200 chars (nested: 100)")
    print("  Positional array: ≥2 items × ≥3 fields")
    print("  Overhead guard: no modification if compressed >= original")


if __name__ == "__main__":
    run_benchmark()
