// ../../sdk/typescript/dist/chunk-KIYIB2SF.js
var CutctxError = class extends Error {
  details;
  constructor(message, details) {
    super(message);
    this.name = "CutctxError";
    this.details = details;
  }
};
var CutctxConnectionError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "CutctxConnectionError";
  }
};
var CutctxAuthError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "CutctxAuthError";
  }
};
var CutctxCompressError = class extends CutctxError {
  statusCode;
  errorType;
  constructor(statusCode, errorType, message, details) {
    super(message, details);
    this.name = "CutctxCompressError";
    this.statusCode = statusCode;
    this.errorType = errorType;
  }
};
var ConfigurationError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "ConfigurationError";
  }
};
var ProviderError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "ProviderError";
  }
};
var StorageError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "StorageError";
  }
};
var TokenizationError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "TokenizationError";
  }
};
var CacheError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "CacheError";
  }
};
var ValidationError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "ValidationError";
  }
};
var TransformError = class extends CutctxError {
  constructor(message, details) {
    super(message, details);
    this.name = "TransformError";
  }
};
var ERROR_TYPE_MAP = {
  configuration_error: ConfigurationError,
  provider_error: ProviderError,
  storage_error: StorageError,
  tokenization_error: TokenizationError,
  cache_error: CacheError,
  validation_error: ValidationError,
  transform_error: TransformError
};
function mapProxyError(status, type, message, details) {
  if (status === 401) {
    const safeDetails = {};
    if (typeof details?.code === "string") safeDetails.code = details.code;
    if (typeof details?.remediation === "string") {
      safeDetails.remediation = details.remediation;
    }
    return new CutctxAuthError(
      message,
      Object.keys(safeDetails).length > 0 ? safeDetails : void 0
    );
  }
  const ErrorClass = ERROR_TYPE_MAP[type];
  if (ErrorClass) return new ErrorClass(message, { statusCode: status, errorType: type });
  return new CutctxCompressError(status, type, message);
}
function snakeToCamel(str) {
  return str.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase());
}
function camelToSnake(str) {
  return str.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}
function deepCamelCase(obj) {
  if (obj === null || obj === void 0) return obj;
  if (Array.isArray(obj)) return obj.map(deepCamelCase);
  if (typeof obj === "object" && !(obj instanceof Date)) {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [snakeToCamel(k), deepCamelCase(v)])
    );
  }
  return obj;
}
function deepSnakeCase(obj) {
  if (obj === null || obj === void 0) return obj;
  if (Array.isArray(obj)) return obj.map(deepSnakeCase);
  if (typeof obj === "object" && !(obj instanceof Date)) {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [camelToSnake(k), deepSnakeCase(v)])
    );
  }
  return obj;
}
async function* parseSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "[DONE]") return;
          try {
            yield JSON.parse(data);
          } catch {
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
var DEFAULT_BASE_URL = "http://localhost:8787";
var DEFAULT_TIMEOUT = 3e4;
var DEFAULT_RETRIES = 1;
function getEnv(key) {
  if (typeof process !== "undefined" && process.env) {
    return process.env[key];
  }
  return void 0;
}
function makeFallbackResult(messages) {
  return {
    messages,
    tokensBefore: 0,
    tokensAfter: 0,
    tokensSaved: 0,
    compressionRatio: 1,
    transformsApplied: [],
    ccrHashes: [],
    compressed: false
  };
}
var ChatCompletions = class {
  constructor(client) {
    this.client = client;
  }
  /**
   * Create a chat completion with automatic compression.
   * Routes through proxy's POST /v1/chat/completions.
   */
  async create(params) {
    const { cutctxMode, cutctxCachePrefixTokens, cutctxOutputBufferTokens, cutctxKeepTurns, cutctxToolProfiles, ...apiParams } = params;
    const headers = {};
    if (cutctxMode) headers["x-cutctx-mode"] = cutctxMode;
    const providerKey = this.client.providerApiKey ?? getEnv("OPENAI_API_KEY");
    if (providerKey) headers["Authorization"] = `Bearer ${providerKey}`;
    const response = await this.client.rawFetch("/v1/chat/completions", {
      method: "POST",
      headers,
      body: apiParams,
      stream: params.stream
    });
    if (params.stream) {
      return parseSSE(response);
    }
    return response.json();
  }
  /**
   * Simulate compression without calling the LLM.
   */
  async simulate(params) {
    const body = {
      messages: params.messages,
      model: params.model,
      config: { default_mode: "simulate", generate_diff_artifact: true }
    };
    const result = await this.client.compressRaw(body);
    return deepCamelCase(result);
  }
};
var Messages = class {
  constructor(client) {
    this.client = client;
  }
  /**
   * Create a message with automatic compression.
   * Routes through proxy's POST /v1/messages (Anthropic).
   */
  async create(params) {
    const { cutctxMode, cutctxCachePrefixTokens, cutctxOutputBufferTokens, cutctxKeepTurns, cutctxToolProfiles, ...apiParams } = params;
    const headers = {
      "anthropic-version": "2023-06-01"
    };
    if (cutctxMode) headers["x-cutctx-mode"] = cutctxMode;
    const providerKey = this.client.providerApiKey ?? getEnv("ANTHROPIC_API_KEY");
    if (providerKey) headers["x-api-key"] = providerKey;
    if (!apiParams.max_tokens) apiParams.max_tokens = 1024;
    const response = await this.client.rawFetch("/v1/messages", {
      method: "POST",
      headers,
      body: apiParams,
      stream: params.stream
    });
    if (params.stream) {
      return parseSSE(response);
    }
    return response.json();
  }
  /**
   * Stream a message with automatic compression.
   */
  stream(params) {
    return this.create({ ...params, stream: true });
  }
  /**
   * Simulate compression without calling the LLM.
   */
  async simulate(params) {
    const body = {
      messages: params.messages,
      model: params.model,
      config: { default_mode: "simulate", generate_diff_artifact: true }
    };
    const result = await this.client.compressRaw(body);
    return deepCamelCase(result);
  }
};
var CutctxClient = class {
  baseUrl;
  apiKey;
  timeout;
  fallback;
  retries;
  config;
  stack;
  /** @internal */
  providerApiKey;
  /** OpenAI-style chat completions API. */
  chat;
  /** Anthropic-style messages API. */
  messages;
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl ?? getEnv("CUTCTX_BASE_URL") ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.apiKey = options.apiKey ?? getEnv("CUTCTX_API_KEY");
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
    this.fallback = options.fallback ?? true;
    this.retries = options.retries ?? DEFAULT_RETRIES;
    this.providerApiKey = options.providerApiKey;
    this.config = options.config;
    this.stack = options.stack;
    this.chat = { completions: new ChatCompletions(this) };
    this.messages = new Messages(this);
  }
  // ============================================================
  // Core: compress
  // ============================================================
  async compress(messages, options = {}) {
    const model = options.model ?? "gpt-4o";
    let lastError;
    const maxAttempts = 1 + this.retries;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        return await this._doCompress(messages, model, options.tokenBudget);
      } catch (error) {
        lastError = error;
        if (error instanceof CutctxAuthError) throw error;
        if (error instanceof CutctxCompressError && error.statusCode < 500) {
          throw error;
        }
      }
    }
    if (this.fallback) {
      return makeFallbackResult(messages);
    }
    if (lastError instanceof CutctxConnectionError) throw lastError;
    if (lastError instanceof CutctxCompressError) throw lastError;
    throw new CutctxConnectionError(
      `Failed after ${maxAttempts} attempts: ${lastError}`
    );
  }
  /**
   * Raw compress call — sends body directly to /v1/compress.
   * Used by simulate() and other advanced features.
   * @internal
   */
  async compressRaw(body) {
    const response = await this._fetch("/v1/compress", {
      method: "POST",
      body: JSON.stringify(body)
    });
    return response.json();
  }
  // ============================================================
  // Health & Stats
  // ============================================================
  /** Check if the proxy is running and healthy. */
  async health() {
    const resp = await this._fetch("/health", { method: "GET" });
    return deepCamelCase(await resp.json());
  }
  /** Get comprehensive proxy statistics. */
  async proxyStats() {
    const resp = await this._fetch("/stats", { method: "GET" });
    return deepCamelCase(await resp.json());
  }
  /** Get Prometheus-format metrics. */
  async prometheusMetrics() {
    const resp = await this._fetch("/metrics", { method: "GET" });
    return resp.text();
  }
  /** Get historical stats. */
  async statsHistory(query) {
    const params = new URLSearchParams();
    if (query?.format) params.set("format", query.format);
    if (query?.series) params.set("series", query.series);
    const qs = params.toString();
    const resp = await this._fetch(`/stats-history${qs ? `?${qs}` : ""}`, { method: "GET" });
    return resp.json();
  }
  /** Get proxy memory usage. */
  async memoryUsage() {
    const resp = await this._fetch("/debug/memory", { method: "GET" });
    return deepCamelCase(await resp.json());
  }
  /** Clear the response cache. */
  async clearCache() {
    const resp = await this._fetch("/cache/clear", { method: "POST" });
    return resp.json();
  }
  // ============================================================
  // Metrics & Observability
  // ============================================================
  /** Get request metrics from the proxy. */
  async getMetrics(query) {
    const resp = await this._fetch("/stats", { method: "GET" });
    const stats = await resp.json();
    let metrics = stats.recent_requests ?? [];
    if (query?.model) {
      metrics = metrics.filter((m) => m.model === query.model);
    }
    if (query?.mode) {
      metrics = metrics.filter((m) => m.mode === query.mode);
    }
    if (query?.limit) {
      metrics = metrics.slice(0, query.limit);
    }
    return metrics.map((m) => deepCamelCase(m));
  }
  /** Get aggregated metrics summary. */
  async getSummary(query) {
    const resp = await this._fetch("/stats", { method: "GET" });
    const stats = await resp.json();
    return deepCamelCase({
      total_requests: stats.requests?.total ?? 0,
      total_tokens_before: stats.tokens?.total_before_compression ?? 0,
      total_tokens_after: (stats.tokens?.total_before_compression ?? 0) - (stats.tokens?.saved ?? 0),
      total_tokens_saved: stats.tokens?.saved ?? 0,
      average_compression_ratio: stats.tokens?.savings_percent ? stats.tokens.savings_percent / 100 : 0,
      models: stats.requests?.by_model ?? {},
      modes: {},
      error_count: stats.requests?.failed ?? 0
    });
  }
  /** Get in-memory session stats. */
  async getStats() {
    const resp = await this._fetch("/stats", { method: "GET" });
    const stats = await resp.json();
    return deepCamelCase({
      total_requests: stats.requests?.total ?? 0,
      total_tokens_before: stats.tokens?.total_before_compression ?? 0,
      total_tokens_after: (stats.tokens?.total_before_compression ?? 0) - (stats.tokens?.saved ?? 0),
      total_tokens_saved: stats.tokens?.saved ?? 0,
      average_compression_ratio: stats.tokens?.savings_percent ? stats.tokens.savings_percent / 100 : 0,
      cache_hits: stats.requests?.cached ?? 0,
      by_mode: {}
    });
  }
  /** Validate proxy configuration. */
  async validateSetup() {
    const resp = await this._fetch("/health", { method: "GET" });
    const health = await resp.json();
    return {
      valid: health.status === "healthy",
      provider: "",
      errors: health.status !== "healthy" ? ["Proxy unhealthy"] : [],
      warnings: [],
      config: health.config ?? {}
    };
  }
  // ============================================================
  // CCR Retrieve
  // ============================================================
  /** Retrieve original content from the CCR compression store. */
  async retrieve(hash, options) {
    const body = { hash };
    if (options?.query) body.query = options.query;
    const resp = await this._fetch("/v1/retrieve", {
      method: "POST",
      body: JSON.stringify(body)
    });
    return deepCamelCase(await resp.json());
  }
  /** Get CCR store statistics. */
  async getCCRStats() {
    const resp = await this._fetch("/v1/retrieve/stats", { method: "GET" });
    return deepCamelCase(await resp.json());
  }
  /** Handle an LLM tool call for cutctx_retrieve. */
  async handleToolCall(request) {
    const resp = await this._fetch("/v1/retrieve/tool_call", {
      method: "POST",
      body: JSON.stringify(deepSnakeCase(request))
    });
    return deepCamelCase(await resp.json());
  }
  // ============================================================
  // Telemetry & Feedback
  // ============================================================
  telemetry = {
    getStats: async () => {
      const resp = await this._fetch("/v1/telemetry", { method: "GET" });
      return deepCamelCase(await resp.json());
    },
    export: async () => {
      const resp = await this._fetch("/v1/telemetry/export", { method: "GET" });
      return resp.json();
    },
    import: async (data) => {
      const resp = await this._fetch("/v1/telemetry/import", {
        method: "POST",
        body: JSON.stringify(data)
      });
      return resp.json();
    },
    getTools: async () => {
      const resp = await this._fetch("/v1/telemetry/tools", { method: "GET" });
      return deepCamelCase(await resp.json());
    },
    getTool: async (signatureHash) => {
      const resp = await this._fetch(`/v1/telemetry/tools/${signatureHash}`, { method: "GET" });
      return deepCamelCase(await resp.json());
    }
  };
  feedback = {
    getStats: async () => {
      const resp = await this._fetch("/v1/feedback", { method: "GET" });
      return deepCamelCase(await resp.json());
    },
    getHints: async (toolName) => {
      const resp = await this._fetch(`/v1/feedback/${encodeURIComponent(toolName)}`, { method: "GET" });
      return deepCamelCase(await resp.json());
    }
  };
  toin = {
    getStats: async () => {
      const resp = await this._fetch("/v1/toin/stats", { method: "GET" });
      return deepCamelCase(await resp.json());
    },
    getPatterns: async (limit) => {
      const qs = limit ? `?limit=${limit}` : "";
      const resp = await this._fetch(`/v1/toin/patterns${qs}`, { method: "GET" });
      return deepCamelCase(await resp.json());
    },
    getPattern: async (hashPrefix) => {
      const resp = await this._fetch(`/v1/toin/pattern/${encodeURIComponent(hashPrefix)}`, { method: "GET" });
      return deepCamelCase(await resp.json());
    }
  };
  // ============================================================
  // Lifecycle
  // ============================================================
  /** Close the client (no-op for HTTP client, included for API parity). */
  close() {
  }
  // ============================================================
  // Internal HTTP helpers
  // ============================================================
  /**
   * Raw fetch with proxy base URL, auth, and timeout.
   * @internal
   */
  async rawFetch(path, options) {
    const url = `${this.baseUrl}${path}`;
    const headers = {
      "Content-Type": "application/json",
      ...options.headers
    };
    if (this.apiKey) {
      if (!headers["Authorization"] && !headers["x-api-key"]) {
        headers["Authorization"] = `Bearer ${this.apiKey}`;
      }
    }
    if (this.stack && !headers["X-Cutctx-Stack"]) {
      headers["X-Cutctx-Stack"] = this.stack;
    }
    let response;
    try {
      response = await fetch(url, {
        method: options.method,
        headers,
        body: options.body ? JSON.stringify(options.body) : void 0,
        signal: AbortSignal.timeout(this.timeout)
      });
    } catch (error) {
      throw new CutctxConnectionError(
        `Failed to connect to Cutctx at ${this.baseUrl}: ${error}`
      );
    }
    if (!response.ok) {
      let errorBody;
      try {
        errorBody = await response.json();
      } catch {
      }
      throw mapProxyError(
        response.status,
        errorBody?.error?.type ?? "unknown",
        errorBody?.error?.message ?? `HTTP ${response.status}`,
        errorBody?.error
      );
    }
    return response;
  }
  /** @internal */
  async _fetch(path, init) {
    const url = `${this.baseUrl}${path}`;
    const headers = {
      "Content-Type": "application/json",
      ...init.headers
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    if (this.stack && !headers["X-Cutctx-Stack"]) {
      headers["X-Cutctx-Stack"] = this.stack;
    }
    let response;
    try {
      response = await fetch(url, {
        method: init.method,
        headers,
        body: init.body,
        signal: AbortSignal.timeout(this.timeout)
      });
    } catch (error) {
      throw new CutctxConnectionError(
        `Failed to connect to Cutctx at ${this.baseUrl}: ${error}`
      );
    }
    if (!response.ok) {
      let errorBody;
      try {
        errorBody = await response.json();
      } catch {
      }
      throw mapProxyError(
        response.status,
        errorBody?.error?.type ?? "unknown",
        errorBody?.error?.message ?? `HTTP ${response.status}`,
        errorBody?.error
      );
    }
    return response;
  }
  async _doCompress(messages, model, tokenBudget) {
    const body = { messages, model };
    if (tokenBudget) {
      body.token_budget = tokenBudget;
    }
    if (this.config) {
      body.config = deepSnakeCase(this.config);
    }
    const response = await this._fetch("/v1/compress", {
      method: "POST",
      body: JSON.stringify(body)
    });
    const data = await response.json();
    return {
      messages: data.messages,
      tokensBefore: data.tokens_before,
      tokensAfter: data.tokens_after,
      tokensSaved: data.tokens_saved,
      compressionRatio: data.compression_ratio,
      transformsApplied: data.transforms_applied,
      ccrHashes: data.ccr_hashes,
      compressed: true
    };
  }
};
function detectFormat(messages) {
  for (const msg of messages) {
    if ("parts" in msg && !("content" in msg)) return "gemini";
    if (msg.role === "model") return "gemini";
    if (msg.tool_calls && msg.role === "assistant") return "openai";
    if (msg.role === "tool" && "tool_call_id" in msg && typeof msg.content === "string") return "openai";
    if (Array.isArray(msg.content)) {
      for (const part of msg.content) {
        if (part.type === "tool-call" || part.type === "tool-result") return "vercel";
        if (part.type === "tool_use" || part.type === "tool_result") return "anthropic";
        if (part.type === "image" && part.source?.type) return "anthropic";
      }
    }
  }
  return "openai";
}
function anthropicToOpenAI(messages) {
  const result = [];
  for (const msg of messages) {
    if (msg.role === "user") {
      if (typeof msg.content === "string") {
        result.push({ role: "user", content: msg.content });
        continue;
      }
      if (Array.isArray(msg.content)) {
        const textBlocks = msg.content.filter((b) => b.type === "text");
        const toolResults = msg.content.filter((b) => b.type === "tool_result");
        if (textBlocks.length > 0) {
          result.push({
            role: "user",
            content: textBlocks.map((b) => b.text).join("\n")
          });
        }
        for (const tr of toolResults) {
          const content = typeof tr.content === "string" ? tr.content : Array.isArray(tr.content) ? tr.content.map((b) => b.text ?? JSON.stringify(b)).join("\n") : JSON.stringify(tr.content);
          result.push({
            role: "tool",
            content,
            tool_call_id: tr.tool_use_id
          });
        }
      }
      continue;
    }
    if (msg.role === "assistant") {
      if (typeof msg.content === "string") {
        result.push({ role: "assistant", content: msg.content });
        continue;
      }
      if (Array.isArray(msg.content)) {
        const textBlocks = msg.content.filter((b) => b.type === "text");
        const toolUseBlocks = msg.content.filter((b) => b.type === "tool_use");
        const content = textBlocks.length > 0 ? textBlocks.map((b) => b.text).join("\n") : null;
        const openaiMsg = { role: "assistant", content };
        if (toolUseBlocks.length > 0) {
          openaiMsg.tool_calls = toolUseBlocks.map((b) => ({
            id: b.id,
            type: "function",
            function: {
              name: b.name,
              arguments: typeof b.input === "string" ? b.input : JSON.stringify(b.input)
            }
          }));
        }
        result.push(openaiMsg);
      }
      continue;
    }
  }
  return result;
}
function openAIToAnthropic(messages) {
  const result = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      result.push({ role: "user", content: msg.content });
      continue;
    }
    if (msg.role === "user") {
      if (typeof msg.content === "string") {
        result.push({ role: "user", content: msg.content });
      } else if (Array.isArray(msg.content)) {
        result.push({
          role: "user",
          content: msg.content.map(
            (p) => p.type === "text" ? { type: "text", text: p.text } : { type: "text", text: "" }
          )
        });
      }
      continue;
    }
    if (msg.role === "assistant") {
      const blocks = [];
      if (msg.content) blocks.push({ type: "text", text: msg.content });
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          blocks.push({
            type: "tool_use",
            id: tc.id,
            name: tc.function.name,
            input: JSON.parse(tc.function.arguments)
          });
        }
      }
      result.push({
        role: "assistant",
        content: blocks.length === 1 && blocks[0].type === "text" ? blocks[0].text : blocks
      });
      continue;
    }
    if (msg.role === "tool") {
      result.push({
        role: "user",
        content: [
          { type: "tool_result", tool_use_id: msg.tool_call_id, content: msg.content }
        ]
      });
      continue;
    }
  }
  return result;
}
function vercelToOpenAI(messages) {
  const result = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      result.push({ role: "system", content: typeof msg.content === "string" ? msg.content : String(msg.content) });
      continue;
    }
    if (msg.role === "user") {
      if (typeof msg.content === "string") {
        result.push({ role: "user", content: msg.content });
        continue;
      }
      const parts = Array.isArray(msg.content) ? msg.content : [];
      const textParts = parts.filter((p) => p.type === "text");
      const imageParts = parts.filter((p) => p.type === "image");
      if (imageParts.length === 0 && textParts.length > 0) {
        result.push({ role: "user", content: textParts.map((p) => p.text).join("") });
      } else {
        const openaiParts = parts.filter((p) => p.type === "text" || p.type === "image").map((p) => {
          if (p.type === "text") return { type: "text", text: p.text };
          if (p.type === "image") {
            const url = p.image instanceof URL ? p.image.toString() : String(p.image);
            return { type: "image_url", image_url: { url } };
          }
          return { type: "text", text: "" };
        });
        result.push({ role: "user", content: openaiParts });
      }
      continue;
    }
    if (msg.role === "assistant") {
      if (typeof msg.content === "string") {
        result.push({ role: "assistant", content: msg.content });
        continue;
      }
      const parts = Array.isArray(msg.content) ? msg.content : [];
      const textParts = parts.filter((p) => p.type === "text");
      const toolCallParts = parts.filter((p) => p.type === "tool-call");
      const content = textParts.length > 0 ? textParts.map((p) => p.text).join("") : null;
      const openaiMsg = { role: "assistant", content };
      if (toolCallParts.length > 0) {
        openaiMsg.tool_calls = toolCallParts.map((p) => ({
          id: p.toolCallId,
          type: "function",
          // AI SDK v6 uses `input`, earlier versions used `args`
          function: { name: p.toolName, arguments: JSON.stringify(p.input ?? p.args) }
        }));
      }
      result.push(openaiMsg);
      continue;
    }
    if (msg.role === "tool") {
      const parts = Array.isArray(msg.content) ? msg.content : [];
      for (const part of parts) {
        if (part.type === "tool-result") {
          let contentStr;
          if (part.output !== void 0) {
            const val = part.output?.value ?? part.output;
            contentStr = typeof val === "string" ? val : JSON.stringify(val);
          } else if (part.result !== void 0) {
            contentStr = typeof part.result === "string" ? part.result : JSON.stringify(part.result);
          } else {
            contentStr = "";
          }
          result.push({
            role: "tool",
            content: contentStr,
            tool_call_id: part.toolCallId
          });
        }
      }
      continue;
    }
  }
  return result;
}
function openAIToVercel(messages) {
  const result = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      result.push({ role: "system", content: msg.content });
      continue;
    }
    if (msg.role === "user") {
      if (typeof msg.content === "string") {
        result.push({ role: "user", content: [{ type: "text", text: msg.content }] });
      } else if (Array.isArray(msg.content)) {
        const parts = msg.content.map((p) => {
          if (p.type === "text") return { type: "text", text: p.text };
          if (p.type === "image_url") return { type: "image", image: new URL(p.image_url.url) };
          return { type: "text", text: "" };
        });
        result.push({ role: "user", content: parts });
      }
      continue;
    }
    if (msg.role === "assistant") {
      const parts = [];
      if (msg.content) parts.push({ type: "text", text: msg.content });
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          let input;
          try {
            input = JSON.parse(tc.function.arguments);
          } catch {
            input = tc.function.arguments ?? {};
          }
          parts.push({
            type: "tool-call",
            toolCallId: tc.id,
            toolName: tc.function.name,
            input
            // AI SDK v6 uses `input`, not `args`
          });
        }
      }
      result.push({ role: "assistant", content: parts });
      continue;
    }
    if (msg.role === "tool") {
      let parsed;
      try {
        parsed = JSON.parse(msg.content);
      } catch {
        parsed = msg.content;
      }
      const output = typeof parsed === "string" ? { type: "text", value: parsed } : { type: "json", value: parsed };
      result.push({
        role: "tool",
        content: [{
          type: "tool-result",
          toolCallId: msg.tool_call_id,
          toolName: "unknown",
          output
        }]
      });
      continue;
    }
  }
  return result;
}
function geminiToOpenAI(messages) {
  const result = [];
  for (const msg of messages) {
    const role = msg.role === "model" ? "assistant" : "user";
    const parts = msg.parts ?? [];
    if (role === "user") {
      const funcResponses = parts.filter((p) => p.functionResponse);
      const textParts = parts.filter((p) => p.text !== void 0);
      if (textParts.length > 0) {
        result.push({ role: "user", content: textParts.map((p) => p.text).join("\n") });
      }
      for (const fr of funcResponses) {
        result.push({
          role: "tool",
          content: JSON.stringify(fr.functionResponse.response),
          tool_call_id: `gemini_${fr.functionResponse.name}`
        });
      }
      continue;
    }
    if (role === "assistant") {
      const textParts = parts.filter((p) => p.text !== void 0);
      const funcCalls = parts.filter((p) => p.functionCall);
      const content = textParts.length > 0 ? textParts.map((p) => p.text).join("\n") : null;
      const openaiMsg = { role: "assistant", content };
      if (funcCalls.length > 0) {
        openaiMsg.tool_calls = funcCalls.map((p) => ({
          id: `gemini_${p.functionCall.name}`,
          type: "function",
          function: {
            name: p.functionCall.name,
            arguments: JSON.stringify(p.functionCall.args)
          }
        }));
      }
      result.push(openaiMsg);
      continue;
    }
  }
  return result;
}
function openAIToGemini(messages) {
  const result = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      result.push({ role: "user", parts: [{ text: msg.content }] });
      continue;
    }
    if (msg.role === "user") {
      const text = typeof msg.content === "string" ? msg.content : (msg.content ?? []).filter((p) => p.type === "text").map((p) => p.text).join("\n");
      result.push({ role: "user", parts: [{ text }] });
      continue;
    }
    if (msg.role === "assistant") {
      const parts = [];
      if (msg.content) parts.push({ text: msg.content });
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          parts.push({
            functionCall: { name: tc.function.name, args: JSON.parse(tc.function.arguments) }
          });
        }
      }
      result.push({ role: "model", parts });
      continue;
    }
    if (msg.role === "tool") {
      let response;
      try {
        response = JSON.parse(msg.content);
      } catch {
        response = { result: msg.content };
      }
      result.push({
        role: "user",
        parts: [{ functionResponse: { name: msg.tool_call_id?.replace("gemini_", "") ?? "unknown", response } }]
      });
      continue;
    }
  }
  return result;
}
function toOpenAI(messages) {
  const format = detectFormat(messages);
  switch (format) {
    case "openai":
      return messages;
    case "anthropic":
      return anthropicToOpenAI(messages);
    case "vercel":
      return vercelToOpenAI(messages);
    case "gemini":
      return geminiToOpenAI(messages);
  }
}
function fromOpenAI(messages, targetFormat) {
  switch (targetFormat) {
    case "openai":
      return messages;
    case "anthropic":
      return openAIToAnthropic(messages);
    case "vercel":
      return openAIToVercel(messages);
    case "gemini":
      return openAIToGemini(messages);
  }
}
function extractUserQuery(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role === "user") {
      if (typeof msg.content === "string") return msg.content;
      if (Array.isArray(msg.content)) {
        const textPart = msg.content.find(
          (p) => p.type === "text" || p.text
        );
        if (textPart) return textPart.text ?? textPart.content ?? "";
      }
    }
  }
  return "";
}
function countTurns(messages) {
  return messages.filter((m) => m.role === "user").length;
}
function extractToolCalls(messages) {
  const names = [];
  for (const msg of messages) {
    if (msg.tool_calls) {
      for (const tc of msg.tool_calls) {
        names.push(tc.function?.name ?? tc.name ?? "unknown");
      }
    }
    if (Array.isArray(msg.content)) {
      for (const part of msg.content) {
        if (part.type === "tool_use") names.push(part.name ?? "unknown");
        if (part.type === "tool-call") names.push(part.toolName ?? "unknown");
      }
    }
  }
  return names;
}
async function compress(messages, options = {}) {
  const {
    client: providedClient,
    model,
    tokenBudget,
    hooks,
    ...clientOptions
  } = options;
  const ctx = {
    model: model ?? "gpt-4o",
    userQuery: extractUserQuery(messages),
    turnNumber: countTurns(messages),
    toolCalls: extractToolCalls(messages),
    provider: ""
  };
  let processedMessages = messages;
  if (hooks) {
    processedMessages = await hooks.preCompress(messages, ctx);
  }
  const inputFormat = detectFormat(processedMessages);
  const openaiMessages = toOpenAI(processedMessages);
  if (hooks) {
    await hooks.computeBiases(openaiMessages, ctx);
  }
  const client = providedClient ?? new CutctxClient(clientOptions);
  const result = await client.compress(openaiMessages, { model, tokenBudget });
  const outputMessages = fromOpenAI(result.messages, inputFormat);
  const finalResult = {
    ...result,
    messages: outputMessages
  };
  if (hooks) {
    const event = {
      tokensBefore: result.tokensBefore,
      tokensAfter: result.tokensAfter,
      tokensSaved: result.tokensSaved,
      compressionRatio: result.compressionRatio,
      transformsApplied: result.transformsApplied,
      ccrHashes: result.ccrHashes,
      model: ctx.model,
      userQuery: ctx.userQuery,
      provider: ctx.provider
    };
    await hooks.postCompress(event);
  }
  return finalResult;
}

// cutctx.ts
var COMPRESS_THRESHOLD_BYTES = Number(
  process.env.CUTCTX_COMPRESS_THRESHOLD_BYTES ?? 4096
);
var DEFAULT_MODEL = process.env.CUTCTX_MODEL ?? "claude-sonnet-4-5";
var lastKnownModel;
var authWarningEmitted = false;
function warnCompressionFailure(message, err) {
  if (err instanceof Error && err.name === "CutctxAuthError") {
    if (authWarningEmitted) return;
    authWarningEmitted = true;
    console.warn(
      "cutctx: client authentication failed; run `cutctx auth login` and relaunch opencode",
      err.message
    );
    return;
  }
  console.warn(message, err instanceof Error ? err.message : err);
}
var plugin = async () => {
  return {
    "chat.params": async (input) => {
      if (input.model?.id) {
        lastKnownModel = input.model.id;
      }
    },
    "tool.execute.after": async (input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return;
      const text = output.output;
      if (typeof text !== "string" || text.length <= COMPRESS_THRESHOLD_BYTES) {
        return;
      }
      try {
        const messages = [{ role: "user", content: text }];
        const result = await compress(messages, { model: lastKnownModel ?? DEFAULT_MODEL });
        const handle = result.ccrHashes[0] ?? "n/a";
        const header = `[cutctx: compressed ${result.tokensBefore} \u2192 ${result.tokensAfter} tokens (handle: ${handle})]`;
        const first = result.messages[0];
        const body = first && typeof first === "object" && "content" in first ? typeof first.content === "string" ? first.content : JSON.stringify(result.messages) : JSON.stringify(result.messages);
        output.output = `${header}
${body}`;
      } catch (err) {
        warnCompressionFailure(
          "cutctx: compress failed, falling back to original",
          err
        );
      }
      void input.tool;
    },
    "experimental.chat.messages.transform": async (_input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return;
      const items = output.messages;
      if (!Array.isArray(items) || items.length === 0) return;
      const modelLimit = Number(process.env.CUTCTX_MODEL_LIMIT ?? 2e5);
      const charBudget = modelLimit * 4;
      const size = JSON.stringify(items).length;
      if (size < charBudget * 0.85) return;
      const protectRecent = Number(process.env.CUTCTX_PROTECT_RECENT_TURNS ?? 4);
      const recent = items.slice(-protectRecent);
      const older = items.slice(0, -protectRecent);
      if (older.length === 0) return;
      const textOf = (item) => item.parts.filter((p) => p.type === "text").map((p) => p.text).join("\n");
      const canonical = older.map((item) => ({
        role: item.info.role === "assistant" ? "assistant" : "user",
        content: textOf(item)
      }));
      try {
        const result = await compress(canonical, { model: lastKnownModel ?? DEFAULT_MODEL });
        const compressedText = result.messages.map(
          (m) => typeof m.content === "string" ? m.content : JSON.stringify(m)
        ).join("\n\n");
        const template = older[older.length - 1].info;
        output.messages = [
          {
            info: template,
            parts: [
              {
                id: `cutctx-compressed-${template.id}`,
                sessionID: template.sessionID,
                messageID: template.id,
                type: "text",
                text: compressedText
              }
            ]
          },
          ...recent
        ];
      } catch (err) {
        warnCompressionFailure(
          "cutctx: history compress failed, passing through",
          err
        );
      }
    },
    "experimental.session.compacting": async (_input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return;
      output.context.push(
        "[cutctx: this session's prior turns were compressed by cutctx. Use the cutctx_retrieve MCP tool with CCR handles to fetch any originals you need.]"
      );
    }
  };
};
var cutctx_default = plugin;
export {
  cutctx_default as default
};
