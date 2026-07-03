# Outreach Current Positioning

Date: 2026-07-03
Status: Release-ready messaging scope

## Current Buyer Message

Lead with control, assurance, and attribution:

> Cutctx is a local-first context control plane for AI agents. It reduces
> context cost, keeps originals retrievable, enforces policy before requests
> leave your infrastructure, and proves what happened through reports, replay,
> and assurance evidence.

Token savings are proof, not the only headline.

## Safe Claims

- Local-first proxy/wrap/library surfaces are implemented.
- Savings attribution separates Cutctx compression, provider cache, semantic
  cache, and other savings sources where telemetry exists.
- WS7 local Context Assurance exists as a HMAC-SHA256 evidence ledger with
  JSON/markdown export and `--verify`.
- WS8 replay exists behind `CUTCTX_REPLAY=1` for policy and pipeline timeline
  events.
- Provider-native caching is complementary, not replaced.
- Full local Python/Rust/dashboard verification is green for the current
  branch, with live-provider tests skipped when credentials are absent.

## Claims That Need Care

- Do not claim SOC 2 completion unless the actual report exists.
- Do not imply hosted SaaS billing or customer portal flows are proven unless
  the active environment verifies them.
- Do not claim enterprise assurance is fully packaged until release owners
  approve EE packaging/signing and positioning.
- Do not promise one universal savings percentage. Use workload-specific
  benchmark outputs.

## P0 Startup Email

Subject: `your coding agents are wasting context on tool output`

Hi {first_name},

Saw {company} is building with {Claude Code / Codex / Cursor / agents}. Cutctx
is a local-first context control plane: it compresses logs, diffs, JSON, search
results, and tool output before they hit the model, then reports exactly where
savings came from.

The useful part for a small team: one local proxy, no app rewrite, and a buyer
report that separates Cutctx savings from provider-native cache wins.

Open to a 20-minute design-partner walkthrough? We can use your own agent trace
or a synthetic benchmark and leave you with an Agent Context Report.

## P1 Platform/SRE Email

Subject: `context replay and savings attribution for agent workflows`

Hi {first_name},

If your platform team is standardizing AI agents, Cutctx gives you a local
control plane for context: policy before upstream, source-level savings
attribution, replay timelines, and a HMAC-backed evidence ledger for assurance
review.

It is complementary to provider prompt caching. Provider cache handles stable
prefixes; Cutctx handles the noisy operational context agents actually produce:
logs, diffs, tool output, JSON, and code/search payloads.

Worth a short design-partner review against one workflow your team already
runs?

## P2 Enterprise/Regulated Email

Subject: `local-first AI context control with replay and evidence export`

Hi {first_name},

Cutctx runs as a local proxy/control plane for AI agents. It gives teams policy
enforcement, savings attribution, replay timelines, and a local HMAC-SHA256
evidence ledger without sending prompts through a new SaaS hop.

We are looking for design partners who care about governance as much as token
cost. The pilot output is concrete: benchmark results, Agent Context Report,
replay sample, and assurance export.

Would a 30-minute technical review be useful?

## Demo Close

Use this close:

> If this saves budget but cannot prove what happened, it is just a compressor.
> Cutctx is the control plane: savings, policy, memory, replay, and assurance in
> one local path.
