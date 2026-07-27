---
name: cutctx
description: Compress bulky tool outputs and retrieve originals by hash when exact detail is needed.
---

# Cutctx

Use Cutctx to keep long sessions compact without losing important details.

## Automatic Mode

- Default to Cutctx when the user asks for token savings, automatic compression, context hygiene, or Cutctx itself.
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

- Use `mcp__cutctx.cutctx_stats` when the user asks whether Cutctx is working.
- Report real savings honestly. If stats show no compressions yet, say Cutctx is available but has not saved tokens in this session.
- Prefer `cutctx report buyer` for created vs observed attribution; never invent savings percentages.

## Do Not

- Do not invent or round up savings numbers.
- Do not compress skill bodies, AGENTS.md / CLAUDE.md instruction blocks, or system prompts Cutctx has marked for skill preserve.
- Do not treat provider prompt-cache discounts as Cutctx-created savings.
