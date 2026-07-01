import type { Plugin } from "@opencode-ai/plugin"
import { compress, stats } from "cutctx-ai"

const COMPRESS_THRESHOLD_BYTES = Number(
  process.env.CUTCTX_COMPRESS_THRESHOLD_BYTES ?? 4096
)

function maybeHeader(before: number, after: number, handle: string): string {
  return `[cutctx: compressed ${before} → ${after} tokens (handle: ${handle})]`
}

const plugin: Plugin = async () => {
  const statsApi = stats()
  const logger = {
    warn: (msg: string, err?: unknown) =>
      console.warn(msg, err instanceof Error ? err.message : err),
    error: (msg: string, err?: unknown) =>
      console.error(msg, err instanceof Error ? err.message : err),
  }

  return {
    "tool.execute.after": async (input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") {
        return
      }
      const text = (output as { text?: string }).text
      if (typeof text !== "string" || text.length <= COMPRESS_THRESHOLD_BYTES) {
        return
      }
      try {
        const result = await compress(
          { role: "user", content: text },
          { model: (input as { model?: string }).model ?? "claude-sonnet-4-5", targetRatio: 0.3 }
        )
        const { content, originalHandle, savings } = result as {
          content: string
          originalHandle: string
          savings: { tokensBefore: number; tokensAfter: number }
        }
        ;(output as { text: string }).text =
          maybeHeader(savings.tokensBefore, savings.tokensAfter, originalHandle) +
          "\n" +
          content
        await statsApi.recordCompression({
          tool: (input as { tool: string }).tool,
          before: savings.tokensBefore,
          after: savings.tokensAfter,
        })
      } catch (err) {
        logger.warn("cutctx: compress failed, falling back to original", err)
      }
    },
  }
}

export default plugin
