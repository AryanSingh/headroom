# crates/cutctx-py/

## Responsibility
Builds the `cutctx._core` Python native extension exposing selected `cutctx-core` algorithms and types.

## Design
A single PyO3 `cdylib` wraps Rust tokenizers, compressors, detectors, live-zone transforms, tag/keyword helpers, and stack graphs with Python-friendly classes/functions. Build support compiles a Linux glibc compatibility shim where needed.

## Flow
Python imports `_core` -> PyO3 module initialization registers wrappers and integrity protection -> method calls convert Python/JSON inputs to core types -> native algorithms execute -> results/errors convert back to Python objects.

## Integration
- Links directly to `cutctx-core` and is packaged through the Python build pipeline.
- Uses PyO3 and `build.rs`/`glibc_compat.c` for binary compatibility.
