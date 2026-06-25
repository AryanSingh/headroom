---
name: cutctx
description: Use when bulky prompts, logs, search results, traces, or notes should be compressed automatically to save tokens and later retrieved by hash when exact details are needed.
---

# CutCtx

Use CutCtx automatically to keep long sessions compact without losing important details.

## Automatic Mode

- Default to using CutCtx once the user asks for token savings, automatic compression, context hygiene, or CutCtx itself.
- Compress proactively when a tool result, browser dump, log, audit note, or search result is large enough to crowd the context window.
- Do not compress short outputs where exact wording is the task.

## Compress

- Use `mcp__cutctx.cutctx_compress` for large command output, multi-file search results, logs, traces, or long notes.
- Keep the returned hash with the compressed summary if you may need the original later.
- Prefer compressing artifacts instead of rewriting them by hand.

## Retrieve

- Use `mcp__cutctx.cutctx_retrieve` with the stored hash when you need the original text again.
- Add a `query` when you only need one part of the stored content.
- If a retrieval is still too large, compress the new result again before continuing.

## Verify

- Use `mcp__cutctx.cutctx_stats` when the user asks whether CutCtx is working.
- Report real savings honestly. If stats show no compressions yet, say CutCtx is available but has not saved tokens in this session.

## Good Use

- Compress repetitive logs before long debugging sessions.
- Compress large audit or planning notes once they stop changing.
- Keep the most recent working context in full, and compress older background material.
