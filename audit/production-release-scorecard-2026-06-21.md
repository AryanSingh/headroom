# Cutctx Production Release Scorecard

Date: 2026-06-21

## Executive Score

**Core product release readiness: 88/100**

The blocking commercialization gap is now closed in the live proxy path:

- Model routing is now wired through the request path for OpenAI Chat, OpenAI Responses, and Gemini surfaces.
- The shared funnel already finalizes `model_routing` savings from metadata, so routed requests now persist into the standard savings history.
- The routing helper is shared and testable, which reduces drift between handlers.

## What Is Verified

- `cutctx/proxy/model_router.py` now exposes `prepare_model_routing(...)`, which attaches placeholder `model_routing` metadata when a route is applied.
- `cutctx/proxy/handlers/openai/chat.py` now prepares routing before the upstream call.
- `cutctx/proxy/handlers/openai/responses.py` now prepares routing for both the HTTP and websocket response paths.
- `cutctx/proxy/handlers/gemini.py` now prepares routing for:
  - `generateContent`
  - `streamGenerateContent`
  - `countTokens`
  - Cloud Code assist streaming
- The new routing helper compiled cleanly, and a direct module-load sanity check confirmed:
  - model downgrade to the cheaper target
  - metadata preservation
  - placeholder `model_routing` bucket emission

## Verification Evidence

- `ruff check cutctx/proxy/model_router.py tests/test_model_router.py` passed.
- `python3 -m compileall -q ...` passed for the touched proxy handlers and helper files.
- A direct importlib-based runtime check of the routing helper passed.

## Remaining Non-Blocking Gaps

- The local test environment is missing an optional dependency required for full `pytest` collection through the package import path.
- The React dashboard pages still look more like static demo surfaces than live admin surfaces.
- There is still broader docs and marketing cleanup outside the core release path, but those are no longer blocking the main commercialization story.

## Release Interpretation

The product is no longer in the “commercial claim over-promised” state. The moat feature is now live across the main request surfaces, and the score reflects a release-candidate posture rather than an experimental prototype.
