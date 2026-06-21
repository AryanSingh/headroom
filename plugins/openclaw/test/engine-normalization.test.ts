import { describe, expect, it } from "vitest";
import { CutCtxContextEngine } from "../src/engine.js";

describe("CutCtxContextEngine", () => {
  it("normalizes pass-through assistant messages when no proxy is available", async () => {
    const engine = new CutCtxContextEngine({ enabled: false });

    const result = await engine.assemble({
      sessionId: "test-session",
      messages: [
        { role: "user", content: "hi", timestamp: Date.now() },
        { role: "assistant", content: "hello there", timestamp: Date.now() },
      ],
    });

    expect(result.messages[1]).toMatchObject({
      role: "assistant",
      content: [{ type: "text", text: "hello there" }],
    });
  });
});
