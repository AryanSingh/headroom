import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock cutctx-ai before importing the plugin
vi.mock("cutctx-ai", () => ({
  compress: vi.fn(),
}))

import plugin from "../cutctx"

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

describe("experimental.session.compacting hook", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.CUTCTX_DISABLED
  })

  it("appends cutctx context to output.context and may replace output.prompt", async () => {
    const handlers = await plugin(fakeInput())
    const handler = (handlers as any)["experimental.session.compacting"]
    expect(handler).toBeTypeOf("function")

    const input = { sessionID: "ses_abc123" }
    const output: { context: string[]; prompt?: string } = { context: [] }

    await handler?.(input, output)

    expect(output.context).toHaveLength(1)
    expect(output.context[0]).toContain("cutctx")
    expect(output.context[0]).toContain("cutctx_retrieve")
    // prompt may be set; if set, it should be a non-empty string
    if (output.prompt !== undefined) {
      expect(typeof output.prompt).toBe("string")
      expect(output.prompt.length).toBeGreaterThan(0)
    }
  })

  it("is a no-op when CUTCTX_DISABLED=1", async () => {
    process.env.CUTCTX_DISABLED = "1"
    const handlers = await plugin(fakeInput())
    const handler = (handlers as any)["experimental.session.compacting"]
    expect(handler).toBeTypeOf("function")

    const input = { sessionID: "ses_disabled" }
    const output: { context: string[]; prompt?: string } = { context: [] }

    await handler?.(input, output)

    expect(output.context).toEqual([])
    expect(output.prompt).toBeUndefined()
  })
})
