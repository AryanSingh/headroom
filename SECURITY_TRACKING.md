# Security & Advisory Tracking

## Open

### pyo3 CVE upgrade (RUSTSEC-2026-0176, RUSTSEC-2026-0177)
**Priority:** HIGH — schedule before first enterprise sale  
**Effort:** Medium (API migration required across PyO3 bindings)

| | |
|---|---|
| Current | `pyo3 = { version = "0.24", features = ["abi3-py310"] }` |
| Target | `>= 0.29` |

**CVEs:**
- RUSTSEC-2026-0176: OOB read in PyList/PyTuple iterators (requires malicious Python object)
- RUSTSEC-2026-0177: Missing Sync bound on closures (requires non-Sync closure across threads)

**Practical risk:** LOW in headroom's usage (PyO3 bindings only receive trusted input from `compress()`, `SmartCrusher`, `DiffCompressor`). However, security review questionnaires from enterprise buyers will flag these.

**Migration notes:**
- pyo3 0.25–0.29 has breaking changes in `Python<'_>` lifetime handling and `#[pyo3(from_py_with)]`
- Do **not** bump the version number alone — run `cargo test` and `pytest e2e/` after the upgrade
- Dedicate a single PR; scope it to the version bump + any API callsite fixes only

---

## Closed

| Date | Severity | Issue | Fix |
|---|---|---|---|
| 2026-06-14 | 🔴 CRITICAL | License key validation was prefix-only — any string got Team tier | HMAC-SHA256 verification via `HEADROOM_LICENSE_HMAC_SECRET` env var (Rust `from_license_key_hmac`) |
| 2026-06-14 | 🔴 CRITICAL | Trial state stored as plaintext JSON — trivially tamperable | Fernet machine-derived encryption via `headroom.security.state_crypto` |
| 2026-06-14 | 🔴 CRITICAL | Seat state stored as plaintext JSON — trivially tamperable | Same `state_crypto` module |
| 2026-06-14 | 🟡 HIGH | Entitlements fail-open for unknown features — undeclared features allowed | `is_entitled` now returns `False` + warning for features not in `FEATURE_TIERS` |
| 2026-06-15 | 🟡 HIGH | `require_entitled` crash bug — `FEATURE_TIERS[feature]` raised `KeyError` for unknown features instead of `EntitlementError` | `.get(feature, EntitlementTier.ENTERPRISE)` fallback in `headroom/entitlements.py` |
| 2026-06-15 | 🟢 MEDIUM | `lru` 0.12.5 IterMut unsoundness (RUSTSEC advisory) | Upgraded to `lru = "0.13"` in `crates/headroom-proxy/Cargo.toml` |
| 2026-06-15 | 🟢 MEDIUM | `read_encrypted_json` plain JSON fallback silently accepted tampered/replaced files | Added `HEADROOM_STRICT_STATE=1` env var to reject unencrypted files in production (`headroom/security/state_crypto.py`) |
