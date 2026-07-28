# Why Codex/OpenAI traffic shows ~0% savings

Reported symptom: OpenAI models save nothing. Measured on this install's own
ledger, that is true, it is large, and it is **not** a property of the models.

## It is the client, not the model

| Client | Requests | Input tokens | Saved | Save rate |
| --- | ---: | ---: | ---: | ---: |
| **codex** | 45,602 | **4,161,632,503** | 13,818,217 | **0.33%** |
| opencode | 8,154 | 927,779,554 | 176,869,321 | 19.1% |
| claude-code | 6,605 | 251,299,253 | 82,572,491 | 32.9% |
| cursor | 6 | 5,006 | 4,403 | 88.0% |

Per model, the same split shows up — every `gpt-5.6-*` variant is Codex
traffic:

| Model | Requests | Input tokens | Saved | Save rate |
| --- | ---: | ---: | ---: | ---: |
| gpt-5.6-terra | 29,528 | 2,238,878,660 | 180,194 | 0.0% |
| gpt-5.6-sol | 6,889 | 948,854,818 | 169,126 | 0.0% |
| gpt-5.6-luna | 3,076 | 343,423,782 | 305 | 0.0% |
| gpt-5.4 | 4,287 | 398,311,680 | 8,354,234 | 2.1% |
| claude-sonnet-5 | 3,012 | 143,282,589 | 43,748,805 | 30.5% |
| claude-haiku-4-5 | 2,919 | 99,658,532 | 36,459,268 | 36.6% |

**4.16 billion input tokens through Codex at 0.33%.** At claude-code's 32.9%
that would be on the order of 1.4 billion tokens.

Two explanations that do *not* hold, checked first:

- **Not unknown models.** `gpt-5.6-terra`, `-sol` and `-luna` all resolve a
  context limit (1,050,000) and a working tokenizer.
- **Not "short turns".** Codex averages ~76,000 input tokens per request.

## The Codex path works — on the content it can compress

Driving `_compress_openai_responses_live_text_units_with_router` directly with
Codex-shaped payloads (`function_call` + `function_call_output`, tool name
`shell`):

| Content in the tool output | Saved |
| --- | ---: |
| Shell / log output | **94.2%** |
| Source code | 0.0% |
| Patch / diff | 0.0% |
| Reasoning prose | 0.0% |
| `reasoning` items | 0.0% — not exposed as text units by design |

Conversation depth is not the limiter: with log content, every tool output
compresses at 2, 6, 20 and 60 turns (98.7% throughout).

So the handler is fine. **Codex context is overwhelmingly source code,
patches, and reasoning — and all three are 0% in the default configuration.**
Shell output, the one shape that compresses well, is a minority of a coding
agent's context.

`--enable-kompress` does *not* rescue it on this path, and the reason is not
what it first looked like. Driving `compress_unit_with_router` directly on a
`function_call_output` unit with Kompress enabled:

| Content | Unit result |
| --- | --- |
| Logs | ratio 0.007 — accepted |
| Reasoning prose | ratio **0.932** — compressed only 6.8% |
| Source code | `reason=router_no_change` |

So the unit adapter is **not** rejecting these units — an earlier revision of
this page said it was, and that was wrong. What happens is:

- **Code** reaches the router and the router changes nothing
  (`router_no_change`), because `code_aware_enabled` is off.
- **Prose** does compress, but only to 0.932, which fails the acceptance gate
  (`min_ratio_relaxed = 0.85`). The result is correctly discarded, so the
  payload shows 0%.

That distinction matters for what to do next: the plumbing is fine and the
acceptance gate is doing its job. The gap is that Kompress only finds ~7% on
this content.

## Why each shape is zero

- **Source code** — `code_aware_enabled` is off by default. Measured, that is
  the right default: it elides ~a quarter of function-body statements while
  keeping signatures, and emits invalid Python on half the files tested. See
  `docs/measured-savings.md`.
- **Patches / diffs** — difftastic is opt-in and only matches `Bash` tool
  output that parses as a unified diff, not patch text inside a
  `function_call_output`.
- **Reasoning prose** — routes to the prose compressor, which needs query
  terms to select against and leaves text untouched without them.
- **`reasoning` items** — deliberately excluded from text-unit extraction, as
  are compaction and tool-call items.

## Full eligibility map

Measured by running every item shape a real Codex turn contains through the
extractor, with the new `responses_extraction` tally:

| Item type | Compressed | Assessment |
| --- | --- | --- |
| `function_call_output` | **yes** | working |
| `local_shell_call_output` | **yes** | working |
| `apply_patch_call_output` | eligible, no change | content is code/patch — see below |
| `message` (user) | no | correctly protected |
| `message` (assistant) | no | reported `unsupported:message`, though unit policy would protect it anyway |
| `reasoning` | no | model-authored and cache-anchored |
| `function_call` | no | mutating tool arguments would corrupt the call |

**Every skipped shape is skipped correctly.** User messages are protected,
assistant messages are protected by unit policy, tool arguments must not be
rewritten or the call breaks, and reasoning items are model-authored context
the provider expects back intact.

So the extraction rules are not the bug, and widening them is not the fix.
Codex's tool outputs — the one category that *is* eligible — carry source code
and patches, and those are 0% by deliberate configuration.

## What to do about it

1. **The unlock for Codex is safe code compression, not more extraction.**
   That is an R&D problem, not a config change. `code_aware` exists and is off
   for measured reasons: it elides ~a quarter of function-body statements
   while preserving signatures, and emits invalid Python on half the files
   tested (`docs/measured-savings.md`). A coding agent is precisely the
   consumer that harms. Anything shipped here needs a fidelity bar, not a
   compression ratio.
2. **Fix the `unsupported:message` label.** Assistant messages are reported as
   an unsupported *type* when they are really a protected *role*. The tally is
   now the primary diagnostic for this path, so a misleading reason in it will
   cost somebody an afternoon.
3. **Do not widen extraction to reasoning or tool arguments** without a
   provider-contract review. Both are plausible-looking and both risk
   corrupting the request.

## Reproduce

```bash
python scripts/savings_harness.py --scenario openai_chat:logs --scenario compression:logs
```

Client and model ledgers come from the proxy's own savings state
(`~/.cutctx/proxy_savings.json`), not a synthetic benchmark.
