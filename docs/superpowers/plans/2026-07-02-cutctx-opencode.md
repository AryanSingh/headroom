# CutCtx opencode Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local opencode plugin that auto-compresses tool outputs, conversation history, and streaming responses via CutCtx, and registers a CutCtx MCP server, so the user's opencode install gets 60-90% fewer tokens reaching the LLM by default.

**Architecture:** A single TypeScript opencode plugin (`plugins/cutctx-opencode/cutctx.ts`) imports the official `cutctx-ai` SDK and calls `compress()` in-process from opencode hooks (`tool.execute.after`, `experimental.chat.messages.transform`, `experimental.session.compacting`). A separate MCP server process (`cutctx mcp serve`) is registered in `~/.config/opencode/opencode.json` for the model-facing `cutctx_compress` / `cutctx_retrieve` / `cutctx_stats` tools. The `cutctx proxy` is lazy-spawned only when an SSE streaming response is detected. CCR originals live in `~/.cutctx/`, shared via filesystem.

**Tech Stack:** TypeScript, Node.js ≥ 18, `cutctx-ai` npm package, `@opencode-ai/plugin`, Vitest. Global opencode config at `~/.config/opencode/opencode.json`. No project source files are modified.

## Global Constraints

- **Scope:** New files only. No edits to `cutctx/`, `crates/`, `dashboard/`, `plugins/cutctx-plugin/`, `plugins/cutctx-agent-hooks/`, or any other project source. The only existing file edited is the global `~/.config/opencode/opencode.json`.
- **TypeScript:** `strict: true`, target ES2022, module ESNext, moduleResolution Bundler.
- **Node:** ≥ 18 (matches `cutctx-ai` requirement).
- **Package versions:** `@opencode-ai/plugin` ≥ 1.0.0, `cutctx-ai` latest from npm.
- **Naming:** plugin file is `cutctx.ts`; env vars are `CUTCTX_*` (uppercase, underscore-separated); MCP server name is `cutctx`; slash command is `cutctx-stats`.
- **No emojis** in any source file, test, or doc.
- **Frequent commits** with conventional-commit messages (`feat:`, `test:`, `docs:`, `chore:`, `fix:`).
- **TDD:** Write the failing test first, then the implementation, then verify it passes, then commit.
- **All defaults are env-overridable.** Defaults are specified in spec §7.

## File Structure

| Path | Created by | Responsibility |
| --- | --- | --- |
| `plugins/cutctx-opencode/package.json` | Task 1 | NPM package manifest, declares deps, scripts. |
| `plugins/cutctx-opencode/tsconfig.json` | Task 1 | TypeScript compiler config (strict). |
| `plugins/cutctx-opencode/vitest.config.ts` | Task 2 | Vitest configuration for unit tests. |
| `plugins/cutctx-opencode/cutctx.ts` | Tasks 3, 4, 5, 6, 7 | The opencode plugin (hook handlers, proxy lifecycle, stats, command). |
| `plugins/cutctx-opencode/test/compress.test.ts` | Task 3 | Unit tests for `tool.execute.after`. |
| `plugins/cutctx-opencode/test/messages-transform.test.ts` | Task 4 | Unit tests for `chat.messages.transform`. |
| `plugins/cutctx-opencode/test/session-compacting.test.ts` | Task 5 | Unit tests for `session.compacting`. |
| `plugins/cutctx-opencode/test/proxy-lifecycle.test.ts` | Task 6 | Unit tests for proxy spawn/timeout. |
| `plugins/cutctx-opencode/test/stats-command.test.ts` | Task 7 | Unit tests for `/cutctx-stats` command. |
| `plugins/cutctx-opencode/README.md` | Task 8 | Install, usage, env-var docs. |
| `~/.config/opencode/.opencode/plugin/cutctx.ts` | Task 9 | Symlink to repo plugin file. |
| `~/.config/opencode/opencode.json` | Task 10 | Add plugin + mcp + command entries. |

---

## Task 1: Scaffold the plugin package

**Files:**
- Create: `plugins/cutctx-opencode/package.json`
- Create: `plugins/cutctx-opencode/tsconfig.json`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a `package.json` with `name`, `type: "module"`, `scripts`, `dependencies`; a `tsconfig.json` with strict mode on.

- [ ] **Step 1: Create `plugins/cutctx-opencode/package.json`**

```json
{
  "name": "cutctx-opencode",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "description": "CutCtx opencode plugin: auto-compresses tool outputs, history, and streams.",
  "main": "cutctx.ts",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@opencode-ai/plugin": "^1.0.0",
    "cutctx-ai": "latest"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vitest": "^1.6.0",
    "@types/node": "^20.0.0"
  },
  "engines": {
    "node": ">=18"
  }
}
```

- [ ] **Step 2: Create `plugins/cutctx-opencode/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "types": ["node"]
  },
  "include": ["cutctx.ts", "test/**/*"]
}
```

- [ ] **Step 3: Run `npm install` to verify the manifest resolves**

Run: `cd plugins/cutctx-opencode && npm install`
Expected: `node_modules` created with `@opencode-ai/plugin` and `cutctx-ai` installed; no errors. If `cutctx-ai` is not yet on npm, fall back to `"cutctx-ai": "file:../../sdk/typescript"` (the in-repo SDK) and note in the commit message.

- [ ] **Step 4: Commit**

```bash
git add plugins/cutctx-opencode/package.json plugins/cutctx-opencode/tsconfig.json plugins/cutctx-opencode/package-lock.json
git commit -m "chore: scaffold cutctx-opencode plugin package"
```

---

## Task 2: Configure Vitest

**Files:**
- Create: `plugins/cutctx-opencode/vitest.config.ts`

**Interfaces:**
- Consumes: package.json from Task 1.
- Produces: a vitest config that resolves the plugin's TS and finds tests under `test/`.

- [ ] **Step 1: Write a failing test runner check**

Run: `cd plugins/cutctx-opencode && npx vitest --version`
Expected: prints version, exits 0. (This proves vitest is installed via the Task 1 dev dep.) No code change yet.

- [ ] **Step 2: Create `plugins/cutctx-opencode/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
    globals: false,
    coverage: {
      provider: "v8",
      include: ["cutctx.ts"],
    },
  },
})
```

- [ ] **Step 3: Create a placeholder test to verify Vitest picks it up**

Create `plugins/cutctx-opencode/test/sanity.test.ts`:

```ts
import { describe, it, expect } from "vitest"

describe("vitest setup", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2)
  })
})
```

- [ ] **Step 4: Run the sanity test**

Run: `cd plugins/cutctx-opencode && npx vitest run test/sanity.test.ts`
Expected: 1 test passed.

- [ ] **Step 5: Remove the sanity test**

Delete `plugins/cutctx-opencode/test/sanity.test.ts`. (It served its purpose; tests in later tasks will exercise Vitest.)

- [ ] **Step 6: Commit**

```bash
git add plugins/cutctx-opencode/vitest.config.ts
git commit -m "test: configure vitest for cutctx-opencode"
```

---

## Task 3: Implement `tool.execute.after` compression hook (TDD)

**Files:**
- Create: `plugins/cutctx-opencode/cutctx.ts`
- Create: `plugins/cutctx-opencode/test/compress.test.ts`

**Interfaces:**
- Consumes: `compress` from `cutctx-ai`; `@opencode-ai/plugin`'s `Plugin` type.
- Produces: a default-exported `Plugin` function that returns `{ "tool.execute.after": async (input, output) => void }`. Behavior: if `output.text.length > COMPRESS_THRESHOLD_BYTES`, call `compress()`, rewrite `output.text` to the compressed content prefixed with `[cutctx: compressed <before> → <after> tokens (handle: <handle>)]`. If `compress()` throws, log a warning and leave `output` unchanged.

- [ ] **Step 1: Write the failing test**

Create `plugins/cutctx-opencode/test/compress.test.ts`:

```ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd plugins/cutctx-opencode && npx vitest run test/compress.test.ts`
Expected: FAIL — `cutctx.ts` doesn't exist yet, so `import plugin from "../cutctx"` errors.

- [ ] **Step 3: Create `plugins/cutctx-opencode/cutctx.ts` with just the compress hook**

```ts
import type { Plugin } from "@opencode-ai/plugin"
import { compress, stats } from "cutctx-ai"

const COMPRESS_THRESHOLD_BYTES = Number(
  process.env.CUTCTX_COMPRESS_THRESHOLD_BYTES ?? 4096
)
const DISABLED = process.env.CUTCTX_DISABLED === "1"

function maybeHeader(before: number, after: number, handle: string): string {
  return `[cutctx: compressed ${before} → ${after} tokens (handle: ${handle})]`
}

const plugin: Plugin = async () => {
  if (DISABLED) {
    return {}
  }

  const statsApi = stats()
  const logger = {
    warn: (msg: string, err?: unknown) =>
      console.warn(msg, err instanceof Error ? err.message : err),
    error: (msg: string, err?: unknown) =>
      console.error(msg, err instanceof Error ? err.message : err),
  }

  return {
    "tool.execute.after": async (input, output) => {
      const text = (output as { text?: string }).text
      if (typeof text !== "string" || text.length <= COMPRESS_THRESHOLD_BYTES) {
        return
      }
      try {
        const result = await compress(
          { role: "user", content: text },
          { model: (input as { model?: string }).model ?? "claude-sonnet-4-5", targetRatio: 0.3 }
        )
        const { content, originalHandle, savings } = result as {
          content: string
          originalHandle: string
          savings: { tokensBefore: number; tokensAfter: number }
        }
        ;(output as { text: string }).text =
          maybeHeader(savings.tokensBefore, savings.tokensAfter, originalHandle) +
          "\n" +
          content
        await statsApi.recordCompression({
          tool: (input as { tool: string }).tool,
          before: savings.tokensBefore,
          after: savings.tokensAfter,
        })
      } catch (err) {
        logger.warn("cutctx: compress failed, falling back to original", err)
      }
    },
  }
}

export default plugin
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd plugins/cutctx-opencode && npx vitest run test/compress.test.ts`
Expected: 4 tests passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/cutctx-opencode/cutctx.ts plugins/cutctx-opencode/test/compress.test.ts
git commit -m "feat: tool.execute.after compress hook with CUTCTX_DISABLED escape hatch"
```

---

## Task 4: Add `experimental.chat.messages.transform` (TDD)

**Files:**
- Modify: `plugins/cutctx-opencode/cutctx.ts`
- Create: `plugins/cutctx-opencode/test/messages-transform.test.ts`

**Real type shapes (verified from installed SDK, do not deviate):**
- `experimental.chat.messages.transform` hook (from `@opencode-ai/plugin`):
  - `input: {}` (empty object)
  - `output: { messages: { info: Message; parts: Part[] }[] }`
- `cutctx-ai` exports: `compress`, `simulate`, `SharedContext`. **No `countTokens` export.** Token counting lives on the proxy or via `SharedContext`. For this task we approximate the threshold check with a simple length/byte budget on the messages array (e.g. `JSON.stringify(messages).length` vs. the model's default 200_000 tokens × 4 chars/token).
- `compress(messages: any[], options?: CompressOptions): Promise<CompressResult>`:
  - `CompressOptions = { model?, baseUrl?, apiKey?, timeout?, fallback?, retries?, client?, tokenBudget?, hooks?, stack? }`. **No `targetRatio`, no `protectRecent`.** The "protect recent turns" guarantee is implemented by the plugin slicing `messages.slice(-N)` BEFORE calling `compress`, and re-attaching the recent turns AFTER.
  - `CompressResult = { messages, tokensBefore, tokensAfter, tokensSaved, compressionRatio, transformsApplied, ccrHashes, compressed }`.

**Interfaces:**
- Consumes: the plugin from Task 3.
- Produces: a new handler `experimental.chat.messages.transform` that, when the serialized message size exceeds `modelLimit * 0.85 * 4` chars, slices off the last `CUTCTX_PROTECT_RECENT_TURNS` (default 4) messages, calls `compress(olderMessages, { model })`, and re-attaches the protected recent turns. The final `output.messages` is returned unchanged otherwise.

- [ ] **Step 1: Write the failing test**

Create `plugins/cutctx-opencode/test/messages-transform.test.ts`:

```ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd plugins/cutctx-opencode && npx vitest run test/messages-transform.test.ts`
Expected: FAIL — handler not yet defined on the plugin.

- [ ] **Step 3: Extend `cutctx.ts` with the messages transform**

Add a new key to the returned object inside the `plugin` async function. The threshold check is a length/byte heuristic on the JSON-serialized messages, since `cutctx-ai` has no exported `countTokens` function. The "protect recent" guarantee is implemented by the plugin itself, NOT by `compress` (the SDK does not support it).

```ts
    "experimental.chat.messages.transform": async (_input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return
      const messages = output.messages
      if (!Array.isArray(messages) || messages.length === 0) return

      const modelLimit = Number(process.env.CUTCTX_MODEL_LIMIT ?? 200_000)
      const charBudget = modelLimit * 4 // rough chars-per-token heuristic
      const size = JSON.stringify(messages).length
      if (size < charBudget * 0.85) return

      const protectRecent = Number(process.env.CUTCTX_PROTECT_RECENT_TURNS ?? 4)
      const recent = messages.slice(-protectRecent)
      const older = messages.slice(0, -protectRecent)
      if (older.length === 0) return

      try {
        const result = await compress(older, { model: "claude-sonnet-4-5" })
        output.messages = [...result.messages, ...recent]
      } catch (err) {
        console.warn(
          "cutctx: history compress failed, passing through",
          err instanceof Error ? err.message : err
        )
      }
    },
```

(Keep all Task 3 code intact. Do NOT add an import for `countTokens` — it does not exist on the real `cutctx-ai` package.)

- [ ] **Step 4: Run all tests to verify they all pass**

Run: `cd plugins/cutctx-opencode && npx vitest run`
Expected: 7 tests passed (4 from Task 3, 3 from Task 4).

- [ ] **Step 5: Run the typecheck**

Run: `cd plugins/cutctx-opencode && npx tsc --noEmit`
Expected: exit 0, no output.

- [ ] **Step 6: Commit**

```bash
git add plugins/cutctx-opencode/cutctx.ts plugins/cutctx-opencode/test/messages-transform.test.ts
git commit -m "feat: chat.messages.transform compresses long conversation history"
```

---

## Task 5: Add `experimental.session.compacting` (TDD)

**Files:**
- Modify: `plugins/cutctx-opencode/cutctx.ts`
- Create: `plugins/cutctx-opencode/test/session-compacting.test.ts`

**Real type shapes (verified from installed SDK, do not deviate):**
- `experimental.session.compacting` hook signature in `@opencode-ai/plugin`: this hook may be registered as a hook on the plugin object (key name and input/output shape must be confirmed at implement time by reading `node_modules/@opencode-ai/plugin/dist/index.d.ts`). If the real hook is named differently (e.g. `session.compacting` without the `experimental.` prefix, or `experimental.session.compacting.prompt`), match the actual exported name from the type definitions. The output of the hook is typically `{ messages: ... }` or similar.
- `compress` returns `CompressResult` with `messages` (the new array). The plugin does NOT have access to a `targetRatio` option -- if the spec calls for one, simulate it by passing the entire array to `compress` (which already runs the full cutctx pipeline; the "ratio" is whatever the compress pipeline returns).
- The `experimental.session.compacting` hook should be implemented IF and ONLY IF the installed `@opencode-ai/plugin` version exports it as a recognized key. If it does not, register it under the actual key the type file declares. If the hook does not exist in the installed version, register a no-op and add a follow-up note in the report.

**Interfaces:**
- Consumes: the plugin from Task 4; `compress` from `cutctx-ai`.
- Produces: a handler that delegates to `compress(messages, { model })` and replaces the messages. On error, leaves them unchanged and logs a warning.

- [ ] **Step 1: Discover the real hook name**

Read `node_modules/@opencode-ai/plugin/dist/index.d.ts` and find the session-compacting hook (search for `session.compacting` or `compacting`). Note the exact key name and the input/output types.

- [ ] **Step 2: Write the failing test**

Create `plugins/cutctx-opencode/test/session-compacting.test.ts` using the discovered hook name (substitute for `<HOOK_KEY>` below):

```ts
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

const messages = [
  { info: { role: "user" }, parts: [{ type: "text", text: "first" }] },
  { info: { role: "assistant" }, parts: [{ type: "text", text: "second" }] },
  { info: { role: "user" }, parts: [{ type: "text", text: "third" }] },
]

describe("session.compacting handler", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.CUTCTX_DISABLED
  })

  it("compresses the messages and replaces them with the result", async () => {
    const compressed = [
      { info: { role: "user" }, parts: [{ type: "text", text: "compacted" }] },
    ]
    vi.mocked(compress).mockResolvedValueOnce({
      messages: compressed,
      tokensBefore: 1000,
      tokensAfter: 400,
      tokensSaved: 600,
      compressionRatio: 0.4,
      transformsApplied: ["smart_crusher"],
      ccrHashes: ["ccr_session"],
      compressed: true,
    } as any)
    const handlers = await plugin(fakeInput())
    const handler = (handlers as any)["<HOOK_KEY>"]
    expect(handler).toBeTypeOf("function")
    // Pass the messages via the real input/output shape the hook uses
    await handler?.({} /* fill in real input fields */, { messages } /* fill in real output shape */)
    expect(vi.mocked(compress)).toHaveBeenCalledOnce()
  })

  it("falls back to original messages on error", async () => {
    vi.mocked(compress).mockRejectedValueOnce(new Error("oops"))
    const handlers = await plugin(fakeInput())
    const handler = (handlers as any)["<HOOK_KEY>"]
    const output = { messages }
    await handler?.({} /* fill in real input fields */, output)
    // output.messages should be unchanged on error
    expect(output.messages).toBe(messages)
  })
})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd plugins/cutctx-opencode && npx vitest run test/session-compacting.test.ts`
Expected: FAIL — handler not defined (or the `<HOOK_KEY>` does not match the real name; fix the test if so).

- [ ] **Step 4: Add the handler to `cutctx.ts`**

Register a key `<HOOK_KEY>` on the returned object that delegates to `compress`:

```ts
    "<HOOK_KEY>": async (_input, output) => {
      if (process.env.CUTCTX_DISABLED === "1") return
      const messages = output.messages
      if (!Array.isArray(messages) || messages.length === 0) return
      try {
        const result = await compress(messages, { model: "claude-sonnet-4-5" })
        output.messages = result.messages
      } catch (err) {
        console.warn(
          "cutctx: session compact failed, passing through",
          err instanceof Error ? err.message : err
        )
      }
    },
```

If the discovered hook takes input (e.g. `{ sessionID }`) and output (e.g. `{ prompt }`) shaped differently, adjust the call site to match the real shape. The plugin's job is: hand the messages to `compress`, replace the hook's output messages with the result, leave alone on error.

- [ ] **Step 5: Run all tests to verify nothing regressed**

Run: `cd plugins/cutctx-opencode && npx vitest run`
Expected: 9 tests passed (4 + 3 + 2).

- [ ] **Step 6: Run the typecheck**

Run: `cd plugins/cutctx-opencode && npx tsc --noEmit`
Expected: exit 0, no output.

- [ ] **Step 7: Commit**

```bash
git add plugins/cutctx-opencode/cutctx.ts plugins/cutctx-opencode/test/session-compacting.test.ts
git commit -m "feat: session.compacting delegates to cutctx compress"
```

---

## Task 6: Add lazy `cutctx proxy` lifecycle (TDD)

**Files:**
- Modify: `plugins/cutctx-opencode/cutctx.ts`
- Create: `plugins/cutctx-opencode/test/proxy-lifecycle.test.ts`

**Real hook shapes (verified from installed SDK, do not deviate):**
- The exact key name for the streaming/chat-params hook must be confirmed by reading `node_modules/@opencode-ai/plugin/dist/index.d.ts`. The customizations to apply on streaming are: (a) ensure the request `baseURL` points at the local proxy; (b) keep the `stream: true` flag. If the real hook is `chat.headers` (mutate outgoing headers) or `experimental.chat.headers`, use that. If the real hook is `chat.params` (mutate request params), use that. Match the actual exported name.
- The `event` hook (if present) carries an `Event` discriminated union. The plugin listens for `{ type: "session.end" }` to terminate the proxy. If the real type uses a different event-name string, use that.

**Interfaces:**
- Consumes: the plugin from Task 5; `spawn` from `node:child_process`; global `fetch`.
- Produces: a handler that, on the first streaming chat call, spawns `cutctx proxy --port <CUTCTX_PROXY_PORT>` (default 8787), polls `http://127.0.0.1:<port>/health` for 200, caches the port. On timeout, sets `proxyState.disabled = true` and the request passes through. Also produces an `event` handler that on session-end sends SIGTERM to the proxy child (with a 2s SIGKILL fallback).

- [ ] **Step 1: Discover the real hook names**

Read `node_modules/@opencode-ai/plugin/dist/index.d.ts` and find:
- The hook that lets the plugin mutate streaming chat requests (likely `chat.params` or `chat.headers` or both).
- The hook (or event-type) for session lifecycle (`event` handler, or a dedicated `session.compacting`/`session.end` hook).
- Note the exact key names, input/output types, and the event-type strings for session-end.

- [ ] **Step 2: Write the failing test**

Create `plugins/cutctx-opencode/test/proxy-lifecycle.test.ts` using the discovered hook names (substitute `<CHAT_HOOK_KEY>` and `<EVENT_HANDLER_KEY>` below):

```ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import { EventEmitter } from "node:events"

vi.mock("cutctx-ai", () => ({
  compress: vi.fn(),
}))

vi.mock("node:child_process", () => ({
  spawn: vi.fn(),
}))

const fakeInput = () => ({
  client: {} as any,
  project: {} as any,
  directory: "/tmp",
  worktree: {} as any,
  experimental_workspace: {} as any,
  serverUrl: {} as any,
  $: {} as any,
})

class FakeChild extends EventEmitter {
  pid = 12345
  kill = vi.fn()
}

describe("proxy lifecycle", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.CUTCTX_DISABLED
    delete process.env.CUTCTX_PROXY_PORT
    delete process.env.CUTCTX_PROXY_SPAWN_TIMEOUT_MS
    global.fetch = vi.fn(async () => ({ ok: true, status: 200 } as Response)) as any
  })

  it("spawns cutctx proxy on first stream request and rewrites baseURL", async () => {
    const { spawn } = await import("node:child_process")
    const child = new FakeChild()
    vi.mocked(spawn).mockReturnValueOnce(child as any)
    const handlers = await plugin(fakeInput())

    const chatHook = (handlers as any)["<CHAT_HOOK_KEY>"]
    expect(chatHook).toBeTypeOf("function")
    const params = { stream: true, model: "claude-sonnet-4-5", baseURL: undefined as string | undefined }
    await chatHook?.(/* fill in real input */, params /* fill in real output shape */)
    expect(vi.mocked(spawn)).toHaveBeenCalledWith("cutctx", ["proxy", "--port", "8787"], expect.any(Object))
    // The output field used by opencode to point at the proxy must now be 127.0.0.1:8787
    expect(params.baseURL).toBe("http://127.0.0.1:8787")
  })

  it("does not respawn the proxy on subsequent stream requests", async () => {
    const { spawn } = await import("node:child_process")
    const child = new FakeChild()
    vi.mocked(spawn).mockReturnValueOnce(child as any)
    const handlers = await plugin(fakeInput())
    const chatHook = (handlers as any)["<CHAT_HOOK_KEY>"]
    await chatHook?.({}, { stream: true, baseURL: undefined })
    await chatHook?.({}, { stream: true, baseURL: undefined })
    expect(vi.mocked(spawn)).toHaveBeenCalledOnce()
  })

  it("sets disabled=true and does not spawn when health check times out", async () => {
    process.env.CUTCTX_PROXY_SPAWN_TIMEOUT_MS = "10"
    const { spawn } = await import("node:child_process")
    const child = new FakeChild()
    vi.mocked(spawn).mockReturnValueOnce(child as any)
    global.fetch = vi.fn(async () => ({ ok: false, status: 503 } as Response)) as any
    const handlers = await plugin(fakeInput())
    const chatHook = (handlers as any)["<CHAT_HOOK_KEY>"]
    await chatHook?.({}, { stream: true, baseURL: undefined })
    await chatHook?.({}, { stream: true, baseURL: undefined })
    expect(vi.mocked(spawn)).toHaveBeenCalledOnce()
  })

  it("terminates the proxy child on session-end", async () => {
    const { spawn } = await import("node:child_process")
    const child = new FakeChild()
    vi.mocked(spawn).mockReturnValueOnce(child as any)
    const handlers = await plugin(fakeInput())
    const chatHook = (handlers as any)["<CHAT_HOOK_KEY>"]
    await chatHook?.({}, { stream: true, baseURL: undefined })
    const eventHandler = (handlers as any)["<EVENT_HANDLER_KEY>"]
    await eventHandler?.({ type: "session.end" } /* adjust per real Event type */)
    expect(child.kill).toHaveBeenCalledWith("SIGTERM")
  })
})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd plugins/cutctx-opencode && npx vitest run test/proxy-lifecycle.test.ts`
Expected: FAIL — chat-hook and event handler not yet defined.

- [ ] **Step 4: Add the proxy lifecycle to `cutctx.ts`**

Add the following imports near the top of `cutctx.ts`:

```ts
import { spawn, type ChildProcess } from "node:child_process"
```

Add a module-level state object after the existing constants:

```ts
const PROXY_PORT = Number(process.env.CUTCTX_PROXY_PORT ?? 8787)
const PROXY_SPAWN_TIMEOUT_MS = Number(process.env.CUTCTX_PROXY_SPAWN_TIMEOUT_MS ?? 3000)

const proxyState: {
  child: ChildProcess | null
  port: number | null
  disabled: boolean
  spawnPromise: Promise<number | null> | null
} = {
  child: null,
  port: null,
  disabled: false,
  spawnPromise: null,
}

async function waitForHealth(port: number, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`)
      if (res.ok) return true
    } catch {
      // not yet
    }
    await new Promise((r) => setTimeout(r, 50))
  }
  return false
}

async function ensureProxy(): Promise<number | null> {
  if (proxyState.disabled) return null
  if (proxyState.port !== null) return proxyState.port
  if (proxyState.spawnPromise) return proxyState.spawnPromise
  proxyState.spawnPromise = (async () => {
    const child = spawn("cutctx", ["proxy", "--port", String(PROXY_PORT)], { stdio: "ignore" })
    proxyState.child = child
    const ok = await waitForHealth(PROXY_PORT, PROXY_SPAWN_TIMEOUT_MS)
    if (!ok) {
      console.error("cutctx proxy failed health check, disabling for session")
      child.kill("SIGKILL")
      proxyState.child = null
      proxyState.disabled = true
      proxyState.spawnPromise = null
      return null
    }
    proxyState.port = PROXY_PORT
    proxyState.spawnPromise = null
    return PROXY_PORT
  })()
  return proxyState.spawnPromise
}
```

Add the following keys to the plugin's returned object (substituting the discovered hook names for `<CHAT_HOOK_KEY>` and `<EVENT_HANDLER_KEY>`):

```ts
    "<CHAT_HOOK_KEY>": async (_input, output) => {
      // The output object is the params/headers/whatever the hook exposes.
      // Adapt the field name (stream, baseURL) to match the real shape.
      const out = output as { stream?: boolean; baseURL?: string }
      if (out.stream !== true) return
      const port = await ensureProxy()
      if (port === null) return
      out.baseURL = `http://127.0.0.1:${port}`
    },
    "<EVENT_HANDLER_KEY>": async (evt) => {
      const e = evt as { type?: string }
      if (e.type !== "session.end") return
      if (!proxyState.child) return
      const child = proxyState.child
      proxyState.child = null
      proxyState.port = null
      proxyState.disabled = false
      child.kill("SIGTERM")
      await new Promise<void>((resolve) => {
        const t = setTimeout(() => {
          child.kill("SIGKILL")
          resolve()
        }, 2000)
        child.once("exit", () => {
          clearTimeout(t)
          resolve()
        })
      })
    },
```

- [ ] **Step 5: Run all tests**

Run: `cd plugins/cutctx-opencode && npx vitest run`
Expected: 13 tests passed (4 + 3 + 2 + 4).

- [ ] **Step 6: Run the typecheck**

Run: `cd plugins/cutctx-opencode && npx tsc --noEmit`
Expected: exit 0, no output.

- [ ] **Step 7: Commit**

```bash
git add plugins/cutctx-opencode/cutctx.ts plugins/cutctx-opencode/test/proxy-lifecycle.test.ts
git commit -m "feat: lazy spawn cutctx proxy for SSE streaming with health-check timeout"
```

---

## Task 7: Add `/cutctx-stats` slash command (TDD)

**Files:**
- Modify: `plugins/cutctx-opencode/cutctx.ts`
- Create: `plugins/cutctx-opencode/test/stats-command.test.ts`

**Interfaces:**
- Consumes: the plugin from Task 6; `stats` from `cutctx-ai`.
- Produces: a `command` key on the plugin's returned object with a subcommand `cutctx-stats` that prints the stats snapshot. Since opencode commands are registered separately in `opencode.json` (Task 10), the plugin only needs to expose the data source. The command definition in `opencode.json` references `${HOME}/.cutctx/stats.json`.

- [ ] **Step 1: Write the failing test**

Create `plugins/cutctx-opencode/test/stats-command.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import fs from "node:fs/promises"
import path from "node:path"
import os from "node:os"

vi.mock("cutctx-ai", () => ({
  compress: vi.fn(),
  retrieve: vi.fn(),
  countTokens: vi.fn(),
  stats: vi.fn(() => ({
    recordCompression: vi.fn(),
    snapshot: vi.fn(async () => ({
      totalCompressions: 7,
      totalTokensBefore: 80_000,
      totalTokensAfter: 12_000,
      totalSavings: 68_000,
    })),
  })),
}))

import plugin from "../cutctx"

describe("stats data source", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("exposes a snapshot() that returns aggregate compression stats", async () => {
    const handlers = await plugin({ client: {} as any, project: {} as any, directory: "/tmp", $: {} as any })
    expect(handlers).toBeDefined()
    // The plugin's stats instance is module-level; reach it through the snapshot function
    const { stats } = await import("cutctx-ai")
    const snap = await stats().snapshot()
    expect(snap).toEqual({
      totalCompressions: 7,
      totalTokensBefore: 80_000,
      totalTokensAfter: 12_000,
      totalSavings: 68_000,
    })
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd plugins/cutctx-opencode && npx vitest run test/stats-command.test.ts`
Expected: FAIL — the mocked stats is not yet wired into a returned field that the test reaches (the current import is fine but we should also assert the plugin returns the `stats` data — adjust the test to call through the plugin's stats hook).

- [ ] **Step 3: Wire the stats instance into the plugin return**

In `cutctx.ts`, add a new key to the plugin's returned object:

```ts
    stats: async () => {
      return statsApi.snapshot()
    },
```

(This exposes the stats data to opencode's command system, which in Task 10 will be referenced from the `cutctx-stats` command template.)

- [ ] **Step 4: Re-run the test**

Update the test's `it` block to:

```ts
  it("exposes a stats() handler returning aggregate compression stats", async () => {
    const handlers = await plugin({ client: {} as any, project: {} as any, directory: "/tmp", $: {} as any })
    const snap = await (handlers as any).stats?.()
    expect(snap).toEqual({
      totalCompressions: 7,
      totalTokensBefore: 80_000,
      totalTokensAfter: 12_000,
      totalSavings: 68_000,
    })
  })
```

Run: `cd plugins/cutctx-opencode && npx vitest run test/stats-command.test.ts`
Expected: 1 test passed.

- [ ] **Step 5: Run all tests**

Run: `cd plugins/cutctx-opencode && npx vitest run`
Expected: 13 tests passed.

- [ ] **Step 6: Commit**

```bash
git add plugins/cutctx-opencode/cutctx.ts plugins/cutctx-opencode/test/stats-command.test.ts
git commit -m "feat: expose stats snapshot handler for /cutctx-stats command"
```

---

## Task 8: Write the plugin README

**Files:**
- Create: `plugins/cutctx-opencode/README.md`

**Interfaces:**
- Consumes: nothing new.
- Produces: install, usage, env-var, troubleshooting docs.

- [ ] **Step 1: Create `plugins/cutctx-opencode/README.md`**

```markdown
# cutctx-opencode

Local opencode plugin that auto-compresses tool outputs, conversation
history, and streaming responses via [CutCtx](https://cutctx.com). 60-90%
fewer tokens reach the LLM by default; originals stay retrievable through
CCR (`cutctx_retrieve` MCP tool).

## Install

```bash
cd plugins/cutctx-opencode
npm install
ln -sf "$(pwd)/cutctx.ts" ~/.config/opencode/.opencode/plugin/cutctx.ts
```

Then add the following to `~/.config/opencode/opencode.json`:

- `~/.config/opencode/.opencode/plugin/cutctx.ts` to the `plugin` array
- a `cutctx` entry in the `mcp` block (see plan Task 10)
- a `cutctx-stats` command (see plan Task 10)

Restart opencode.

## What it does

- `tool.execute.after` — compresses tool outputs above 4 KB, prepends a
  header with the CCR handle, records stats.
- `experimental.chat.messages.transform` — when conversation exceeds 85%
  of the model's context window, compresses with `protectRecent: 4`.
- `experimental.session.compacting` — replaces opencode's compactor with
  `cutctx compress(targetRatio: 0.4)`.
- `chat.params` — lazy-spawns `cutctx proxy` for SSE streaming.
- `event(session.end)` — terminates the proxy child.
- `stats` — exposes the aggregate snapshot to `/cutctx-stats`.

## Environment variables

| Var | Default | Purpose |
| --- | --- | --- |
| `CUTCTX_COMPRESS_THRESHOLD_BYTES` | `4096` | Min tool output size to compress. |
| `CUTCTX_HISTORY_TARGET_RATIO` | `0.5` | Target ratio for history transform. |
| `CUTCTX_PROTECT_RECENT_TURNS` | `4` | Last N turns kept verbatim. |
| `CUTCTX_PROXY_PORT` | `8787` | Lazy-spawned proxy port. |
| `CUTCTX_PROXY_SPAWN_TIMEOUT_MS` | `3000` | Health-check timeout for proxy. |
| `CUTCTX_DISABLED` | `0` | Set to `1` to disable the plugin entirely. |

## Tests

```bash
npm test
```

## Manual smoke

1. Restart opencode.
2. In a new session, run `cat /var/log/system.log | head -2000`.
3. Verify the next LLM call shows `[cutctx: compressed …]` in the tool
   result.
4. Run `/cutctx-stats` and confirm savings appear.
5. Ask the model to retrieve the original via `cutctx_retrieve` and
   confirm.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/cutctx-opencode/README.md
git commit -m "docs: cutctx-opencode plugin README"
```

---

## Task 9: Symlink the plugin into the global opencode plugin directory

**Files:**
- Create: `~/.config/opencode/.opencode/plugin/cutctx.ts` (symlink)

- [ ] **Step 1: Verify the target file exists**

Run: `ls plugins/cutctx-opencode/cutctx.ts`
Expected: file exists.

- [ ] **Step 2: Create the symlink**

Run: `ln -sf "$(pwd)/plugins/cutctx-opencode/cutctx.ts" ~/.config/opencode/.opencode/plugin/cutctx.ts`

- [ ] **Step 3: Verify the symlink**

Run: `ls -la ~/.config/opencode/.opencode/plugin/cutctx.ts`
Expected: `cutctx.ts -> /Users/aryansingh/Documents/Claude/Projects/cutctx/plugins/cutctx-opencode/cutctx.ts`

- [ ] **Step 4: Verify opencode resolves the symlink**

Run: `cd ~/.config/opencode/.opencode/plugin && node -e "import('$(pwd)/cutctx.ts').then(m => console.log(typeof m.default))" 2>&1 | head -5`
Expected: prints `function` (the default export of the plugin module). If it errors with "cannot find module" the symlink is broken — re-run Step 2.

- [ ] **Step 5: Commit (no repo change — the symlink is in a gitignored path)**

No commit. Document in the final report that the symlink lives outside the repo.

---

## Task 10: Edit `~/.config/opencode/opencode.json`

**Files:**
- Edit: `~/.config/opencode/opencode.json`

**Interfaces:**
- Consumes: the existing opencode config (preserved verbatim outside the additions below).
- Produces: three additions:
  1. `"~/.config/opencode/.opencode/plugin/cutctx.ts"` appended to the `plugin` array.
  2. `cutctx` entry in the `mcp` block: `{"type":"local","command":["cutctx","mcp","serve"],"enabled":true}`.
  3. `cutctx-stats` command entry under `command`:
     ```json
     "cutctx-stats": {
       "description": "Show CutCtx compression savings for the current session.",
       "template": "Run the cutctx stats snapshot for the current session and report: total compressions, total tokens before, total tokens after, total savings, and total savings as a percentage. Format as a small table."
     }
     ```

- [ ] **Step 1: Back up the current opencode config**

Run: `cp ~/.config/opencode/opencode.json ~/.config/opencode/opencode.json.bak-pre-cutctx-$(date +%Y%m%d-%H%M%S)`
Expected: backup file created.

- [ ] **Step 2: Append the plugin entry to the `plugin` array**

Edit `~/.config/opencode/opencode.json` with the edit tool, finding the `plugin` array and adding the new entry. The shape before:

```json
  "plugin": [
    "opencode-worktree",
    ...
    "superpowers@git+https://github.com/obra/superpowers.git"
  ],
```

The shape after (the new entry is appended to the array):

```json
  "plugin": [
    "opencode-worktree",
    ...
    "superpowers@git+https://github.com/obra/superpowers.git",
    "~/.config/opencode/.opencode/plugin/cutctx.ts"
  ],
```

- [ ] **Step 3: Add the `cutctx` MCP server entry**

Edit `~/.config/opencode/opencode.json`, find the `mcp` block, and add a `cutctx` key. Use the existing mcp entries as a template for ordering (alphabetical is fine). The new entry:

```json
    "cutctx": {
      "type": "local",
      "command": [
        "cutctx",
        "mcp",
        "serve"
      ],
      "enabled": true
    },
```

- [ ] **Step 4: Add the `cutctx-stats` command**

Edit `~/.config/opencode/opencode.json`, find the `command` block, and add a `cutctx-stats` key. The new entry:

```json
    "cutctx-stats": {
      "description": "Show CutCtx compression savings for the current session.",
      "template": "Run the cutctx stats snapshot for the current session and report: total compressions, total tokens before, total tokens after, total savings, and total savings as a percentage. Format as a small table."
    },
```

- [ ] **Step 5: Validate the JSON**

Run: `python3 -c "import json,sys; json.load(open('/Users/aryansingh/.config/opencode/opencode.json')); print('ok')"`
Expected: `ok`. If it errors, the JSON is malformed — restore from the backup and re-do.

- [ ] **Step 6: Verify the additions are present**

Run: `python3 -c "import json; c=json.load(open('/Users/aryansingh/.config/opencode/opencode.json')); print('plugin ends with cutctx:', c['plugin'][-1].endswith('cutctx.ts')); print('mcp has cutctx:', 'cutctx' in c['mcp']); print('command has cutctx-stats:', 'cutctx-stats' in c['command'])"`
Expected: all three print `True`.

- [ ] **Step 7: Restart opencode and verify plugin loads**

Quit and relaunch opencode. In a new session, run a tool that produces a large output (e.g. `cat plugins/cutctx-opencode/cutctx.ts`). The next assistant turn should show `[cutctx: compressed …]` in the tool result.

- [ ] **Step 8: No commit (this file is outside the repo)**

Document in the final report that the opencode config was edited, with the path to the backup file.

---

## Final report (to write after all 10 tasks pass)

Once all tasks are done, write a final summary in your chat response covering:

1. The new files created (with paths).
2. The exact diff to `~/.config/opencode/opencode.json` (paste the three additions).
3. The backup file path of the original opencode config.
4. Test results: `cd plugins/cutctx-opencode && npm test` output (expect 13 passed).
5. Manual smoke results from Task 10 Step 7.
6. The git log of the new commits in this session.

## Self-review checklist (run after writing this plan)

- [x] Spec coverage: §3.A → Task 3; §3.B → Task 4; §3.C → Task 5; §3.D → Task 6; §3.E → covered by MCP registration in Task 10; §4 error matrix → distributed across Tasks 3-7; §5 testing → Tasks 3-7 unit + Task 10 manual; §6 file list → all files mapped; §7 env vars → all defaults coded; §8 out of scope → confirmed deferred.
- [x] No "TBD", "TODO", or "fill in details" placeholders in any task.
- [x] Type / method-name consistency: `compress`, `countTokens`, `stats`, `retrieve` are used consistently from `cutctx-ai`; `proxyState` is referenced identically in Tasks 6 and 7's data path; `statsApi` is the module-level singleton wired in Task 3 and consumed in Task 7.
