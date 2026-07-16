# crates/cutctx-core/src/signals/

## Responsibility
Provides reusable, non-mutating importance classifiers that inform multiple compression strategies.

## Design
`LineImportanceDetector` defines per-line classification into typed categories/confidence. `KeywordDetector` uses a shared Aho-Corasick registry; `Tiered` composes multiple detectors as an ordered chain without inheritance.

## Flow
A transform supplies a line and contextual metadata -> tiered detectors evaluate in order -> the best confident `ImportanceSignal` is returned -> caller uses priority/category to retain errors, identifiers, or other salient lines.

## Integration
- Shared by log, diff, search, text, and smart compression logic.
- Kept above `transforms/` so classification is reusable and side-effect free.
