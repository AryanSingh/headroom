import type { OpenAIMessage } from "./types.js";
import { CutctxConnectionError } from "./errors.js";

const DEFAULT_TIMEOUT = 30_000;

export interface HostedCompressionClientOptions {
  baseUrl: string;
  apiKey?: string;
  timeout?: number;
}

export interface HostedCompressionResult {
  text: string | null;
  messages: OpenAIMessage[];
  tokensBefore: number;
  tokensAfter: number;
  tokensSaved: number;
  compressionRatio: number;
  transformsApplied: string[];
  model: string;
  inputKind: string;
  compatibilityMode: string;
  raw: Record<string, any>;
}

export class HostedCompressionError extends Error {
  statusCode: number;
  payload: unknown;

  constructor(message: string, options: { statusCode: number; payload?: unknown }) {
    super(message);
    this.name = "HostedCompressionError";
    this.statusCode = options.statusCode;
    this.payload = options.payload;
  }
}

export class HostedCompressionClient {
  private baseUrl: string;
  private apiKey?: string;
  private timeout: number;

  constructor(options: HostedCompressionClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
  }

  async compressText(
    text: string,
    options: { model?: string; [key: string]: any } = {},
  ): Promise<HostedCompressionResult> {
    const { model = "gpt-4o", ...rest } = options;
    return this.post({ text, model, ...rest });
  }

  async compressMessages(
    messages: OpenAIMessage[],
    options: { model?: string; [key: string]: any } = {},
  ): Promise<HostedCompressionResult> {
    const { model = "gpt-4o", ...rest } = options;
    return this.post({ messages, model, ...rest });
  }

  private async post(payload: Record<string, any>): Promise<HostedCompressionResult> {
    let response: Response;

    try {
      response = await fetch(`${this.baseUrl}/v1/hosted/compress`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeout),
      });
    } catch (error) {
      throw new CutctxConnectionError(
        `Failed to connect to Cutctx hosted compression at ${this.baseUrl}: ${error}`,
      );
    }

    let data: Record<string, any>;
    try {
      data = (await response.json()) as Record<string, any>;
    } catch {
      data = { error: { message: await response.text() } };
    }

    if (!response.ok) {
      const error = data.error;
      const message = typeof error?.message === "string"
        ? error.message
        : typeof data.detail === "string"
          ? data.detail
          : "Hosted compression request failed";
      throw new HostedCompressionError(message, {
        statusCode: response.status,
        payload: data,
      });
    }

    return {
      text: typeof data.text === "string" ? data.text : null,
      messages: Array.isArray(data.messages) ? (data.messages as OpenAIMessage[]) : [],
      tokensBefore: Number(data.tokens_before ?? 0),
      tokensAfter: Number(data.tokens_after ?? 0),
      tokensSaved: Number(data.tokens_saved ?? 0),
      compressionRatio: Number(data.compression_ratio ?? 0),
      transformsApplied: Array.isArray(data.transforms_applied)
        ? data.transforms_applied.map(String)
        : [],
      model: String(data.model ?? payload.model ?? ""),
      inputKind: String(data.input_kind ?? "messages"),
      compatibilityMode: String(
        data.compatibility_mode
          ?? payload.compatibility_mode
          ?? ("text" in payload ? "tool_output" : "messages"),
      ),
      raw: data,
    };
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers.Authorization = `Bearer ${this.apiKey}`;
    }
    return headers;
  }
}
