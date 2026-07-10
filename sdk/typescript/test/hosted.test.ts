import { beforeEach, describe, expect, it, vi } from "vitest";

import { CutctxConnectionError } from "../src/errors.js";
import {
  HostedCompressionClient,
  HostedCompressionError,
  type HostedCompressionResult,
} from "../src/hosted.js";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function okResponse(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, body: object): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("HostedCompressionClient", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("posts text payloads to /v1/hosted/compress", async () => {
    mockFetch.mockResolvedValueOnce(okResponse({
      object: "cutctx.compression",
      input_kind: "text",
      compatibility_mode: "tool_output",
      model: "gpt-4o",
      text: "compressed",
      messages: [{ role: "tool", content: "compressed", tool_call_id: "hosted_compression_input" }],
      tokens_before: 100,
      tokens_after: 40,
      tokens_saved: 60,
      compression_ratio: 0.6,
      transforms_applied: ["router:smart_crusher:0.40"],
    }));

    const client = new HostedCompressionClient({
      baseUrl: "https://cutctx.example/",
      apiKey: "secret",
      timeout: 12_500,
    });
    const result = await client.compressText("hello", {
      model: "gpt-4o",
      protect_recent: 0,
      min_tokens_to_compress: 10,
      compatibility_mode: "tool_output",
    });

    expect(result.tokensSaved).toBe(60);
    expect(result.compatibilityMode).toBe("tool_output");
    expect(result.transformsApplied).toEqual(["router:smart_crusher:0.40"]);

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://cutctx.example/v1/hosted/compress");
    expect(options.method).toBe("POST");
    expect(options.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer secret",
    });
    expect(JSON.parse(String(options.body))).toEqual({
      text: "hello",
      model: "gpt-4o",
      protect_recent: 0,
      min_tokens_to_compress: 10,
      compatibility_mode: "tool_output",
    });
  });

  it("passes through compatibility mode options", async () => {
    mockFetch.mockResolvedValueOnce(okResponse({
      input_kind: "text",
      compatibility_mode: "rag_text",
      model: "gpt-4o",
      text: "compressed-rag",
      messages: [{ role: "user", content: "compressed-rag" }],
      tokens_before: 30,
      tokens_after: 10,
      tokens_saved: 20,
      compression_ratio: 0.67,
      transforms_applied: ["router:kompress:0.33"],
    }));

    const client = new HostedCompressionClient({ baseUrl: "https://cutctx.example" });
    const result = await client.compressText("hello", { compatibility_mode: "rag_text" });

    const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(options.body))).toEqual({
      text: "hello",
      model: "gpt-4o",
      compatibility_mode: "rag_text",
    });
    expect(result.compatibilityMode).toBe("rag_text");
  });

  it("posts message payloads without auth when no api key is set", async () => {
    const messages = [{ role: "user", content: "hello" }] as const;
    mockFetch.mockResolvedValueOnce(okResponse({
      input_kind: "messages",
      compatibility_mode: "messages",
      model: "gpt-4o",
      text: null,
      messages,
      tokens_before: 1,
      tokens_after: 1,
      tokens_saved: 0,
      compression_ratio: 0,
      transforms_applied: [],
    }));

    const client = new HostedCompressionClient({ baseUrl: "http://localhost:8787" });
    const result = await client.compressMessages([...messages]);

    const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(options.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(String(options.body))).toEqual({
      messages,
      model: "gpt-4o",
    });
    expect(result.inputKind).toBe("messages");
    expect(result.compatibilityMode).toBe("messages");
    expect(result.messages).toEqual(messages);
  });

  it("raises structured hosted errors", async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(401, {
      error: { message: "Invalid hosted key" },
    }));

    const client = new HostedCompressionClient({ baseUrl: "https://cutctx.example" });

    try {
      await client.compressText("hello");
      throw new Error("Expected hosted compression to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(HostedCompressionError);
      expect(error).toMatchObject({
        name: "HostedCompressionError",
        statusCode: 401,
        payload: { error: { message: "Invalid hosted key" } },
      });
      expect(String(error)).toContain("Invalid hosted key");
    }
  });

  it("raises connection errors when the hosted endpoint is unreachable", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("fetch failed"));

    const client = new HostedCompressionClient({ baseUrl: "https://cutctx.example" });

    await expect(client.compressText("hello")).rejects.toBeInstanceOf(CutctxConnectionError);
  });

  it("supports a simple baseUrl swap from local proxy to hosted endpoint", async () => {
    const localResponse = {
      input_kind: "text",
      compatibility_mode: "tool_output",
      model: "gpt-4o",
      text: "compressed",
      messages: [{ role: "tool", content: "compressed", tool_call_id: "hosted_compression_input" }],
      tokens_before: 100,
      tokens_after: 40,
      tokens_saved: 60,
      compression_ratio: 0.6,
      transforms_applied: ["router:smart_crusher:0.40"],
    };
    mockFetch
      .mockResolvedValueOnce(okResponse(localResponse))
      .mockResolvedValueOnce(okResponse(localResponse));

    const localClient = new HostedCompressionClient({ baseUrl: "http://localhost:8787" });
    const hostedClient = new HostedCompressionClient({
      baseUrl: "https://api.cutctx.example",
      apiKey: "hosted-secret",
    });

    const [local, hosted] = await Promise.all([
      localClient.compressText("hello", {
        model: "gpt-4o",
        min_tokens_to_compress: 10,
        compatibility_mode: "tool_output",
      }),
      hostedClient.compressText("hello", {
        model: "gpt-4o",
        min_tokens_to_compress: 10,
        compatibility_mode: "tool_output",
      }),
    ]);

    const comparable = (result: HostedCompressionResult) => ({
      text: result.text,
      messages: result.messages,
      tokensBefore: result.tokensBefore,
      tokensAfter: result.tokensAfter,
      tokensSaved: result.tokensSaved,
      compressionRatio: result.compressionRatio,
      transformsApplied: result.transformsApplied,
      model: result.model,
      inputKind: result.inputKind,
      compatibilityMode: result.compatibilityMode,
    });

    expect(comparable(local)).toEqual(comparable(hosted));
    expect(mockFetch.mock.calls[0]?.[0]).toBe("http://localhost:8787/v1/hosted/compress");
    expect(mockFetch.mock.calls[1]?.[0]).toBe("https://api.cutctx.example/v1/hosted/compress");
  });

  it("is exported from the package root", async () => {
    const pkg = await import("../src/index.js");

    expect(pkg.HostedCompressionClient).toBe(HostedCompressionClient);
    expect(pkg.HostedCompressionError).toBe(HostedCompressionError);
  });
});
