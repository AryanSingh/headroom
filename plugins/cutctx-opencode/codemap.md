# plugins/cutctx-opencode/

## Responsibility
Compresses large OpenCode tool outputs and old conversation history, and annotates compacted sessions with CCR retrieval guidance.

## Design
A single OpenCode plugin registers `chat.params`, `tool.execute.after`, message-transform, and session-compaction hooks. Environment variables control thresholds/model limits/disablement; last-seen model state attributes compression accurately. All compression is fail-open through `cutctx-ai`.

## Flow
Chat hook captures model -> tool hook compresses oversized text and prepends token/CCR metadata -> history hook converts OpenCode `{info,parts}` items to canonical messages, compresses older turns, reconstructs one compact item, and preserves recent turns -> compaction hook adds retrieval instructions.

## Integration
- Loaded by `@opencode-ai/plugin` and bundled with esbuild.
- Calls the local/SDK Cutctx compression surface and emits CCR handles for MCP retrieval.
