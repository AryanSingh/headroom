# Competitive Gap Backlog

*Prepared from the current product docs and the competitor set you shared: Morph, LLMLingua-2, Compresr, The Token Company, and Helicone.*

## What we are actually behind on

Cutctx is already strong on local-first compression, reversible retrieval, cross-provider support, memory, and governance. The main gaps are not raw capability breadth. They are:

1. Hosted simplicity: competitors can be consumed like a pure API.
2. Gateway depth: Helicone is broader in observability, routing, and control-plane ergonomics.
3. Narrow benchmark proof: Morph and LLMLingua have very crisp, single-purpose performance stories.
4. Research credibility: LLMLingua-2 still reads like the canonical OSS baseline for prompt compression.
5. Procurement packaging: hosted vendors with ready-made compliance stories are easier to buy.

## Priority order

1. Hosted compression entrypoint
2. Gateway and observability depth
3. Benchmark and proof-point parity
4. OSS/research baseline compatibility
5. Enterprise procurement hardening

## P1. Hosted compression entrypoint

### Why this matters

Compresr, The Token Company, and Morph all benefit from a very simple story: send text to an API and get compressed text back. Cutctx currently requires a stronger mental model because it is a local-first proxy/control plane, which is better for power users but slower for adoption.

### Implement

1. Add a minimal hosted compression surface that mirrors the existing local pipeline.
2. Keep the hosted surface thin: one request in, one compressed response out, with the same compressor selection logic the local proxy uses.
3. Add an SDK wrapper for the hosted endpoint in Python and TypeScript.
4. Expose a clear compatibility mode for agentic text, RAG text, and raw tool output.
5. Preserve local-first behavior as the default. The hosted path should be additive, not a replacement for proxy mode.

### Verify

1. Send a representative prompt through the hosted endpoint and confirm the output matches the local proxy for the same input and settings.
2. Measure end-to-end latency on a small, medium, and large payload.
3. Confirm the response shape is stable across both SDKs.
4. Confirm the hosted path can be consumed with a simple `baseURL` swap.

### Prevent regression

1. Add golden tests that compare hosted and local compression outputs on fixed fixtures.
2. Add a contract test for response schema stability.
3. Keep the hosted layer behind an explicit feature flag until it reaches parity.
4. Add a test that proves local proxy behavior is unchanged when hosted mode is not enabled.

## P2. Gateway and observability depth

### Why this matters

Helicone is not just a gateway. It is a monitoring, routing, debugging, and policy surface for LLM traffic. Cutctx already has proxying, analytics, dashboards, and governance primitives, but not the same depth of request-level observability and “default control plane” ergonomics.

### Implement

1. Add first-class request tracing across prompt, compression, routing, and response stages.
2. Record session-level and request-level events with stable IDs that can be correlated in the dashboard.
3. Expose route metadata, provider choice, fallback behavior, and latency breakdowns.
4. Add rate-limit and budget views that are visible from the dashboard, not just enforced in the proxy.
5. Add a single-page request inspector that shows raw input, compressed input, retrieved originals, and final provider payload.
6. Add gateway controls for fallback routing and policy-aware provider selection.

### Verify

1. Send one request through the proxy and confirm the trace appears in the dashboard.
2. Confirm the trace includes compression decisions, provider choice, and latency.
3. Trigger a fallback path and verify it is visible in the trace.
4. Confirm the request inspector shows the same request across the proxy and dashboard views.
5. Confirm rate-limit events are recorded and queryable.

### Prevent regression

1. Add e2e tests that load the dashboard and inspect a known request trace.
2. Add API tests that assert trace records are written for every request in observability mode.
3. Keep observability additive and feature-flagged so the existing hot path stays stable.
4. Add a no-op test proving the proxy still works when observability storage is unavailable.

## P3. Benchmark and proof-point parity

### Why this matters

Morph has a very sharp claim: deletion-style compaction, 50-70% compression, 3,300+ tokens/sec. Cutctx has broader value, but we need similarly crisp proof for the narrow use case where we do compete head-on.

### Implement

1. Add a dedicated verbatim-compaction benchmark suite with fixed fixtures.
2. Split benchmarks into at least three categories: code/tool output, prose/RAG, and mixed agent traces.
3. Record tokens/sec, compression ratio, and verbatim fidelity as first-class metrics.
4. Add a line-level or block-level compaction mode that is easy to benchmark separately from the broader pipeline.
5. Publish a benchmark report that compares Cutctx to raw context, native provider compaction, and deletion-style compaction.

### Verify

1. Run the benchmark suite on pinned fixtures and confirm the results are reproducible.
2. Verify each benchmark emits all required metrics.
3. Confirm the benchmark report renders correctly in markdown and HTML.
4. Validate that verbatim outputs preserve exact file paths, line numbers, and error strings.

### Prevent regression

1. Store benchmark fixtures and expected outputs under version control.
2. Add a threshold test so tokens/sec or fidelity regressions fail CI.
3. Add a smoke benchmark that runs on every release branch.
4. Keep benchmark numbers separated by mode so a regression in one compressor does not hide inside an aggregate.

## P4. OSS and research baseline compatibility

### Why this matters

LLMLingua-2 remains the strongest recognizable OSS/research baseline in prompt compression. If we want to win technical evaluations, we should make Cutctx easy to compare against it instead of treating it as an external footnote.

### Implement

1. Keep the existing LLMLingua integration as a named, documented comparison arm.
2. Add a benchmark preset that runs Cutctx compression and LLMLingua-2 side by side on the same prompts.
3. Add a documented adapter path so researchers can swap compressors without rewriting the surrounding pipeline.
4. Provide an evaluation page that explains when Cutctx should beat LLMLingua-2 and when it should not.

### Verify

1. Confirm the adapter runs on the existing eval corpus without manual data reshaping.
2. Confirm the benchmark output includes both absolute and relative scores.
3. Confirm the docs clearly state the task class each compressor is intended for.

### Prevent regression

1. Add an integration test that loads the LLMLingua adapter and runs one known prompt.
2. Add a test that ensures the comparison preset continues to emit both result sets.
3. Keep evaluation fixtures stable so changes in tokenization or prompt shaping are visible, not accidental.

## P5. Enterprise procurement hardening

### Why this matters

Hosted competitors can sell faster because procurement is simple. Cutctx is stronger on self-hosting, but the docs already note that SOC 2, formal DPA/MSA, and third-party audit reports still need external validation.

### Implement

1. Turn the current enterprise materials into a procurement-ready packet with a fixed checklist.
2. Add a clear security evidence bundle for identity, audit, retention, and deployment posture.
3. Separate “available now” from “available with lighthouse customer support” in the docs.
4. Make the trust story easy to hand to legal, security, and IT reviewers.

### Verify

1. Confirm the procurement packet matches the actual shipped controls.
2. Confirm the docs do not overclaim compliance status.
3. Confirm the enterprise checklist can be completed without needing product-code inspection.

### Prevent regression

1. Add a docs review gate for all trust/compliance claims.
2. Add a checklist artifact that must be updated whenever enterprise controls change.
3. Keep a clear separation between shipped controls and planned controls in the product guide.

## Recommended sequencing

1. Ship P1 if the goal is fastest adoption.
2. Ship P2 if the goal is to compete with Helicone for control-plane ownership.
3. Ship P3 if the goal is to win technical bake-offs.
4. Ship P4 if the goal is to win research-heavy or OSS-first buyers.
5. Ship P5 if the goal is to reduce enterprise sales friction.

## Practical agent checklist

1. Read the current docs for the area you are changing.
2. Identify the smallest additive change that closes the gap.
3. Put the new behavior behind a feature flag if it changes runtime behavior.
4. Add one happy-path test and one regression test before making the change.
5. Run the smallest relevant test slice first.
6. Run the broader package or e2e slice after the targeted tests pass.
7. Update the docs or benchmark artifact only after behavior is verified.
