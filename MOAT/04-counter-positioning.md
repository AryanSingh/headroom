# Workstream D — Counter-Positioning vs. the Providers

**Moat type:** Counter-positioning (durable because it's rooted in the incumbents' incentives, not our cleverness).
**Thesis:** Our single biggest threat is provider-native optimization — Anthropic prompt caching, OpenAI prefix caching, Google/Bedrock equivalents — which is free, improving, and zero-config. We cannot win a raw "token saver" fight against features the providers bundle for free. But the providers will **structurally never** build a great *cross-provider, spend-reducing, provider-independent* tool, because it helps customers spend less with them and switch away — it cannibalizes their core revenue and their lock-in. That asymmetry is the durable position. This workstream is mostly **roadmap priority and positioning**, not new moats — it hardens A/B/C by making Headroom the thing providers can't follow.

**What already exists (build on):**
- `headroom/providers/` + `crates/headroom-proxy/src/{bedrock/*,compression/provider_native.rs,cache_stabilization/*}` — multi-provider proxy, provider-native cache awareness.
- `headroom/security/{firewall.py,firewall_ml.py}` — egress controls (seed of a verifiable no-egress guarantee).
- `headroom/{cost_forecast.py,pricing/}` — cost model (seed of cross-provider arbitrage).

**The principle for prioritization:** when choosing what to build, prefer features a rational provider would refuse to ship. Those are defensible. Features the provider will eventually bundle (better single-provider caching) are a treadmill — match them only enough to not lose, and don't lead with them.

---

## D1 — Cross-provider quality-bounded spend router

**Branch:** `moat-D1-spend-router`
**Risk:** MEDIUM
**Why providers won't follow:** routing to the cheapest provider/model that clears a quality bar is the opposite of provider lock-in.

### Scope
Route each request to the lowest-cost provider/model that meets a configurable quality bar, using the eval harness as the bar and the spend ledger (`03`/C4) as the cost input. Honor policy allowlists (`03`/C5).

### Files
**Add:** `crates/headroom-proxy/src/routing/spend_router.rs` (decision at dispatch in `proxy.rs`), `headroom/routing/quality_bar.py` (offline calibration via `headroom/evals/`).
**Modify:** `crates/headroom-proxy/src/proxy.rs`, `headroom/providers/`.

### Acceptance criteria
- For a calibrated task class, the router selects the cheapest model clearing the quality bar (test on a labeled set).
- Routing respects policy allowlists and is deterministic per config.
- A/B shows cost reduction at equal-or-better measured quality.

---

## D2 — Verifiable local-first / no-egress proof

**Branch:** `moat-D2-no-egress-proof`
**Risk:** MEDIUM
**Why providers won't follow:** a provider cannot credibly promise your prompts never reach them — that's their business.

### Scope
Turn "your data stays local" from a claim into a **verifiable artifact**: an egress firewall that enforces no-prompt-egress by default and emits a signed, hash-chained "data residency proof" (ties to audit chain `03`/C6) attesting that, in a period, no prompt content left the boundary except to the explicitly configured model provider(s).

### Files
**Modify:** `headroom/security/firewall.py` (enforce + record egress decisions), tie into `headroom/audit.py` chain.
**Add:** `headroom/security/residency_proof.py` (signed periodic attestation), `docs/data-residency.md`, tests.

### Acceptance criteria
- With egress firewall on, any attempt to send prompt content anywhere except configured providers is blocked + audited (test with a rogue sink).
- Residency proof verifies and is exportable for security review.

---

## D3 — Cross-provider failover & portability

**Branch:** `moat-D3-provider-portability`
**Risk:** MEDIUM
**Why providers won't follow:** seamless switching away is the antithesis of lock-in.

### Scope
One config, swap or fail over between providers; translate request/response formats (Anthropic ↔ OpenAI ↔ Bedrock/Vertex) so an outage or price change at one provider degrades gracefully to another. Builds on existing `sse/` adapters and `bedrock/` envelope code.

### Files
**Modify:** `crates/headroom-proxy/src/sse/*`, `crates/headroom-proxy/src/bedrock/*`, `headroom/providers/`.
**Add:** `crates/headroom-proxy/src/routing/failover.rs`, tests.

### Acceptance criteria
- A simulated provider outage fails over to a configured backup with format translation (integration test).
- Round-trip format translation preserves tool calls and streaming semantics (parity test, reuse `headroom-parity`).

---

## D4 — Positioning & proof (non-code)

Not an engineering PR — the messaging that makes the above legible. Owner: founders/marketing.

- **Lead with** cross-provider control + reversible fidelity + local-first governance. **Token savings is the proof point, not the headline** (already the stance in `artifacts/value-proposition.md` — hold it).
- **Publish reproducible head-to-head benchmarks** vs LLMLingua-2 / Morph Compact / lean-ctx (closes the credibility gap flagged in `PRODUCT_ANALYSIS.md` §4.8) — and explicitly **vs provider-native caching across providers**, which providers can't match by definition.
- **Frame against providers explicitly:** "Native caching helps inside one provider. Headroom works across providers, reduces what you spend with them, keeps your data out of their hands, and lets you leave."

---

## Definition of done (Workstream D)
- Spend router demonstrably cuts cost at equal/better measured quality.
- A verifiable no-egress proof exists and survives security review.
- Provider failover works with format translation.
- Public, reproducible benchmarks (incl. cross-provider vs native caching) are live.
- **Guiding test for every roadmap item:** "Would a rational provider refuse to build this because it loses them money or lock-in?" If yes, it's defensible — prioritize it. If no, it's a treadmill — match, don't lead.
