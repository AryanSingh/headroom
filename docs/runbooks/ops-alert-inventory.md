# Operations Alert Inventory

**Status:** Step 1 complete (inventory). Alert delivery, ownership, and staging
verification remain **BLOCKED — needs operations owner**.

**Last reviewed:** 2026-07-30 (verified-production-remediation worktree)

**Related plan:** Task 7 in
`docs/superpowers/plans/2026-07-29-verified-production-remediation-backlog.md`

---

## Scope and sources

This document inventories every alert rule, receiver, route, runbook link, and
owner discoverable in the repository. It does **not** claim that staging alert
delivery or on-call acknowledgement was tested.

| Source | Path | What it defines |
|--------|------|-----------------|
| PrometheusRule (deployed) | `k8s/prometheus-rules.yaml` | Four `cutctx.rules` alert expressions |
| Deployment scrape hints | `k8s/deployment.yaml` | `prometheus.io/scrape` pod annotations (`/metrics` on port 8787) |
| Helm ServiceMonitor (optional) | `helm/cutctx/templates/servicemonitor.yaml`, `helm/cutctx/values.yaml` | Prometheus Operator scrape config; **disabled by default** (`serviceMonitor.enabled: false`) |
| Recommended alerts (spec only) | `docs/spec/016-observability.md` | Four suggested alerts; example YAML uses obsolete metric `cutctx_errors_total` |
| Security policy mention | `docs/security/SECURITY_POLICY.md` | States automated alerting via Prometheus exists; no routing detail |
| Pilot incident procedure | `docs/pilot/incident-response.md` | Generic incident steps; no alert-to-runbook mapping |
| Backup runbook | `docs/runbooks/backup-restore.md` | Recovery procedure; references paging on-call without naming a destination |
| Support escalation template | `docs/pilot/support-and-escalation.md` | Blank support-channel fields; no named on-call owner |
| Metric catalogue | `cutctx/proxy/prometheus_metrics.py`, `docs/observability.md` | Exported proxy metrics used by alert expressions |

**Not found in repository:** Alertmanager configuration, notification receivers
(Slack, PagerDuty, email), routing trees, inhibition rules, on-call rotations,
synthetic uptime checks, or cert-manager / kube-state-metrics scrape configs.

---

## Notification routing (receivers and routes)

No Alertmanager `ConfigMap`, Helm values, or third-party integration manifest
exists in this repository. PrometheusRule resources define **when** an alert
fires; they do **not** define **where** notifications go.

| Component | Repository state | Notification destination | Owner |
|-----------|------------------|--------------------------|-------|
| Alertmanager deployment | **Not in repo** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** |
| Receivers (Slack, email, PagerDuty, webhook, etc.) | **Not in repo** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** |
| Route / match / continue tree | **Not in repo** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** |
| Severity-based routing (`critical` vs `warning`) | Labels present on rules only; no router | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** |
| Staging test-alert delivery (Task 7 Step 3) | **Not performed** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** |

Until an operations owner supplies and approves receiver configuration, every
alert below fires in Prometheus only with **no guaranteed human notification
path**.

---

## Current alert rules (`k8s/prometheus-rules.yaml`)

Resource: `PrometheusRule/cutctx-alerts` in namespace `cutctx`, group
`cutctx.rules`.

| Alert | Severity | Threshold / condition | `for` duration | Notification destination | Acknowledgement expectation | Named owner | Runbook link |
|-------|----------|----------------------|----------------|--------------------------|----------------------------|-------------|--------------|
| `HighErrorRate` | `critical` | `rate(cutctx_requests_failed_total[5m]) / clamp_min(rate(cutctx_requests_total[5m]), 1e-9) > 0.05` (failed share > 5%) | 5m | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **None linked in rule annotations.** Closest recovery docs: `docs/pilot/incident-response.md` (§4 Recovery), `docs/runbooks/backup-restore.md` |
| `HighLatency` | `warning` | `rate(cutctx_latency_ms_sum[5m]) / clamp_min(rate(cutctx_latency_ms_count[5m]), 1e-9) > 2000` (mean latency > 2000 ms) | 5m | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **None linked in rule annotations.** Closest: `docs/pilot/incident-response.md` |
| `UpstreamFailureSpike` | `warning` | `increase(cutctx_requests_failed_total[15m]) > 50` (> 50 failures in 15m window) | 10m | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **None linked in rule annotations.** Closest: `docs/pilot/incident-response.md` (§3 Evidence, §4 Recovery) |
| `WebSocketCapacityRejections` | `warning` | `increase(cutctx_ws_sessions_rejected_total[5m]) > 0` (one or more admission rejections) | 2m | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | **UNASSIGNED / BLOCKED — needs operations owner** | [`websocket-capacity.md`](websocket-capacity.md), linked by the rule's `runbook_url` annotation |

**Annotation gaps:** `WebSocketCapacityRejections` sets `runbook_url`.
The other three rules do not set `runbook_url`, `dashboard_url`, or `owner`
annotations. No named owner is available in this repository.

---

## Coverage vs Task 7 Step 2 signals

Comparison against the production signals named in the remediation plan.

| Signal | Current rule coverage | Metric / probe availability in repo | Recommended action (no ops owner required) |
|--------|----------------------|-------------------------------------|---------------------------------------------|
| **Availability / proxy down** | **Gap** — no `up`, `ProbeSuccess`, or `/readyz` alert | Scrape target health depends on cluster Prometheus config (`prometheus.io` annotations on `k8s/deployment.yaml`; optional Helm `ServiceMonitor`). `/livez` and `/readyz` probes exist on the Deployment but are not wired to PrometheusRule alerts. | **Recommended gap.** Draft expression (requires approved scrape `job` label): `up{job=~".*cutctx.*"} == 0` for 2m. Do not deploy until receiver and `job` label are confirmed by operations. |
| **High latency** | **Covered** by `HighLatency` | `cutctx_latency_ms_sum` / `cutctx_latency_ms_count` exported in `cutctx/proxy/prometheus_metrics.py` | None required for metric existence. Routing/owner still blocked. |
| **Error / upstream failure spikes** | **Covered** by `HighErrorRate` and `UpstreamFailureSpike` | `cutctx_requests_failed_total`, `cutctx_requests_total` exported | None required for metric existence. Consider deduplication policy once routing exists (two alerts can fire together). |
| **Storage / disk risk** | **Gap** | PVC `10Gi` ReadWriteOnce (`k8s/pvc.yaml`). No kubelet volume or node-exporter disk metrics referenced in repo. Backup CronJob (`k8s/backup-cronjob.yaml`) has no failure alert. | **Recommended gap.** Requires cluster-level metrics (`kubelet_volume_stats_*`, node filesystem) and operations-approved thresholds. Not implementable from application metrics alone. |
| **Certificate expiry** | **Gap** | Ingress TLS placeholder (`k8s/ingress.yaml`); `cert-manager.io/cluster-issuer` annotation is commented out. No cert-manager metrics or Certificate resources in repo. | **Recommended gap.** Requires cert-manager (or ingress-controller) metrics in the monitoring stack. Do not fabricate receivers. |
| **WebSocket admission pressure** | **Covered** by `WebSocketCapacityRejections` | `cutctx_ws_sessions_rejected_total` is exported on `/metrics`; `/health` reports configured capacity and active/reserved/rejected session state. | Review [`websocket-capacity.md`](websocket-capacity.md). Receiver, acknowledgement, and ownership remain blocked on operations. |
| **Inbound service saturation** | **Partial gap** | `cutctx_inbound_requests_active` gauge exported. | **Recommended gap** for inbound saturation: draft `cutctx_inbound_requests_active > <T>` once operations defines `<T>`. |

### Draft alert candidates (metrics confirmed; deployment blocked on ops)

These expressions are **documentation only**. Do not add to
`k8s/prometheus-rules.yaml` until an operations owner approves thresholds,
receivers, and staging delivery.

```yaml
# Availability — requires confirmed Prometheus scrape job label
- alert: CutctxProxyScrapeDown
  expr: up{job=~".*cutctx.*"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: Cutctx proxy metrics scrape is down

# Inbound concurrency — threshold T must be set by operations
- alert: CutctxInboundConcurrencyHigh
  expr: cutctx_inbound_requests_active > 100  # placeholder; ops must set T
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: Cutctx proxy inbound request concurrency is elevated

# Rate-limit pressure — useful upstream-health signal; threshold needs tuning
- alert: CutctxRateLimitPressure
  expr: rate(cutctx_requests_rate_limited_total[5m]) > 1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: Cutctx proxy is rate-limiting inbound requests
```

### Spec vs deployed divergence (`docs/spec/016-observability.md`)

The observability spec recommends `HighErrorRate`, `LowSavings`, `CacheDown`, and
`ProxyDown` but its example uses `cutctx_errors_total`, which is **not** exported
by the current proxy. Deployed rules in `k8s/prometheus-rules.yaml` instead use
`cutctx_requests_failed_total` and include `HighLatency` and `UpstreamFailureSpike`
not listed in the spec table. `LowSavings`, `CacheDown`, and `ProxyDown` remain
undocumented in deployed YAML.

---

## Incident procedure stub — customer status updates

**Status-update ownership: BLOCKED — needs operations owner**

The pilot incident template (`docs/pilot/incident-response.md` §5) requires a
customer communication owner and update cadence but does not name who holds that
role or which public status channel to use.

Until an operations owner is named:

1. **Incident commander** — **UNASSIGNED / BLOCKED — needs operations owner**
2. **Customer / status communication owner** — **UNASSIGNED / BLOCKED — needs operations owner**
3. **Public status page or customer notification channel** — **UNASSIGNED / BLOCKED — needs operations owner**
4. **Initial customer update SLA** — **UNASSIGNED / BLOCKED — needs operations owner**
5. **Synthetic uptime checks for public critical paths** (Task 7 Step 4) — **Not configured in repo**

When an operations owner is assigned, extend this section with: named roles,
PagerDuty/Slack escalation paths, status-page URL, and the mapping from each
alert in the table above to a specific runbook section.

---

## Open actions (requires operations owner)

| Action | Task 7 step | Blocker |
|--------|-------------|---------|
| Name alert receivers and Alertmanager routes | Step 1 (routing), Step 5 | No operations owner |
| Add `runbook_url` / `owner` annotations to PrometheusRule alerts | Step 1 | No named owner |
| Approve and deploy draft availability / saturation alerts | Step 2 | Thresholds + scrape `job` label + receiver |
| Send staging test alert and record acknowledgement | Step 3 | Staging environment + destination not named |
| Configure synthetic uptime checks and status communications | Step 4 | No status-page owner |
| Reconcile `docs/spec/016-observability.md` with deployed rules | Follow-on | Product/docs owner optional |
