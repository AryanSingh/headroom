# Competitor Routing and Compression Evidence Ledger

**Verification date:** 2026-07-17
**Standard:** A positive feature claim needs a dated source. A claim that a
competitor lacks a feature is `not_established` unless a primary source
directly confirms the absence.

## Verified sources

| Competitor | Claim supported by the source | Source | Status |
|---|---|---|---|
| LiteLLM | Maintains a documented catalogue of supported models and providers; this is evidence of broad gateway/provider coverage, not a directly comparable count of first-class Cutctx adapters. | [LiteLLM: Supported Models & Providers](https://docs.litellm.ai/docs/providers) | primary source checked 2026-07-17 |
| Portkey | Publishes model-routing documentation. This supports the claim that Portkey offers a routing surface; it does not establish a particular optimization algorithm without a source for that algorithm. | [Portkey: Model routing](https://portkey.ai/docs/product/ai-gateway/model-routing) | primary source recorded; feature detail requires claim-by-claim review |
| Claude Code | Publishes context and token-cost management guidance. This supports a cost-management comparison only, not a claim about byte-preserving proxy compression. | [Anthropic: Manage costs effectively](https://docs.anthropic.com/en/docs/claude-code/costs) | primary source checked 2026-07-17 |
| Aider | Publishes repository-map documentation. This supports a repository-context feature comparison, not an AST-compression equivalence claim. | [Aider: Repository map](https://aider.chat/docs/repomap.html) | primary source recorded; feature detail requires claim-by-claim review |

## Claims deliberately not made

The following prior claim forms are **not established** by this ledger and must
not be published as facts without new primary evidence:

- “No competitor has live-zone compression.”
- “No competitor has cache byte-fidelity.”
- “No competitor has ML content detection.”
- “No competitor has offload-and-retrieve or traffic-learning.”
- “Portkey has adaptive cost routing” (the precise behavior must be sourced).
- Any absolute “best in class,” “unique,” or “no competitor approaches” claim.

## Usage rule

Product and sales documentation may link a source-backed positive capability
claim to this ledger. It must state the scope of the comparison and must not
turn a missing source into a negative assertion about another product.
