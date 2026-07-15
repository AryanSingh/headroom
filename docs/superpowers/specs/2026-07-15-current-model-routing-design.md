# Current Model Routing Design

## Problem

The dashboard's Aggressive control selects the `economy` preset. That preset
does not declare routes for the current labels observed in production:
`gpt-5.6-terra` and `claude-sonnet-5`. The router consequently returns
`no_route_for_model`, yet the activity table only displays the effective model
and not the routing decision that explains the abstention.

## Decision

Maintain explicit, exact source-model routes in every bundled preset. Do not
use provider-family wildcards. Aggressive reuses the project-supported GPT-5
model graph with a cheapest eligible target (`gpt-5.4-mini`) and keeps the
existing hard safety classifier: tool context and high-complexity prompts are
not downgraded. Current Claude 5 identifiers receive explicit candidates only
when their selected target is in the configured transport-safe target set.

Routing evidence is persisted with the request log as a compact routing
summary: requested model, effective model, applied boolean, reason, and
candidate target. The Overview table renders this summary as a Routing column,
so `no_route_for_model`, `workload_not_downgradeable`, and successful routes
are distinguishable without opening a trace.

## Learning Model

The calibrated linear scorer remains an abstention layer. It can lower routing
eligibility after shadow evaluation, but it cannot override the deterministic
high-risk/tool-context gate or select a model without an explicit route.

## Verification

- Exact route-table tests prove every current project model label is present in
  the intended preset.
- Router tests prove a simple Terra request routes in Aggressive mode and a
  high-risk/tool-context request does not.
- Outcome/request-log tests prove routing summaries survive `/stats` output.
- Dashboard tests prove the activity table renders both an applied route and a
  named abstention reason.
