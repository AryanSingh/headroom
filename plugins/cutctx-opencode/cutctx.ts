import type { Plugin } from "@opencode-ai/plugin"
import { compress } from "cutctx-ai"

const COMPRESS_THRESHOLD_BYTES = Number(
  process.env.CUTCTX_COMPRESS_THRESHOLD_BYTES ?? 4096
)
const DEFAULT_MODEL = "claude-sonnet-4-5"

const plugin: Plugin = async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return

      const text = output.output
      if (typeof text !== "string" || text.length <= COMPRESS_THRESHOLD_BYTES) {
        return
      }

      try {
        const messages = [{ role: "user" as const, content: text }]
        const result = await compress(messages, { model: DEFAULT_MODEL })
        const handle = result.ccrHashes[0] ?? "n/a"
        const header = `[cutctx: compressed ${result.tokensBefore} → ${result.tokensAfter} tokens (handle: ${handle})]`

        const first = result.messages[0]
        const body =
          first && typeof first === "object" && "content" in first
            ? typeof first.content === "string"
              ? first.content
              : JSON.stringify(result.messages)
            : JSON.stringify(result.messages)

        output.output = `${header}\n${body}`
      } catch (err) {
        console.warn(
          "cutctx: compress failed, falling back to original",
          err instanceof Error ? err.message : err
        )
      }

      // touch input.tool so it's considered used in narrow call paths
      void input.tool
    },
    "experimental.chat.messages.transform": async (_input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return
      const messages = output.messages
      if (!Array.isArray(messages) || messages.length === 0) return

      const modelLimit = Number(process.env.CUTCTX_MODEL_LIMIT ?? 200_000)
      const charBudget = modelLimit * 4 // rough chars-per-token heuristic
      const size = JSON.stringify(messages).length
      if (size < charBudget * 0.85) return

      const protectRecent = Number(process.env.CUTCTX_PROTECT_RECENT_TURNS ?? 4)
      const recent = messages.slice(-protectRecent)
      const older = messages.slice(0, -protectRecent)
      if (older.length === 0) return

      try {
        const result = await compress(older, { model: DEFAULT_MODEL })
        output.messages = [...result.messages, ...recent]
      } catch (err) {
        console.warn(
          "cutctx: history compress failed, passing through",
          err instanceof Error ? err.message : err
        )
      }
    },
    "experimental.session.compacting": async (_input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return
      output.context.push(
        "[cutctx: this session's prior turns were compressed by cutctx. Use the cutctx_retrieve MCP tool with CCR handles to fetch any originals you need.]"
      )
    },
  }
}

export default plugin
