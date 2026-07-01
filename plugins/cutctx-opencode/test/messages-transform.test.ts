import { describe, it, expect, vi, beforeEach } from "vitest"

vi.mock("cutctx-ai", () => ({
  compress: vi.fn(),
}))

import { compress } from "cutctx-ai"
import plugin from "../cutctx"

const fakeInput = () => ({
  client: {} as any,
  project: {} as any,
  directory: "/tmp",
  worktree: {} as any,
  experimental_workspace: {} as any,
  serverUrl: {} as any,
  $: {} as any,
})

// Build a "long" history by repeating role+content pairs.
function longMessages(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    info: { role: i % 2 === 0 ? "user" : "assistant" } as any,
    parts: [{ type: "text" as const, text: "long content ".repeat(500) }],
  }))
}

const shortMessages = longMessages(2)

describe("experimental.chat.messages.transform", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.CUTCTX_DISABLED
  })

  it("returns messages unchanged when under threshold", async () => {
    const handlers = await plugin(fakeInput())
    const output = { messages: shortMessages }
    await handlers["experimental.chat.messages.transform"]?.({} as any, output as any)
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
    expect(output.messages).toBe(shortMessages)
  })

  it("compresses the older portion and re-attaches the recent N when over threshold", async () => {
    const history = longMessages(200)
    const recent = history.slice(-4)
    const older = history.slice(0, -4)
    vi.mocked(compress).mockResolvedValueOnce({
      messages: [{ info: older[0]!.info, parts: [{ type: "text", text: "compacted" }] }],
      tokensBefore: 100_000,
      tokensAfter: 30_000,
      tokensSaved: 70_000,
      compressionRatio: 0.3,
      transformsApplied: ["smart_crusher"],
      ccrHashes: ["ccr_older"],
      compressed: true,
    } as any)
    const handlers = await plugin(fakeInput())
    const output = { messages: history }
    await handlers["experimental.chat.messages.transform"]?.({} as any, output as any)
    expect(vi.mocked(compress)).toHaveBeenCalledOnce()
    const call = vi.mocked(compress).mock.calls[0]!
    // The first argument to compress must be the older portion only
    expect(call[0]).toHaveLength(older.length)
    // The recent N messages are preserved verbatim at the tail
    expect(output.messages.slice(-4)).toEqual(recent)
    // The head was replaced with the compressed result
    expect(output.messages[0]?.parts[0]).toMatchObject({ type: "text", text: "compacted" })
  })

  it("is a no-op when CUTCTX_DISABLED=1", async () => {
    process.env.CUTCTX_DISABLED = "1"
    const handlers = await plugin(fakeInput())
    const output = { messages: longMessages(200) }
    await handlers["experimental.chat.messages.transform"]?.({} as any, output as any)
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
  })
})
