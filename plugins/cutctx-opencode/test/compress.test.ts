import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock cutctx-ai before importing the plugin
vi.mock("cutctx-ai", () => ({
  compress: vi.fn(),
}))

import { compress } from "cutctx-ai"
import plugin from "../cutctx"

const THRESHOLD = 4096

const fakeInput = () =>
  ({
    client: {} as any,
    project: {} as any,
    directory: "/tmp",
    worktree: "/tmp",
    experimental_workspace: { register: () => {} },
    serverUrl: new URL("http://localhost"),
    $: {} as any,
  }) as any

describe("tool.execute.after compression hook", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.CUTCTX_DISABLED
  })

  it("does not compress when output is below threshold", async () => {
    const output = { title: "t", output: "small output", metadata: {} } as any
    const handlers = await plugin(fakeInput())
    await handlers["tool.execute.after"]?.(
      { tool: "read", sessionID: "s", callID: "c", args: {} } as any,
      output
    )
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
    expect(output.output).toBe("small output")
  })

  it("compresses large output and prepends the cutctx header", async () => {
    const big = "x".repeat(THRESHOLD + 100)
    const output = { title: "t", output: big, metadata: {} } as any
    vi.mocked(compress).mockResolvedValueOnce({
      messages: [{ role: "user", content: "compressed-body" }],
      tokensBefore: 12400,
      tokensAfter: 3720,
      tokensSaved: 8680,
      compressionRatio: 0.3,
      transformsApplied: [],
      ccrHashes: ["ccr_8f2c1a"],
      compressed: true,
    } as any)
    const handlers = await plugin(fakeInput())
    await handlers["tool.execute.after"]?.(
      { tool: "bash", sessionID: "s", callID: "c", args: {} } as any,
      output
    )
    expect(vi.mocked(compress)).toHaveBeenCalledOnce()
    expect(output.output).toContain(
      "[cutctx: compressed 12400 → 3720 tokens (handle: ccr_8f2c1a)]"
    )
    expect(output.output).toContain("compressed-body")
  })

  it("falls back to the original output when compress() throws", async () => {
    const big = "y".repeat(THRESHOLD + 100)
    const output = { title: "t", output: big, metadata: {} } as any
    vi.mocked(compress).mockRejectedValueOnce(new Error("kaboom"))
    const handlers = await plugin(fakeInput())
    await handlers["tool.execute.after"]?.(
      { tool: "read", sessionID: "s", callID: "c", args: {} } as any,
      output
    )
    expect(output.output).toBe(big)
  })

  it("is a no-op when CUTCTX_DISABLED=1", async () => {
    process.env.CUTCTX_DISABLED = "1"
    const big = "z".repeat(THRESHOLD + 100)
    const output = { title: "t", output: big, metadata: {} } as any
    const handlers = await plugin(fakeInput())
    await handlers["tool.execute.after"]?.(
      { tool: "read", sessionID: "s", callID: "c", args: {} } as any,
      output
    )
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
    expect(output.output).toBe(big)
  })
})
