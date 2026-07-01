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
  }
}

export default plugin
