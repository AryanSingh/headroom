#!/usr/bin/env python3
"""
Cutctx MCP server — run as: python3 -m cutctx.mcp_server

Exposes seven tools to Claude and other MCP clients:
  - cutctx_retrieve    : fetch original content from a CCR compression marker
  - cutctx_status      : check proxy health + compression stats
  - cutctx_proxy_start : manually start the proxy
  - cutctx_compress    : compress text via Cutctx proxy
  - cutctx_scan        : scan text for security violations (PII, injection)
  - cutctx_audit       : query audit log events
  - cutctx_orgs        : list or create organizations

Set CUTCTX_AUTO_START=1 (default) to auto-start the proxy on first tool call.
Set CUTCTX_PROXY_URL to override the default http://127.0.0.1:8787.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import httpx
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

PROXY_URL = os.getenv("CUTCTX_PROXY_URL", "http://127.0.0.1:8787")
AUTO_START = os.getenv("CUTCTX_AUTO_START", "1") == "1"

server = Server("cutctx")


# ---------------------------------------------------------------------------
# Proxy lifecycle helpers
# ---------------------------------------------------------------------------

async def _check_proxy() -> bool:
    """Return True if the Cutctx proxy is reachable."""
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{PROXY_URL}/health")
            return r.status_code < 400
    except Exception:
        return False


async def _start_proxy() -> bool:
    """Attempt to start the Cutctx proxy. Returns True if it comes up."""
    candidates = [
        ["cutctx", "proxy"],
        [sys.executable, "-m", "cutctx.cli", "proxy"],
    ]
    for cmd in candidates:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Poll until healthy (up to 10 seconds)
            for _ in range(20):
                await asyncio.sleep(0.5)
                if await _check_proxy():
                    return True
        except FileNotFoundError:
            continue
    return False


async def _ensure_proxy() -> bool:
    """Ensure the proxy is running if AUTO_START is enabled."""
    if not AUTO_START:
        return await _check_proxy()
    if await _check_proxy():
        return True
    return await _start_proxy()


def _admin_headers() -> dict[str, str]:
    """Build admin auth headers from environment."""
    key = os.getenv("CUTCTX_ADMIN_API_KEY", "")
    headers: dict[str, str] = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="cutctx_retrieve",
            aliases=["cutctx_retrieve"],
            description=(
                "Retrieve the original uncompressed content behind a Cutctx compression marker. "
                "Markers look like '[N items compressed ... hash=abc123]' or '<<ccr:abc123>>' "
                "or '<<ccr:abc123,base64,4.5KB>>'. "
                "They are NOT file paths — never try to cat/read/open them. "
                "When you see one in a tool result or message history, call this tool with the "
                "hash to get the full original content. "
                "Use the optional 'query' param to filter very large results via BM25 search. "
                "If the content has expired (TTL passed or proxy restarted), re-run the "
                "original command instead of retrying."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hash": {
                        "type": "string",
                        "description": (
                            "Hash from the compression marker — the hex string after 'hash=' "
                            "or 'ccr:'. E.g. 'abc123' from '[... hash=abc123]' or "
                            "'<<ccr:abc123,base64,4.5KB>>'."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "Optional BM25 search query to filter very large retrieved results "
                            "to only the relevant portion."
                        ),
                    },
                },
                "required": ["hash"],
            },
        ),
        types.Tool(
            name="cutctx_status",
            description=(
                "Check whether the Cutctx proxy is running and return compression stats "
                "for the current session (tokens saved, cost saved, requests handled)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="cutctx_proxy_start",
            description=(
                "Start the Cutctx proxy if it is not already running. "
                "Use this if cutctx_retrieve returns a 'proxy unreachable' error."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="cutctx_compress",
            description=(
                "Compress text or messages using Cutctx's compression algorithms. "
                "Returns compressed content with token savings information."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text or JSON messages to compress.",
                    },
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="cutctx_scan",
            description=(
                "Scan text for security violations using Cutctx's LLM firewall. "
                "Detects PII (SSN, credit cards, emails), injection attacks, and jailbreak attempts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to scan for security violations.",
                    },
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="cutctx_audit",
            description=(
                "Query recent audit log events from the Cutctx proxy. "
                "Filter by action type, limit results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Filter by action type (e.g. 'org.created', 'stats.reset').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 20).",
                        "default": 20,
                    },
                },
            },
        ),
        types.Tool(
            name="cutctx_orgs",
            description=(
                "List organizations in Cutctx, or create a new one. "
                "Call with action='list' to see all orgs, or action='create' with name and admin_email."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create"],
                        "description": "Whether to list or create organizations.",
                        "default": "list",
                    },
                    "name": {
                        "type": "string",
                        "description": "Organization name (required for create).",
                    },
                    "admin_email": {
                        "type": "string",
                        "description": "Admin email (required for create).",
                    },
                },
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # Handle legacy name
    if name == "cutctx_retrieve":
        name = "cutctx_retrieve"

    if name == "cutctx_retrieve":
        await _ensure_proxy()

        # Normalize all marker formats to a bare hash
        hash_key = str(arguments.get("hash", "")).strip()
        hash_key = hash_key.strip("<>")
        if hash_key.startswith("ccr:"):
            hash_key = hash_key[4:]
        elif hash_key.startswith("hash="):
            hash_key = hash_key[5:]
        hash_key = hash_key.split(",")[0].strip()

        if not hash_key:
            return [types.TextContent(
                type="text",
                text="Error: hash is required. Pass the hex string from the compression marker.",
            )]

        payload: dict = {"hash": hash_key}
        if query := str(arguments.get("query", "")).strip():
            payload["query"] = query

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{PROXY_URL}/v1/retrieve", json=payload)
            if r.status_code == 404:
                return [types.TextContent(
                    type="text",
                    text=(
                        "Content not found: either expired (TTL passed) or the proxy was "
                        "restarted. Re-run the original command to regenerate the data."
                    ),
                )]
            r.raise_for_status()
            data = r.json()
            content = data.get("content", str(data))
            return [types.TextContent(type="text", text=content)]
        except httpx.HTTPError as exc:
            return [types.TextContent(
                type="text",
                text=(
                    f"Cutctx proxy unreachable at {PROXY_URL} ({type(exc).__name__}). "
                    "Try calling cutctx_proxy_start, or run `cutctx proxy` in a terminal."
                ),
            )]

    elif name == "cutctx_status":
        running = await _check_proxy()
        if not running:
            return [types.TextContent(
                type="text",
                text=(
                    "Cutctx proxy is NOT running.\n"
                    "Call cutctx_proxy_start to start it, or run `cutctx proxy` in a terminal."
                ),
            )]
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{PROXY_URL}/metrics")
            return [types.TextContent(
                type="text",
                text=f"Cutctx proxy is running at {PROXY_URL}.\n\n{r.text}",
            )]
        except Exception:
            return [types.TextContent(
                type="text",
                text=f"Cutctx proxy is running at {PROXY_URL} (metrics endpoint unavailable).",
            )]

    elif name == "cutctx_proxy_start":
        if await _check_proxy():
            return [types.TextContent(
                type="text",
                text=f"Cutctx proxy is already running at {PROXY_URL}.",
            )]
        success = await _start_proxy()
        if success:
            return [types.TextContent(
                type="text",
                text=f"Cutctx proxy started successfully at {PROXY_URL}.",
            )]
        return [types.TextContent(
            type="text",
            text=(
                "Failed to start proxy. Make sure cutctx-ai is installed:\n"
                "  pip install cutctx-ai\n"
                "Then retry, or run `cutctx proxy` in a terminal."
            ),
        )]

    elif name == "cutctx_compress":
        await _ensure_proxy()
        text = str(arguments.get("text", "")).strip()
        if not text:
            return [types.TextContent(type="text", text="Error: text is required.")]

        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    f"{PROXY_URL}/v1/compress",
                    json={"content": text},
                    headers=_admin_headers(),
                )
            r.raise_for_status()
            data = r.json()
            compressed = data.get("compressed", data.get("content", str(data)))
            savings = data.get("savings_percent", data.get("savings", ""))
            result = f"Compressed content:\n{compressed}"
            if savings:
                result += f"\n\nSavings: {savings}%"
            return [types.TextContent(type="text", text=result)]
        except httpx.HTTPError as exc:
            return [types.TextContent(
                type="text",
                text=f"Compression failed ({type(exc).__name__}): {exc}",
            )]

    elif name == "cutctx_scan":
        await _ensure_proxy()
        text = str(arguments.get("text", "")).strip()
        if not text:
            return [types.TextContent(type="text", text="Error: text is required.")]

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"{PROXY_URL}/firewall/scan",
                    json={"text": text},
                    headers=_admin_headers(),
                )
            r.raise_for_status()
            data = r.json()
            violations = data.get("violations", [])
            if not violations:
                return [types.TextContent(type="text", text="No security violations detected.")]
            lines = [f"Found {len(violations)} violation(s):"]
            for v in violations:
                kind = v.get("kind", "unknown")
                desc = v.get("description", "")
                matched = v.get("matched_text", "")
                block = "BLOCK" if v.get("block", False) else "WARN"
                lines.append(f"  [{block}] {kind}: {desc}")
                if matched:
                    lines.append(f"         Matched: {matched[:80]}")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except httpx.HTTPError as exc:
            return [types.TextContent(
                type="text",
                text=f"Scan failed ({type(exc).__name__}): {exc}",
            )]

    elif name == "cutctx_audit":
        await _ensure_proxy()
        action = str(arguments.get("action", "")).strip()
        limit = int(arguments.get("limit", 20))

        try:
            params = f"?limit={limit}"
            if action:
                params += f"&action={action}"
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    f"{PROXY_URL}/audit/events{params}",
                    headers=_admin_headers(),
                )
            r.raise_for_status()
            data = r.json()
            events = data.get("events", [])
            if not events:
                return [types.TextContent(type="text", text="No audit events found.")]
            lines = [f"Showing {len(events)} event(s):"]
            for e in events:
                ts = e.get("timestamp", "?")[:19]
                act = e.get("action", "?")
                actor = e.get("actor", "?")
                ok = "OK" if e.get("success", True) else "FAIL"
                lines.append(f"  [{ts}] {act} by {actor} — {ok}")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except httpx.HTTPError as exc:
            return [types.TextContent(
                type="text",
                text=f"Audit query failed ({type(exc).__name__}): {exc}",
            )]

    elif name == "cutctx_orgs":
        await _ensure_proxy()
        action = str(arguments.get("action", "list")).strip()

        try:
            async with httpx.AsyncClient(timeout=10) as c:
                if action == "create":
                    org_name = str(arguments.get("name", "")).strip()
                    admin_email = str(arguments.get("admin_email", "")).strip()
                    if not org_name:
                        return [types.TextContent(type="text", text="Error: name is required for create.")]
                    r = await c.post(
                        f"{PROXY_URL}/orgs",
                        json={"name": org_name, "admin_email": admin_email},
                        headers=_admin_headers(),
                    )
                else:
                    r = await c.get(
                        f"{PROXY_URL}/orgs",
                        headers=_admin_headers(),
                    )
            r.raise_for_status()
            data = r.json()
            orgs_list = data.get("organizations", data if isinstance(data, list) else [])
            if action == "create":
                return [types.TextContent(
                    type="text",
                    text=f"Created organization: {data.get('name', '?')} (id={data.get('id', '?')})",
                )]
            if not orgs_list:
                return [types.TextContent(type="text", text="No organizations found. Create one to get started.")]
            lines = [f"Found {len(orgs_list)} organization(s):"]
            for o in orgs_list:
                lines.append(f"  - {o.get('name', '?')} ({o.get('slug', '?')}) id={o.get('id', '?')}")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except httpx.HTTPError as exc:
            return [types.TextContent(
                type="text",
                text=f"Org query failed ({type(exc).__name__}): {exc}",
            )]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
