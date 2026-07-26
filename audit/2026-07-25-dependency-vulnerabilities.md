# Dependency vulnerability audit — first local run of pip-audit and cargo-audit

**Date:** 2026-07-25
**Status:** **partially resolved.** The five request-path packages were upgraded
the same day, cutting **37 advisories to 9** and clearing every finding on
network-facing code. `pyo3` and seven lower-risk Python packages remain. See
"Resolved" below.
**Why now:** prior audits listed both tools as "BLOCKED — not installed", so
Python and Rust dependency exposure had never been measured locally. Both are
now installed and were run against the current lockfiles.

> Counts below were produced and re-verified directly, not summarised from a
> delegated report. `cargo audit` output was re-run independently; `pip-audit`
> figures come from its JSON output.

---

## Resolved (2026-07-26)

| Package | Was | Now | Advisories cleared |
|---|---|---|---:|
| `pyjwt` | 2.11.0 | 2.13.0 | 11 |
| `aiohttp` | 3.14.0 | 3.14.3 | 8 |
| `starlette` | 1.0.1 | 1.3.1 | 5 |
| `python-multipart` | 0.0.27 | 0.0.32 | 3 |
| `cryptography` | 46.0.7 | 49.0.0 | 1 |

**28 of 37 advisories cleared; 12 vulnerable packages down to 7.**

Four of those five were **transitive** (via fastapi/litellm) and therefore not
declared anywhere, which means the upgrade would have existed only in one
developer's virtualenv and a fresh resolve could have pulled the vulnerable
versions straight back in. Explicit security floors were added to
`pyproject.toml` so the fix is durable:

```toml
"starlette>=1.1.0",           # ASGI framework under the proxy
"python-multipart>=0.0.30",   # multipart request-body parsing
"aiohttp>=3.14.1",            # outbound HTTP
"pyjwt>=2.12.0",              # JWT verification for enterprise SSO
```

Verified after upgrading: `pytest tests/` 9,120 passed / 469 skipped, and
`pytest cutctx_ee/tests/` 53 passed, both exit 0. `ruff check` and
`ruff format --check` clean. One new advisory-free deprecation surfaced —
`starlette.testclient` with `httpx` now warns to use `httpx2`; functional, but
worth a follow-up.

### Second pass (2026-07-26) — Rust clean, Python down to 3

**Rust: `cargo audit` now reports zero vulnerabilities.** `pyo3` was upgraded
**0.24.1 → 0.29.0**, closing RUSTSEC-2026-0176 (out-of-bounds read in
`PyList`/`PyTuple` iterators) and RUSTSEC-2026-0177 (missing `Sync` bound on
`PyCFunction::new_closure`). This spanned five minor versions of breaking API
change; the migration was mechanical but not trivial:

- `py.allow_threads(…)` → `py.detach(…)` (12 sites)
- `Python::with_gil(…)` → `Python::attach(…)` (3 sites)
- explicit `from_py_object` / `skip_from_py_object` on 15 `#[pyclass]`
  declarations, since 0.29 stops deriving `FromPyObject` automatically

Verified independently after rebuilding the extension: `cargo test --workspace`
**1,495 passed / 0 failed**, no new clippy warnings, and the compression path
works through the rebuilt `cutctx._core`. The 4 unmaintained/yanked warnings
(`fxhash`, `paste`, `number_prefix`, `num-bigint`) remain — none is a
vulnerability.

**Python: 9 → 3 advisories.** Upgraded `click` 8.3.1→8.4.2,
`pygments` 2.19.2→2.20.0, `pydantic-settings` 2.12.0→2.14.2,
`mcp` 1.26.0→1.28.1.

### Still outstanding (3 advisories)

| Package | Version | Fix | Why not done |
|---|---|---|---|
| `langsmith` | 0.8.0 | 0.8.18 | **Blocked by a dependency conflict** — see below |
| `sqlitedict` | 2.1.0 | none | No patched release exists. Decide between removing it and accepting the risk. |
| `torch` | 2.11.0 | 2.13.0 | Optional ML extra only (`[ml]`/`[voice]`/`[all]`), multi-GB upgrade. Already conflicts with the installed setuptools (`torch 2.11.0 requires setuptools<82`, environment has 83.0.0). Worth its own pass. |

**The `langsmith` conflict is a real finding.** Its fix version requires
`websockets>=15.0`, but this project pins `websockets>=13.0,<14.0` for the
Codex WebSocket proxy (`/v1/responses`). Installing the fix silently pulled
`websockets` to 16.1.1 and broke that constraint, so it was reverted. Fixing
this advisory therefore requires first deciding whether the WebSocket proxy can
move to `websockets` 15/16. Since `langsmith` is inert unless Langfuse env vars
are explicitly set, leaving it is the lower risk of the two — but the
constraint conflict should be resolved deliberately rather than forgotten.

## Headline (as first measured, before the upgrades)

| Tool | Command | Exit | Result |
|---|---|---|---|
| pip-audit | `.venv/bin/pip-audit` | 1 | **12 packages, 37 advisories** |
| cargo-audit | `cargo audit` | 1 | **2 vulnerabilities, 4 warnings** (604 dependencies scanned) |

`pip-audit --strict` (what CI runs at `.github/workflows/ci.yml:365`) could not
complete locally because the editable `cutctx-ai` package is not resolvable on
PyPI — it is skipped with "Dependency not found on PyPI and could not be
audited". Worth knowing: **`--strict` may be passing in CI for the same reason,
without auditing the local package.**

**Every finding except `sqlitedict` has a fix version available.** Most are
single-version bumps.

## Python — 12 packages, 37 advisories

| Package | Installed | Advisories | First fix |
|---|---|---:|---|
| `pyjwt` | 2.11.0 | **11** | 2.12.0 |
| `aiohttp` | 3.14.0 | **8** | 3.14.1 |
| `starlette` | 1.0.1 | **5** | 1.1.0 |
| `mcp` | 1.26.0 | 3 | 1.27.2 |
| `python-multipart` | 0.0.27 | 3 | 0.0.30 |
| `click` | 8.3.1 | 1 | 8.3.3 |
| `cryptography` | 46.0.7 | 1 | 48.0.1 |
| `langsmith` | 0.8.0 | 1 | 0.8.18 |
| `pydantic-settings` | 2.12.0 | 1 | 2.14.2 |
| `pygments` | 2.19.2 | 1 | 2.20.0 |
| `torch` | 2.11.0 | 1 | 2.13.0 |
| `sqlitedict` | 2.1.0 | 1 | **none available** |

### Reachability assessment

Treat this section as a starting point for triage, not a verdict — it is
inference from where each package is used, not exploit validation.

**On the request path — prioritise these.** `starlette` is the ASGI framework
under the proxy, `python-multipart` parses multipart request bodies, `aiohttp`
is used for outbound HTTP, and `pyjwt` backs enterprise SSO token verification.
These four account for 27 of the 37 advisories and all sit directly in
network-facing code.

**Security primitives.** `cryptography` provides the Fernet encryption and HMAC
used for licence-cache integrity (`cutctx/security/state_crypto.py`).

**Narrower exposure.** `click` is the CLI framework; `mcp` serves the MCP
integration; `torch` ships only in the `[ml]`/`[voice]`/`[all]` extras;
`pygments` only colourises CLI output; `langsmith` requires explicit
opt-in env vars.

**No fix path.** `sqlitedict` 2.1.0 is end-of-life with no patched release.
Check whether it is still imported anywhere; if not, drop it.

## Rust — 2 vulnerabilities, 4 warnings

Independently re-verified:

| Crate | Version | ID | Title | Fix |
|---|---|---|---|---|
| `pyo3` | 0.24.2 | RUSTSEC-2026-0176 | Out-of-bounds read in `nth`/`nth_back` for `PyList` and `PyTuple` iterators | ≥0.29.0 |
| `pyo3` | 0.24.2 | RUSTSEC-2026-0177 | Missing `Sync` bound on `PyCFunction::new_closure` closures | ≥0.29.0 |

**`pyo3` is the highest-priority item in this report.** It is the Python↔Rust
bridge for the `cutctx._core` extension module, so it is loaded by every user of
the product, and an out-of-bounds read is a memory-safety issue rather than a
logic bug. The upgrade from 0.24 to 0.29 spans five minor versions and will need
real work — pyo3 makes breaking API changes between minors — so scope it
deliberately rather than treating it as a version bump.

Warnings (unmaintained or yanked, not vulnerabilities):

| Crate | ID | Note |
|---|---|---|
| `fxhash` 0.2.1 | RUSTSEC-2025-0057 | Unmaintained; transitive via `dashmap`. Non-cryptographic hash — low risk, no patch path. |
| `paste` 1.0.15 | RUSTSEC-2024-0436 | Unmaintained; compile-time macro only. |
| `number_prefix` 0.4.0 | RUSTSEC-2025-0119 | Unmaintained; transitive via `indicatif` progress bars. |
| `num-bigint` 0.4.7 | — | **Yanked** by its maintainer. Worth finding out why. |

## Recommended sequence

1. **Bump the request-path Python packages** — `starlette`, `python-multipart`,
   `aiohttp`, `pyjwt`. 27 of 37 advisories, all with fixes, all on network-facing
   code. Run the full suite after; `starlette` 1.0→1.1 may need attention.
2. **Bump `cryptography`** to 48.0.1 and re-verify the licence-cache HMAC path.
3. **Scope the `pyo3` 0.24→0.29 upgrade** as its own piece of work. Memory
   safety in the extension every user loads justifies it, but it is not a
   one-liner.
4. **Sweep the low-risk remainder** — `click`, `mcp`, `pygments`,
   `pydantic-settings`, `torch`, `langsmith`.
5. **Decide on `sqlitedict`** — no fix exists, so either remove it or accept and
   document the risk.
6. **Fix the CI gap.** Make `pip-audit --strict` fail loudly if it cannot audit
   the local package, or exclude it explicitly, so the gate is not silently
   weaker than it looks.

---

*Read-only assessment. No dependency, `pyproject.toml`, `Cargo.toml`, or lock
file was modified. Installing the two audit tools was the only change.*
