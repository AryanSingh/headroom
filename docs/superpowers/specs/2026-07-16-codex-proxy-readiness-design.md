# Codex Proxy Readiness Design

## Problem

Codex is globally configured to use the Cutctx Responses proxy at
`http://127.0.0.1:8787/v1`. On a cold restart, the proxy needs roughly two
minutes to import optional components and warm its compression models. Existing
launch helpers can continue after a shorter timeout, leaving Codex connected to
a closed or not-yet-ready port. This causes `stream disconnected before
completion` failures.

## Decision

The local `com.cutctx.proxy` launch agent is the single persistent owner of
port 8787. The Codex launcher and manual restart helper must wait for
`/readyz`, not merely a listening port or `/health`, before starting or
reporting success. The waiting period is 180 seconds, which covers the observed
cold start; expiry is a failure, not a warning that allows Codex to continue.

## Components

- `~/Library/LaunchAgents/com.cutctx.proxy.plist` is bootstrapped into the
  current launchd GUI domain and remains enabled for login/startup recovery.
- `~/.local/bin/codex-cutctx-lib.sh` remains the Codex launcher boundary. Its
  `codex_cutctx_ensure_proxy` function starts the launch agent when needed,
  waits for an HTTP 200 from `/readyz` for at most 180 seconds, and returns a
  non-zero status if readiness is never reached.
- `restart-proxy.sh` uses the same 180-second `/readyz` contract and exits
  non-zero on failure, avoiding a false-ready result.

## Failure Handling

If a proxy process is alive but not ready, launchers poll readiness instead of
creating a competing process. If it never becomes ready, they preserve logs,
return failure, and do not start Codex. This makes the error actionable and
prevents an unreliable Responses stream from being opened.

## Verification

The regression checks inspect each launcher for the 180-second `/readyz`
contract and fail-closed behavior. A live verification then confirms the
launch-agent service is loaded and that the active proxy returns HTTP 200 from
`/readyz` before Codex is allowed to use it.
