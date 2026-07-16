# sdk/typescript/src/utils/

## Responsibility
Normalizes provider message formats, recursively converts naming conventions, and parses server-sent event streams.

## Design
`format.ts` detects OpenAI/Anthropic/Gemini shapes and converts through a canonical OpenAI representation. `case.ts` performs deep camel/snake conversion across arrays/objects. `stream.ts` exposes an async-generator SSE parser plus stream collection helper.

## Flow
Client/adapters normalize input messages -> request bodies become snake case -> response objects become camel case; streaming responses are decoded incrementally, split into SSE data frames, JSON-parsed where possible, and yielded until completion.

## Integration
- Used by `client.ts`, `compress.ts`, provider adapters, and public exports.
- Operates on standard fetch `Response`/ReadableStream primitives.
