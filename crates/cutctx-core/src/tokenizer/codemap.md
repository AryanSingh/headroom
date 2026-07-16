# crates/cutctx-core/src/tokenizer/

## Responsibility
Provides deterministic native token counting across OpenAI-compatible BPE models, registered Hugging Face tokenizers, and calibrated estimation fallbacks.

## Design
The thread-safe `Tokenizer` strategy trait exposes counting and backend identity. `TiktokenCounter`, `HfTokenizer`, and `EstimatingCounter` are concrete strategies; the registry detects model families, supports prefix-based HF registration, and returns a suitable implementation.

## Flow
Caller requests a tokenizer for a model -> registry chooses tiktoken, an installed HF tokenizer, or estimator -> `count_text` returns a stable count -> transforms use before/after counts to size and validate output.

## Integration
- Used throughout transforms and exposed by Python bindings.
- Backed by `tiktoken-rs`, Hugging Face tokenizers/hub, and local estimation rules.
