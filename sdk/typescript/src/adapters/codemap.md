# sdk/typescript/src/adapters/

## Responsibility
Adds transparent pre-request Cutctx compression to common LLM SDK interfaces.

## Design
Wrapper/decorator functions preserve the underlying OpenAI, Anthropic, Gemini, or Vercel AI client/model shape while intercepting generation calls. Provider-specific modules convert messages to/from the canonical SDK representation and delegate actual compression to `compress`.

## Flow
Application calls wrapped provider API -> adapter extracts messages/model -> normalizes to OpenAI form -> calls Cutctx compression -> converts compressed messages back to provider form -> invokes the original provider client with remaining options.

## Integration
- Depends on `compress.ts`, message types, and format helpers.
- Intended for OpenAI-compatible clients, Anthropic Messages, Google Gemini models, and Vercel AI middleware.
