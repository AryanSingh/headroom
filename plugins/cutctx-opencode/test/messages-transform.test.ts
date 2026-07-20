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

// Build a "long" history in opencode's real {info, parts} shape.
function longMessages(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    info: {
      id: `msg_${i}`,
      sessionID: "ses_abc123",
      role: i % 2 === 0 ? "user" : "assistant",
    } as any,
    parts: [
      {
        id: `part_${i}`,
        sessionID: "ses_abc123",
        messageID: `msg_${i}`,
        type: "text" as const,
        text: "long content ".repeat(500),
      },
    ],
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
      messages: [{ role: "user", content: "compacted" }],
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
    // compress() must receive canonical {role, content} messages derived
    // from the older items' text parts, not raw {info, parts} objects —
    // otherwise cutctx-ai's format detector misclassifies them as Gemini.
    expect(call[0]).toHaveLength(older.length)
    expect(call[0][0]).toMatchObject({ role: "user", content: expect.stringContaining("long content") })
    expect(call[0][0]).not.toHaveProperty("parts")
    // The recent N messages are preserved verbatim at the tail
    expect(output.messages.slice(-4)).toEqual(recent)
    // The head is a valid {info, parts} item wrapping the compressed text
    expect(output.messages[0]).toHaveProperty("info")
    expect(output.messages[0]?.parts[0]).toMatchObject({ type: "text", text: "compacted" })
  })

  it("is a no-op when CUTCTX_DISABLED=1", async () => {
    process.env.CUTCTX_DISABLED = "1"
    const handlers = await plugin(fakeInput())
    const output = { messages: longMessages(200) }
    await handlers["experimental.chat.messages.transform"]?.({} as any, output as any)
    expect(vi.mocked(compress)).not.toHaveBeenCalled()
  })

  it("warns once for repeated authentication failures", async () => {
    const authError = new Error("Invalid or expired Cutctx client credential.")
    authError.name = "CutctxAuthError"
    vi.mocked(compress).mockRejectedValue(authError)
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    const handlers = await plugin(fakeInput())

    const first = { messages: longMessages(200) }
    const second = { messages: longMessages(200) }
    await handlers["experimental.chat.messages.transform"]?.({} as any, first as any)
    await handlers["experimental.chat.messages.transform"]?.({} as any, second as any)

    expect(warn).toHaveBeenCalledTimes(1)
    expect(warn.mock.calls[0]![0]).toContain("cutctx auth login")
    expect(first.messages).toHaveLength(200)
    expect(second.messages).toHaveLength(200)
    warn.mockRestore()
  })
})
