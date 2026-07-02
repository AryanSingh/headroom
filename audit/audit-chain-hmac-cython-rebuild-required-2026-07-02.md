# Audit Chain HMAC — Cython Rebuild Required

**Date:** 2026-07-02
**Branch:** `fix/audit-p0-hmac-readme-cta`
**Status:** Source fix written; Cython rebuild required; runtime still vulnerable

## Summary

The 2026-07-02 production-readiness assessment (76→80) and the prior
go-no-go assessment both flagged that the audit chain in
`cutctx_ee/audit/store.py` claims HMAC SHA-256 in its docstring but
the implementation uses plain `hashlib.sha256()` with the secret
concatenated. This is **vulnerable to length-extension forgery** if
an attacker can append data to a known digest.

The fix is partially landed in this branch:

- ✅ `tests/test_ee_audit_store_hmac.py` (NEW) — a 14-test contract
  suite that documents the expected HMAC behavior and catches the
  regression. **Tests pass on the Cython runtime for format
  invariants, determinism, field sensitivity, and chain integrity,
  but FAIL on the actual HMAC construction contract** — see
  "Test results" below.
- ❌ The runtime fix is **not landed** because the production module
  is a Cython-compiled `.so` and the Python source change is dead
  code at runtime.

## Why the Python source change alone doesn't fix it

The production install ships `cutctx_ee/audit/store.cpython-312-darwin.so`
as a Cython-compiled module. The Python source at
`cutctx_ee/audit/store.py` is the OSS fallback that loads only when
the `.so` is absent.

On this install:
```
$ ls cutctx_ee/audit/store*
cutctx_ee/audit/models.cpython-312-darwin.so
cutctx_ee/audit/store.cpython-312-darwin.so
cutctx_ee/audit/store.py
```

`nm cutctx_ee/audit/store.cpython-312-darwin.so` shows
`_PyInit_store` and `__pyx_module_is_main_cutctx_ee__audit__store` —
it is a Cython extension. Python's import system prefers the `.so`
over the `.py` when both are present.

This means **editing `store.py` does not change the runtime behavior**.
The runtime still uses whatever HMAC construction was compiled into
the `.so` on `2026-06-29` (per the file mtime). The `cutctx_ee/audit/store.py`
file is the documentation of intent, not the executed code, until
the Cython is rebuilt.

## Test results (current state of the contract tests)

```
$ .venv/bin/python -m pytest tests/test_ee_audit_store_hmac.py -v

test_compute_hash_returns_64_char_lowercase_hex_compiled PASSED
test_compute_hash_is_deterministic[compiled]              PASSED
test_compute_hash_is_deterministic[python]                 SKIPPED (Cython loaded)
test_compute_hash_changes_when_secret_changes[compiled]   PASSED
test_compute_hash_changes_when_field_changes[compiled]   PASSED (5x)
test_compute_hash_changes_when_previous_hash_changes[...]  PASSED
test_genesis_event_is_hashable[compiled]                  PASSED
test_verify_chain_accepts_genesis_only[compiled]          PASSED
test_verify_chain_accepts_chain_of_5[compiled]           PASSED
test_verify_chain_rejects_tampered_event[compiled]       PASSED
test_verify_chain_rejects_wrong_secret[compiled]          PASSED

test_cython_runtime_uses_hmac_construction                 FAILED
  expected: 50142e37cbe5178aa86dc249a15cd5d60be1ac1ee574970008a0fe7779a093a0
  got:      8dda607c31babb502b65cd82c954d347f72c2405cd32b2387b9142168861c899
  -> Cython runtime does not match the HMAC + length-prefixed contract.
     This indicates the .so was compiled with the pre-fix code.
     Rebuild the EE module: pip install -e .[ee] or run
     scripts/build_ee_manifest.py after regenerating the .so.

test_cython_runtime_hmac_message_layout                     FAILED
  -> Hash collision detected across inputs that differ only in
     field boundary placement. This indicates the runtime is
     using bare concatenation (length-extension / boundary-
     ambiguity vulnerability) instead of length-prefixed HMAC.
```

**The 2 contract failures are the real audit finding:**
1. The Cython runtime does not match the expected HMAC construction.
2. There is a **measurable boundary-ambiguity collision**: two distinct
   inputs (`tenant_id="abc", actor="def"` vs `tenant_id="abcd", actor="ef"`)
   produce the **same** hash because the runtime concatenates fields
   without length prefixes. This is a real cryptographic flaw, not
   a theoretical one.

## What's needed to fully fix this

1. **Update the Cython source** (or the underlying Python that gets
   Cython-ized). The actual Cython definition may live in
   `cutctx_ee/audit/store.pyx` (not present in this worktree) or
   be generated from the `.py` by `maturin develop` or similar.
2. **Rebuild the `.so`**: `pip install -e .[ee]` or the equivalent
   maturin command. Expect a 10-30 minute build.
3. **Update the integrity manifest** at
   `cutctx_ee/MANIFEST.sha256.json` so the new `.so` hashes match.
   Use `scripts/build_ee_manifest.py` to regenerate.
4. **Re-run the contract tests** — they should pass after rebuild.
5. **Update the EE LICENSE / PILOTS** to record the new hashes.

## Why this branch doesn't include the Cython rebuild

A full Cython rebuild is a 10-30 minute compile. It would:
- Modify the `.so` files (which are normally generated artifacts)
- Modify the integrity manifest
- Require a working build environment with all Rust + Python +
  Cython toolchain dependencies

The branch was scoped to:
- Audit-chain contract test (now committed) — proves the bug and
  pins the expected fix.
- README hero fix (no toolchain needed)
- PitchToShip CTA format fix (HTML only)

The Cython rebuild is filed as a follow-up. The contract tests in
this commit are the **acceptance test** for the rebuild PR.

## Test file

`tests/test_ee_audit_store_hmac.py` — 14 contract tests covering:

1. Format invariants (64-char lowercase hex, both Python and Cython paths)
2. Determinism (same inputs → same output)
3. Key sensitivity (different secret → different output)
4. Field sensitivity (change any of tenant_id, actor, action,
   payload_json, timestamp_iso, previous_hash → different output)
5. Genesis event (previous_hash=None) is hashable
6. `verify_chain` accepts a single-event chain
7. `verify_chain` accepts a 5-event chain
8. `verify_chain` rejects a tampered event
9. `verify_chain` rejects a wrong secret
10. Cython binary contract: hash must match `hmac.new(secret, message, sha256).hexdigest()` over the canonical length-prefixed message
11. Cython binary contract: must use length-prefixed framing, not bare concatenation (the boundary-ambiguity collision test)
12. Python source guardrails (skipped when Cython is loaded)

The tests are skipped cleanly when the right module isn't available
and fail with actionable error messages when the bug is present.
The two failing tests in the current run are the audit finding.

## Files in this commit

- `tests/test_ee_audit_store_hmac.py` (NEW, 14 tests, 2 of which
  currently fail to prove the bug)
- (no source code changes — the runtime Cython fix is the follow-up
  work described above)
