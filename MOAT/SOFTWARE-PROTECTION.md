# Headroom — Software Protection & Anti-Tamper Implementation Plan

**Preventing reverse engineering and unauthorized use of the commercial product.**

**Date:** 2026-06-16
**Status:** Ready for implementation
**Audience:** hand to coding agents. Each layer is a workstream of PRs with files, work, acceptance, and **verification** (see §11 for the consolidated red-team checklist).

---

## 0. Read this first — the honest threat model

**You cannot make client-side software un-reverse-engineerable.** Anything shipped to a customer's machine — Python, a Rust `.so`, a binary — can, with enough effort, be inspected, patched, and bypassed. Treat that as a fact, not a challenge. The realistic goals are:

1. **Ship less.** The single most effective control is architectural: keep the crown jewels (agent-tuned models, the insight corpus, the highest-value heuristics, license *truth*) **server-side**, where they're never delivered to the attacker. Code you don't ship can't be stolen.
2. **Raise the cost.** For what must ship, make reverse engineering and tampering expensive and slow (compiled, stripped, obfuscated, integrity-checked, anti-debug).
3. **Make abuse detectable + attributable.** Watermark each licensed build, phone home, and detect shared keys / tampered installs server-side — so unauthorized use is *caught* and *traceable to a customer*.
4. **Make it legally actionable.** The commercial license (anti-reverse-engineering + anti-circumvention clauses) + DMCA §1201 + detection evidence is the durable deterrent. Technical measures buy time; the legal layer is the backstop.

**Design rule for every PR below:** the enforcement point is the **compiled Rust proxy** and the **server**, never shippable Python. Never degrade the local-first promise or add request-path latency.

---

## 1. Current state (grounded — verified 2026-06-16)

- **Rust proxy** (`crates/headroom-proxy`): release profile already `strip = "symbols"`, `lto = "thin"`, `codegen-units = 1` ✅. Good baseline; not yet anti-debugged or integrity-checked.
- **Licensing:** `crates/headroom-proxy/src/license/{mod.rs,client.rs}` — Ed25519 `hrk1` token verify (embedded `prod-1` pubkey, `exp` enforced), activation + CRL (`activate_and_fetch_crl`), `instance_id` binding at activation. `headroom_ee/billing/license_db.py` has `activations/revocations/seat_leases/trials`. **Weakness:** CRL **fails open** on fetch error (a revoked key survives an outage).
- **`headroom_ee` (the proprietary package):** **pure Python**, shipped to customers via `packaging/headroom-ee` → **this is your most exposed asset.** No compilation, no obfuscation today.
- **No hardware fingerprint enforcement, no integrity self-check, no anti-debug, no per-customer watermark** yet.
- **Have:** `headroom/security/state_crypto.py` (machine-derived Fernet), `headroom/security/firewall.py`, SBOM (`cyclonedx-bom` in `publish.yml`), the leak guard (`scripts/assert_oss_wheel_clean.py`), `headroom_ee` SPDX CI gate.

---

## 2. Dependency / sequencing graph

```
SP-0 crown-jewels-server-side (design; do continuously)
SP-1 license enforcement hardening ──> SP-4 integrity/tamper detection ──> SP-5 watermarking
SP-2 Rust binary hardening ───────────┘                                   │
SP-3 compile/obfuscate shipped Python ────────────────────────────────────┤
SP-6 server-side abuse detection (needs activation/CRL telemetry) ─────────┤
SP-7 build/supply-chain signing + secrets ─────────────────────────────────┘
SP-8 legal/operational backstop (parallel, non-code)
```
Order of value: **SP-0 ≫ SP-1 ≈ SP-6 > SP-3 > SP-2/SP-4/SP-5 > SP-7 > SP-8(parallel)**. Do SP-0 thinking first; it changes what the others even need to protect.

---

## SP-0 — Keep the crown jewels server-side (architecture)

**The highest-leverage control.** Decide, per asset, "ship vs. serve." Default the valuable ones to **serve**.

| Asset | Decision | Where |
|---|---|---|
| Agent-tuned models (`kompress-agent-*`), insight corpus | **Serve** | `headroom_ee/insight` + a model-inference endpoint; never ship weights to customers (the base `kompress-v2-base` stays open, per `01`). |
| License *truth* (validity, seats, revocation) | **Serve** | already server-side (activation/CRL); client only caches a signed lease. |
| Highest-value compression heuristics / routing | **Prefer Rust** (compiled) over Python; or serve for the most novel parts. | `crates/headroom-core` |
| Spend/policy/audit logic | **Serve** | already in the control plane. |
| Commodity client (proxy, SDK, base compressors) | **Ship (open)** | Apache — drives adoption. |

**Acceptance:** a written "ship vs serve" register in `docs/protection/asset-register.md`; the agent-tuned model is reachable only via an authenticated endpoint (weights never in any shipped artifact). **Verify:** unzip every shipped artifact (wheel, EE wheel, docker image) → no model weights, no corpus, no server-only secrets present (grep + file-type scan).

---

## SP-1 — Harden license enforcement (build on `hrk1`)

**Branch:** `sp1-license-hardening`  ·  **Files:** `crates/headroom-proxy/src/license/{mod,client}.rs`, `config.rs`; `headroom_ee/billing/license_db.py`; `headroom/proxy/routes/license*.py`.

Work:
1. **CRL fail-closed after grace.** Today `activate_and_fetch_crl` fails open. Change to: cached CRL + a **grace window** (e.g. 72h) of last-known-good; after grace with no successful refresh → **downgrade to `OpenSource`** (commercial features off). Keep core compression working (don't brick the proxy).
2. **Instance/hardware binding.** On activation, bind the license to a stable **install fingerprint** = hash(machine-id + OS + a salted install UUID). Server stores it (`activations`). On startup and heartbeat, the client sends the fingerprint; server rejects if it doesn't match the activation (or exceeds the seat's allowed device count). Add `fingerprint` to the signed lease so the proxy can self-check offline too.
3. **Periodic signed heartbeat lease.** Short-lived (e.g. 24h) signed entitlement lease, refreshed via heartbeat (reuse seat-lease infra). Expired lease + past grace → downgrade. Persist the lease encrypted via `state_crypto.py`.
4. **Clock-rollback detection.** Store last-seen monotonic + wall timestamps in encrypted state; if wall clock jumps backward materially vs last-seen (to defeat `exp`), reject and force re-activation.
5. **Revocation kill-switch.** Server can revoke a `lic_id` (CRL epoch bump); proxy honors within grace.

**Acceptance/Verify:** see §11 (V-1..V-4).

---

## SP-2 — Rust binary hardening

**Branch:** `sp2-binary-hardening`  ·  **Files:** `Cargo.toml`, `crates/headroom-proxy/src/{main.rs,license/mod.rs}`, build scripts.

Work:
1. **Confirm + extend release hardening:** keep `strip = "symbols"`; add `panic = "abort"`? (NO — they deliberately don't, to avoid killing the proxy; respect that). Ensure debug symbols/`.pdb` are never shipped; `debug-assertions = false` in release.
2. **Anti-debug / anti-trace (defense-in-depth, low-cost):** at startup detect a debugger (`ptrace(PTRACE_TRACEME)` self-attach on Linux, `IsDebuggerPresent`/`ptrace` equivalents on macOS/Windows) and, if commercial-licensed, log an audit event + degrade gracefully (don't hard-crash — avoids false positives in legit profiling; make it advisory + telemetry).
3. **String/symbol hygiene:** move sensitive constants (the embedded pubkey is fine to ship; but error strings that map the license logic) behind obfuscated/`include_bytes!`-style blobs; avoid descriptive panic messages near the license path.
4. **Inline + dedupe the license check** so there isn't a single trivially-patchable branch; add a redundant verification path (verify in two places that must agree).

**Acceptance/Verify:** §11 (V-5, V-6).

---

## SP-3 — Compile / harden the shipped Python (`headroom_ee`)

**Branch:** `sp3-compile-ee`  ·  **Files:** `packaging/headroom-ee/*`, build pipeline.

Pure-Python ships readable source — the weakest link. Options, best-first:
1. **Move the most valuable logic into the Rust crate** (compiled, stripped). Preferred for anything truly novel.
2. **Compile `headroom_ee` to native extensions** with **Cython** (annotate `.py`→`.pyx`→`.so`) or **Nuitka** (`--module`/standalone). Ship **only `.so`**, drop `.py`/`.pyc` from the wheel; strip docstrings. This defeats casual `unzip`+read and decompilers (no bytecode to decompile).
3. **At minimum**, ship bytecode-only with stripped docstrings (`python -OO`) — *weak*, treat as a stopgap only.

Build: add a `compile` step in `packaging/headroom-ee` that produces a `.so`-only wheel; keep a pure-Python dev path for the monorepo (the symlinked source stays for dev; the *released* EE wheel is compiled).

**Acceptance/Verify:** §11 (V-7).

---

## SP-4 — Install integrity & tamper detection

**Branch:** `sp4-integrity`  ·  **Files:** `crates/headroom-proxy/src/license/mod.rs` (or new `integrity.rs`), a signed manifest, startup hook.

Work:
1. **Signed artifact manifest:** at build, generate a manifest of sha256 hashes of shipped commercial artifacts (proxy binary, EE `.so`s, model files), Ed25519-signed by the build key (reuse the `prod-1` signing infra).
2. **Startup self-verification:** the proxy verifies its own binary hash + the EE artifacts against the signed manifest. On mismatch (patched binary / swapped license module) → **disable commercial features + emit a tamper audit event** (don't necessarily crash; degrade + report).
3. **Detect a patched license check:** the redundant verification (SP-2.4) + manifest check makes "flip the boolean" patches fail-closed.

**Acceptance/Verify:** §11 (V-8, V-9).

---

## SP-5 — Per-customer watermarking + leak tracing

**Branch:** `sp5-watermark`  ·  **Files:** build pipeline, `headroom_ee/insight` (model serving), `headroom_ee/audit`.

Work:
1. **Per-license build watermark:** stamp a per-`lic_id` watermark into the released EE artifact (e.g., a signed constant / benign perturbation) so a leaked copy maps to the customer who received it.
2. **Canary tokens:** embed unique inert markers (fake "internal" strings/URLs) per license; if they show up in the wild (public repos, paste sites, your canary callback), you know who leaked.
3. **Model watermark (when SP-0 serves models):** if any agent-tuned model is ever delivered, watermark weights per customer (e.g., a fingerprinting fine-tune) so leaked weights are attributable.
4. **Server correlation:** record which watermark/canary maps to which `lic_id` in the license DB.

**Acceptance/Verify:** §11 (V-10).

---

## SP-6 — Server-side abuse detection (privacy-respecting)

**Branch:** `sp6-abuse-detection`  ·  **Files:** `headroom_ee/billing/license_db.py`, a new `headroom_ee/abuse/` analyzer, `headroom/proxy/routes/license*.py`, alerts.

Work (all server-side, on activation/heartbeat metadata only — never prompt content):
1. **Shared-key detection:** too many distinct fingerprints/IPs per seat, or **impossible travel** (same key, distant geos within minutes) → flag.
2. **Seat overuse / activation storms** → flag + optional auto-throttle.
3. **Revoke + alert workflow:** flagged licenses raise an alert; admin can revoke (CRL). Every action audited (Phase-2 chain).

**Acceptance/Verify:** §11 (V-11).

---

## SP-7 — Build, supply-chain & secrets hygiene

**Branch:** `sp7-supply-chain`  ·  **Files:** `.github/workflows/*`, `packaging/*`, KMS config.

Work:
1. **Code-sign** released binaries/wheels (macOS notarization, Windows Authenticode, Linux/PyPI Sigstore) so customers can verify authenticity and tampered redistributions are detectable.
2. **No debug/symbol leakage:** CI asserts released artifacts are stripped and contain no `.py` source for EE, no `.pdb`/dSYM, no source maps.
3. **Signing keys in KMS/HSM**, never in repo (extend the existing private-key discipline). CI secret-scan (already partly present) blocks key material.
4. **SBOM** per release (already have `cyclonedx-bom`); reproducible builds where feasible.

**Acceptance/Verify:** §11 (V-12).

---

## SP-8 — Legal & operational backstop (parallel, non-code)

- **Commercial license:** `LICENSE-COMMERCIAL` already prohibits reverse engineering, circumventing license/seat/trial/telemetry controls, and competing use (§4 c/e/f). Have counsel confirm anti-circumvention + DMCA §1201 language and add a clause acknowledging integrity/watermarking measures.
- **Customer agreement:** audit-right + no-circumvention clauses; license terminates on tamper.
- **Operational:** a takedown/DMCA playbook; a leak-response runbook (watermark → identify → notify/terminate); incident logging.

---

## 11. Verification steps (red-team checklist)

> Run these to **prove** each control works. Each is "attacker action → expected defense → how to confirm." Wire the automatable ones into CI; do the manual ones each release. A control without a passing verification is not done.

**V-1 Expired/forged token (SP-1).** Present a token with past `exp`, a tampered claim, and an unknown `kid`. *Expect:* each → `OpenSource`. *Confirm:* `cargo test -p headroom-proxy` cases assert rejection (already partly exist; extend for `exp`).

**V-2 Revocation + CRL fail-closed (SP-1).** Revoke a `lic_id`; refresh CRL → denied. Then block the CRL endpoint and advance the clock past the grace window → commercial features **off** (not still-on). *Confirm:* integration test with a stubbed CRL endpoint + fake clock; assert downgrade after grace.

**V-3 Instance binding (SP-1).** Activate on machine A; copy the entire install (+ encrypted state) to machine B and run. *Expect:* B's fingerprint ≠ activation → rejected / seat conflict. *Confirm:* test with two distinct fingerprints against one single-seat license → second is denied.

**V-4 Clock rollback (SP-1).** Set the system clock backward to un-expire a lease. *Expect:* rollback detected → re-activation forced. *Confirm:* test injecting a backward wall-clock vs stored last-seen.

**V-5 Symbol/string strip (SP-2).** Run `nm -D`, `strings`, and `objdump -T` on the released proxy binary and EE `.so`. *Expect:* no internal symbol names, no descriptive license-logic strings, no source paths. *Confirm:* a CI script greps the artifact for forbidden tokens (function names, `license`, file paths) → must be empty.

**V-6 Anti-debug (SP-2).** Attach `gdb`/`lldb` to the running proxy. *Expect:* audit event emitted (advisory degrade), not a silent bypass. *Confirm:* manual attach + check audit log.

**V-7 Python decompilation (SP-3).** On the **released** EE wheel: `unzip -l` → assert **no `.py`** and no `.pyc`; attempt `uncompyle6`/`decompyle3` on anything present → must fail (it's a native `.so`, not bytecode). Try `import headroom_ee; inspect.getsource(...)` → must fail/return no source. *Confirm:* CI script on the built EE wheel.

**V-8 Patch-the-check (SP-4).** Take the shipped binary, patch the license verify to always-return-Enterprise (or swap the EE license module). *Expect:* startup integrity check detects the hash mismatch → commercial features disabled + tamper audit event. *Confirm:* manual patch of a copy → run → assert downgrade + audit entry.

**V-9 Manifest signature (SP-4).** Tamper with one byte of a shipped artifact and re-run. *Expect:* manifest verification fails → fail-closed. *Confirm:* automated test that flips a byte and asserts detection.

**V-10 Watermark trace (SP-5).** Take two EE builds issued to different `lic_id`s; extract the watermark/canary from each. *Expect:* each maps to the correct `lic_id` in the license DB. *Confirm:* a `scripts/extract_watermark.py` that recovers the id from a build; plant a canary and verify the callback identifies the license.

**V-11 Shared-key abuse (SP-6).** Replay activations/heartbeats for one key from 10 fingerprints across distant geos within minutes. *Expect:* flagged (impossible travel / fingerprint count) → alert; auto-revoke if configured. *Confirm:* feed synthetic events to the abuse analyzer; assert the flag + CRL revoke.

**V-12 Supply-chain (SP-7).** Verify the released binary's code signature; confirm the EE wheel has no source/symbols; run the secret-scan. *Expect:* signature valid; no `.py`/symbols/keys. *Confirm:* CI gates (`assert_oss_wheel_clean.py` extended with an EE-artifact variant + a signature check).

**V-13 Boundary (existing).** `python3 scripts/assert_oss_wheel_clean.py dist` → no `headroom_ee` in the OSS wheel (already enforced in CI).

---

## 12. Honest limitations & what NOT to waste time on

- **No client-side control is unbreakable.** A determined, skilled attacker with the binary will eventually bypass SP-1..SP-4. These raise cost and buy detection time; they don't make it impossible.
- **The durable deterrents are SP-0 (don't ship it), SP-5/SP-6 (detect + attribute), and SP-8 (legal).** Invest there first.
- **Don't:** pour weeks into exotic Python obfuscation/packers (low ROI, breaks easily, hurts debuggability), add DRM that phones home on every request (latency + privacy = the thing you're selling against), or build anti-debug that hard-crashes on legitimate profiling. Keep enforcement out of the hot path and never break the local-first promise.
- **Don't fingerprint users invasively** — the install fingerprint is for license binding only; keep it minimal and disclosed (consistent with the local-first brand and the opt-in telemetry posture).

## 13. Definition of done

- Crown-jewel assets are served, not shipped (SP-0 register; verified absent from artifacts).
- License enforcement is fail-closed-after-grace, instance-bound, heartbeat-leased, clock-tamper-aware (V-1..V-4).
- Released proxy is stripped + anti-debugged + integrity-checked; EE ships compiled (no source) (V-5..V-9).
- Each licensed build is watermarked and traceable; server detects shared-key abuse (V-10, V-11).
- Releases are signed, source/secret-free, SBOM'd (V-12, V-13).
- Commercial license + DMCA + leak-response runbook in place (SP-8).
- Every control above has a **passing verification** from §11 (automatable ones in CI).
