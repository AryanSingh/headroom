# Distribution Protection

## Architecture

CutCtx uses a Rust core (`crates/headroom-core`) compiled to a native extension via
[PyO3](https://pyo3.rs/) and [maturin](https://www.maturin.rs/). All five compression
algorithms are implemented entirely in Rust:

| Algorithm | Rust crate | Python wrapper |
|---|---|---|
| SmartCrusher | `crates/headroom-core` | `headroom/transforms/smart_crusher.py` |
| DiffCompressor | `crates/headroom-core` | `headroom/transforms/diff_compressor.py` |
| LogCompressor | `crates/headroom-core` | `headroom/transforms/log_compressor.py` |
| SearchCompressor | `crates/headroom-core` | `headroom/transforms/search_compressor.py` |
| CodeAwareCompressor | `crates/headroom-core` | `headroom/transforms/code_compressor.py` |

The Python classes in `headroom/transforms/` are thin dispatch wrappers — they import
the compiled extension (`headroom._core`) and forward calls into Rust. No proprietary
algorithm logic lives in Python.

---

## What Is Protected

The compiled Rust binary (`headroom_core.so` on Linux/macOS, `headroom_core.pyd` on
Windows) is the artifact that ships:

- **No symbol names.** When built with `strip = true` (see below), the binary contains
  no function names, variable names, or type names from the source.
- **No readable string literals from algorithm logic.** Rust string literals used
  internally are embedded as raw bytes with no surrounding context; they are not
  searchable the way Python source strings are.
- **Not decompilable.** Native machine code cannot be lifted back to anything
  resembling Rust source. This is categorically different from Python `.pyc` files,
  which are trivially decompiled to near-identical source by tools such as `uncompyle6`
  or `decompile3`.

The `.py` source files for the transform modules are stripped from the distributed
wheel by `scripts/strip_wheel.py`, so there is no Python-level entry point to read.

---

## What Is Not Protected

The following modules ship as Python source under the Apache-2.0 licence and contain
no proprietary algorithm logic:

- **CLI argument parsing** — `headroom/cli/`
- **Proxy server routing** — `headroom/proxy/server.py` and related modules
- **Provider integrations** — `headroom/providers/`

These are intentionally open so that users can inspect, fork, and extend them.

---

## Building a Protected Distribution

```bash
# Full build + strip in one command
bash scripts/build_protected_wheel.sh

# Or manually:
maturin build --release
python scripts/strip_wheel.py dist/cutctx_ai-*.whl
```

The output wheel is written alongside the input with a `-stripped` suffix, e.g.
`dist/cutctx_ai-0.27.0-cp310-cp310-linux_x86_64-stripped.whl`.

Makefile shortcuts:

```bash
make build-protected   # strip source from the most recently built wheel
make dist-protected    # compile Rust + strip in one step
```

---

## Additional Hardening

**Strip debug symbols** from the Rust binary by adding the following to `Cargo.toml`:

```toml
[profile.release]
strip = true
```

This removes all DWARF debug information and symbol tables from the `.so`/`.pyd`,
reducing binary size and eliminating any residual symbol names that survive a
standard release build.

**Enable Link-Time Optimisation (LTO)** for maximum inlining and dead-code
elimination:

```toml
[profile.release]
lto = true
strip = true
```

LTO merges all crate codegen units before machine-code generation, making it
significantly harder to identify function boundaries in a disassembler.

**Commercial (`cutctx-ee`) package.** The proprietary enterprise edition
(`cutctx-ee`, see `LICENSING.md`) is distributed as pre-compiled wheels only —
no source is published. Enterprise wheels are built with both `lto = true` and
`strip = true` and are not available on PyPI.

---

## Verifying Protection

After building a stripped wheel, confirm that the algorithm source files are absent:

```bash
unzip -l cutctx_ai-*-stripped.whl | grep "transforms/"
# Should show no .py files for the algorithm modules
# __init__.py stubs are retained; .py algorithm files are not
```

To verify the Rust extension is present and importable:

```bash
pip install dist/cutctx_ai-*-stripped.whl
python -c "from headroom._core import SmartCrusher; print('ok')"
```
