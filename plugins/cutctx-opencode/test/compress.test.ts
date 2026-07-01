import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock cutctx-ai before importing the plugin
vi.mock("cutctx-ai", () => ({
  compress: vi.fn(),
  retrieve: vi.fn(),
  stats: vi.fn(() => ({ recordCompression: vi.fn(), snapshot: vi.fn() })),
}))

import { compress, stats } from "cutctx-ai"
import plugin from "../cutctx"

const THRESHOLD = 4096

describe("tool.execute.after compression hook", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.CUTCTX_DISABLED
  })

  it("does not compress when output is below threshold", async () => {
    const output = { text: "small output" }
    const handlers = await plugin({ client: {} as any, project: {} as any, directory: "/tmp", $: {} as any })
    await handlers["tool.execute.after"]?.({ tool: "read" } as any, output as any)
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
    expect(output.text).toBe("small output")
  })

  it("compresses large output and prepends the cutctx header", async () => {
    const big = "x".repeat(THRESHOLD + 100)
    const output = { text: big }
    vi.mocked(compress).mockResolvedValueOnce({
      content: "compressed-body",
      originalHandle: "ccr_8f2c1a",
      savings: { tokensBefore: 12400, tokensAfter: 3720, ratio: 0.3 },
    } as any)
    const handlers = await plugin({ client: {} as any, project: {} as any, directory: "/tmp", $: {} as any })
    await handlers["tool.execute.after"]?.({ tool: "bash" } as any, output as any)
    expect(vi.mocked(compress)).toHaveBeenCalledOnce()
    expect(output.text).toContain("[cutctx: compressed 12400 → 3720 tokens (handle: ccr_8f2c1a)]")
    expect(output.text).toContain("compressed-body")
    expect(vi.mocked(stats).mock.results.length).toBeGreaterThan(0)
  })

  it("falls back to the original output when compress() throws", async () => {
    const big = "y".repeat(THRESHOLD + 100)
    const output = { text: big }
    vi.mocked(compress).mockRejectedValueOnce(new Error("kaboom"))
    const handlers = await plugin({ client: {} as any, project: {} as any, directory: "/tmp", $: {} as any })
    await handlers["tool.execute.after"]?.({ tool: "read" } as any, output as any)
    expect(output.text).toBe(big)
  })

  it("is a no-op when CUTCTX_DISABLED=1", async () => {
    process.env.CUTCTX_DISABLED = "1"
    const big = "z".repeat(THRESHOLD + 100)
    const output = { text: big }
    const handlers = await plugin({ client: {} as any, project: {} as any, directory: "/tmp", $: {} as any })
    await handlers["tool.execute.after"]?.({ tool: "read" } as any, output as any)
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
    expect(output.text).toBe(big)
  })
})
