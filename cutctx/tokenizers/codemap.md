# cutctx/tokenizers/

## Responsibility
Provides model-aware token counting behind a uniform interface.

## Design
A tokenizer protocol has Tiktoken, Hugging Face, Mistral, and estimator strategies; a registry selects by model/provider.

## Flow
Callers submit content and a model hint; the registry resolves a counter and returns exact or estimated counts.

## Integration
Used by budgeting, transforms, routing, cost, and evals; optional adapters load tokenizer libraries.
