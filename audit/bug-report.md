# Model routing: `claude-sonnet-5` is not eligible

## Severity

High for users relying on aggressive model routing to reduce Claude Sonnet 5
costs. The proxy behaves safely (it does not select an unconfigured target),
but the UI mode implies a capability that the current route table cannot
provide for the observed traffic.

## Reproduction

1. Set the dashboard orchestrator/model-routing mode to **Aggressive**. This
   resolves to the `economy` preset.
2. Send an Anthropic request whose requested model is `claude-sonnet-5`.
3. Inspect Recent requests.

## Expected

For a low-risk request, a documented explicit downgrade route should change
the effective model; otherwise the dashboard should surface an actionable
`no_route_for_model` reason.

## Actual

The request remains on `claude-sonnet-5`. Directly exercising both bundled
presets returns:

```
economy: applied=False; reason=no_route_for_model; target=None
codex-gpt54mini-high: applied=False; reason=no_route_for_model; target=None
```

The `economy` route table includes `claude-sonnet-4-5` and older 3.5 Claude
identifiers, but no `claude-sonnet-5` source. `ModelRouter._find_route` only
performs an exact source-model match, so the requested model cannot route.

## Evidence

- Screenshot: every visible recent request is labelled `claude-sonnet-5`.
- `cutctx/proxy/model_router.py`: `economy_preset()` defines only 4.5/3.5
  Claude source routes; `maybe_route()` returns `no_route_for_model` when no
  exact source entry is found.
- Local direct routing check reproduced the returned reason for both presets.

## Suggested fix

Add an explicitly validated `claude-sonnet-5` downgrade mapping to the
appropriate supported target (and a matching exact-model regression test),
after confirming the upstream transport accepts that target. Also expose the
per-request routing-decline reason in the Recent requests UI so an unsupported
model is distinguishable from a disabled feature, bypass header, or
complexity-based abstention.
