# ADR-003: USearch as Optional Extra vs Default Backend

- **Status:** Accepted
- **Date:** 2026-06-30
- **Drivers:** cutctx

---

## Context

USearch (Unum's vector search library) provides significant performance improvements over Cutctx's existing vector backends:

- **~10× faster** search than sqlite-vec
- **~50% memory savings** via f16 quantization vs f32
- **Zero-copy memory-mapped** index loading for instant restarts

However, adding it as a mandatory dependency has tradeoffs:

1. **Install footprint** — `usearch` pulls in `numpy` and native extensions. Cutctx's core is intentionally dependency-light.
2. **Existing users** — Thousands of existing installations work with `sqlite-vec` (bundled in proxy) or `hnswlib`. Forcing `usearch` would break stable deployments without benefit.
3. **Semantic weight** — Vector search is only relevant for the memory subsystem. Users who only use Cutctx for compression should not pay the cost.

Cutctx already has a clean plugin architecture for vector backends (`VectorBackend` enum in `config.py`, `create_vector_backend()` in `factory.py`). The question was: should `usearch` be the new default (bundled in `[all]`), or kept as an optional extra in the `[memory]` group?

## Decision

**USearch is an optional extra in the `[memory]` group**, not a mandatory dependency or part of `[all]`.

- Installed via: `pip install usearch` or `pip install cutctx-ai[memory]`
- Not included in: `pip install cutctx-ai` (core) or `pip install cutctx-ai[all]` (broad bundle)
- The `AUTO` fallback chain (`factory.py`) **prefers USearch when installed**: `USEARCH → SQLITE_VEC → HNSW`
- When `VectorBackend.USEARCH` is explicitly set but `usearch` is not installed, the factory logs a warning and falls back to `AUTO`

## Consequences

### Positive

- **Zero breakage** — All existing installations continue working unchanged
- **Automatic benefit** — Users who `pip install usearch` get it automatically via the `AUTO` detection chain
- **Clear path** — Documentation recommends `pip install cutctx-ai[memory]` for memory users, which includes USearch
- **No Rust compilation** — USearch ships pre-compiled wheels for all platforms (Linux, macOS, Windows); `pip install usearch` is instant
- **Backward compatible** — The `VectorBackend` enum and `create_vector_backend()` factory already supported the plugin pattern; adding `USEARCH` was additive

### Negative

- **Discovery** — Users may not know USearch exists unless they read the docs or hit the "no vector backend available" error
- **Split attention** — Four backends (`AUTO`, `USEARCH`, `SQLITE_VEC`, `HNSW`) means more choices, more testing matrix
- **`[all]` omission** — `usearch` is intentionally excluded from `[all]`, meaning the "install everything" command does not include the fastest backend. This was a deliberate choice to keep `[all]` lightweight (avoid pulling `numpy` for compression-only users), but it may confuse users who expect `[all]` to be truly comprehensive

### Mitigations

- The fallback error message in `factory.py` explicitly recommends `pip install usearch` as the first option
- `[memory]` extra includes USearch, and the memory documentation recommends `[memory]` over manual `usearch` install
- Log messages at startup inform which backend was selected by `AUTO`

## Related

- [ADR-001: USearch in Python vs Rust](../plans/2026-06-30-usearch-stack-graphs-integration-plan.md#adr-1-usearch-in-python-vs-rust)
- [ADR-002: Stack Graphs in Rust vs Python](../plans/2026-06-30-usearch-stack-graphs-integration-plan.md#adr-2-stack-graphs-in-rust-vs-python)
- [USearch Backend Documentation](../usearch.md)
