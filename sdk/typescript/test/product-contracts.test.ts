import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  HostedCompressionClient,
  HostedCompressionError,
} from "../src/index.js";

const repoRoot = resolve(__dirname, "../../..");
const read = (relativePath: string) =>
  readFileSync(resolve(repoRoot, relativePath), "utf8");

const mockFetch = vi.fn();

function okResponse(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TypeScript hosted client product contract", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });

  it("keeps the documented hosted example aligned with package exports", () => {
    const packageJson = JSON.parse(read("sdk/typescript/package.json")) as {
      exports: Record<string, unknown>;
    };
    const readme = read("sdk/typescript/README.md");

    expect(packageJson.exports["."]).toBeTruthy();
    expect(readme).toContain("import { HostedCompressionClient } from 'cutctx-ai'");
    expect(readme).toContain("compressText");
    expect(readme).toContain("compressMessages");
    expect(readme).toContain("http://localhost:8787");
    expect(readme).toContain("https://api.cutctx.ai");
  });

  it("uses the same request and result contract for local and hosted URLs", async () => {
    const responseBody = {
      input_kind: "text",
      compatibility_mode: "tool_output",
      model: "gpt-4o",
      text: "compressed",
      messages: [{ role: "tool", content: "compressed" }],
      tokens_before: 100,
      tokens_after: 40,
      tokens_saved: 60,
      compression_ratio: 0.4,
      transforms_applied: ["router:smart_crusher:0.40"],
    };
    mockFetch
      .mockResolvedValueOnce(okResponse(responseBody))
      .mockResolvedValueOnce(okResponse(responseBody));

    const local = await new HostedCompressionClient({
      baseUrl: "http://127.0.0.1:8787/",
    }).compressText("long tool output", {
      compatibility_mode: "tool_output",
      min_tokens_to_compress: 10,
    });
    const hosted = await new HostedCompressionClient({
      baseUrl: "https://api.cutctx.example/",
      apiKey: "hosted-secret",
    }).compressText("long tool output", {
      compatibility_mode: "tool_output",
      min_tokens_to_compress: 10,
    });

    expect(local.tokensSaved).toBe(60);
    expect(hosted.tokensSaved).toBe(local.tokensSaved);
    expect(mockFetch.mock.calls[0]?.[0]).toBe(
      "http://127.0.0.1:8787/v1/hosted/compress",
    );
    expect(mockFetch.mock.calls[1]?.[0]).toBe(
      "https://api.cutctx.example/v1/hosted/compress",
    );
    expect(mockFetch.mock.calls[0]?.[1]?.headers).toEqual({
      "Content-Type": "application/json",
    });
    expect(mockFetch.mock.calls[1]?.[1]?.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer hosted-secret",
    });
  });

  it("keeps hosted failures typed for callers", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { message: "Invalid hosted key" } }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      new HostedCompressionClient({ baseUrl: "https://api.cutctx.example" }).compressText(
        "hello",
      ),
    ).rejects.toMatchObject({
      name: "HostedCompressionError",
      statusCode: 401,
      payload: { error: { message: "Invalid hosted key" } },
    } satisfies Partial<HostedCompressionError>);
  });
});
