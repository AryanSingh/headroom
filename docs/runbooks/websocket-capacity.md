# WebSocket Capacity Rejections

## Trigger

`WebSocketCapacityRejections` fires when `cutctx_ws_sessions_rejected_total`
increases. The proxy rejected a Codex WebSocket session before opening an
upstream connection because its configured admission limit was full.

## Immediate checks

1. Inspect `/health` and review `runtime.websocket_sessions` for `active`,
   `reserved`, `limit`, and `rejected_total`.
2. Confirm whether the workload has a legitimate burst or whether clients are
   reconnecting repeatedly after another upstream or network failure.
3. Check proxy CPU, memory, file descriptors, and upstream WebSocket errors
   before increasing capacity.

## Mitigation

Reduce client concurrency or reconnect pressure first. If the host has been
capacity-reviewed, increase `CUTCTX_MAX_WS_SESSIONS` deliberately and restart
or roll the proxy so the setting takes effect. A value of `0` disables the
admission limit; do not use it as an incident shortcut without a host resource
review.

## Follow-up

Record the observed peak active and reserved sessions, the configured limit,
and the cause of the pressure. Tune the limit with the operations owner based
on sustained resource measurements.

## Escalation

Alert delivery routes and on-call ownership are not configured in this
repository. Escalate through the operations process once an owner and receiver
are assigned; see `docs/runbooks/ops-alert-inventory.md`.
