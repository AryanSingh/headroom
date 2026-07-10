# Live Savings Canary Runbook

This runbook describes the exact sequence for producing trustworthy live canary data for
CutCtx savings experiments on Codex and GPT-5.x traffic. It covers the remaining engineering
prerequisites, deployment, traffic generation, task-quality feedback, monitoring, reporting,
promotion, rollback, and final acceptance.

Do not claim the 20% savings target from unit tests or synthetic source attribution alone.
The target is achieved only after a live treatment arm has enough representative traffic,
passes the quality/cache guardrails, and produces a decision-ready report.

## 1. Experiment contract

The initial allocation is:

| Arm | Allocation | Behavior |
| --- | ---: | --- |
| `control` | 70% | Existing production optimization behavior |
| `mutable_tail` | 10% | More aggressive compression of mutable tool results while preserving stable prefixes |
| `tool_api_slimming` | 10% | More aggressive tool-schema and API-surface reduction |
| `model_routing` | 10% | Route eligible low-complexity work through `codex-gpt54mini-high` |

An eligible request is one whose detected client is `codex` or whose requested model name
starts with `gpt-5`.

The release criteria for a treatment arm are:

1. At least 100 request samples in control and the treatment arm.
2. At least 100 task-quality samples in control and the treatment arm.
3. Created savings per million input tokens is at least 20% higher than control.
4. Task-quality success is no more than 1% below control.
5. Provider prompt-cache value per input token is no more than 1% below control.
6. Combined created plus provider-observed savings per input token does not decline.
7. The treatment has not been automatically paused.
8. The 95% confidence interval and raw sample counts are included in the published report.

Because each treatment initially receives 10% of eligible requests, collecting 100 requests
per treatment normally requires at least 1,000 eligible requests overall. Run longer when
traffic is uneven or confidence intervals remain wide.

## 2. Release blockers to complete before live data collection

Implementation status (2026-07-10): the three code blockers in sections 2.1–2.3 are
implemented and covered by automated tests. Canary state is restart-safe, Codex assignment
uses the shared privacy-safe identity resolver, request-ID-only traffic is excluded, and
quality feedback is idempotent. The remaining work in this runbook is operator work:
releasable-build isolation, staging configuration, representative traffic, observation,
and controlled promotion.

### 2.1 Persist canary state across proxy restarts

Status: implemented in `cutctx/proxy/savings_canary.py`.

Current metrics, paused arms, sticky assignments, and 25%/50% promotions are held in memory.
A restart resets them. Implement persistence before using data across restarts.

Use the following exact persisted shape:

```json
{
  "schema_version": 1,
  "salt_fingerprint": "sha256-prefix-only",
  "allocations": {
    "mutable_tail": 10,
    "tool_api_slimming": 10,
    "model_routing": 10
  },
  "paused": {},
  "metrics": {
    "control": {},
    "mutable_tail": {},
    "tool_api_slimming": {},
    "model_routing": {}
  },
  "sticky_assignments": {},
  "feedback_event_ids": []
}
```

Implementation requirements:

1. Add a configurable path named `CUTCTX_SAVINGS_CANARY_PATH`.
2. Default it to `~/.cutctx/savings_canary.json`.
3. Load it when `SavingsCanaryCoordinator` is created.
4. Reject or archive files with an unsupported schema version.
5. Store only a fingerprint of the salt, never the salt itself.
6. Persist after a request observation, feedback event, automatic pause, or promotion.
7. Write to a temporary file, `fsync`, then atomically replace the destination.
8. Create the file with user-only permissions (`0600`).
9. Protect in-process updates with the existing coordinator lock.
10. Protect multi-process updates with a file lock or SQLite transaction.
11. Bound sticky assignments and feedback IDs; keep the most recent 50,000 of each.
12. On startup, verify that allocations total no more than 100%.
13. If the configured salt fingerprint differs from the persisted fingerprint, refuse to
    continue the experiment until an operator explicitly starts a new experiment.

Required tests:

```bash
uv run pytest -q tests/test_savings_attribution_v6.py
```

Add coverage proving:

- metrics survive coordinator reconstruction;
- paused arms survive restart;
- promoted allocations survive restart;
- the same identity remains in the same arm after restart;
- corrupted state is quarantined without silently merging invalid data;
- duplicate feedback event IDs are ignored;
- a salt change is detected and blocks accidental cohort reshuffling.

### 2.2 Provide a stable assignment identity for Codex

Status: implemented in `cutctx/proxy/canary_identity.py` and shared by OpenAI Chat,
Responses HTTP, and Responses WebSocket handling.

The coordinator supports `X-Cutctx-Session-Id`, `X-Session-Id`, and `Session-Id`, but
`cutctx wrap codex` does not currently inject one into native Codex traffic. Falling back to
request ID creates request-level randomization rather than task/session-level stickiness.

Implement one stable identity resolver shared by OpenAI Chat and Responses paths with this
priority order:

1. `X-Cutctx-Session-Id` from trusted internal traffic.
2. Existing Codex WebSocket/session identifier.
3. Existing turn or conversation identifier.
4. A privacy-safe hash of authenticated user, project, and conversation identifiers.
5. Request ID only as the final fallback, with `assignment_sticky=false` in telemetry.

Requirements:

1. Never persist raw OAuth tokens, API keys, prompts, or user email addresses.
2. Hash identity material with the configured canary salt before persistence.
3. Reuse the identity across all HTTP calls and WebSocket frames for one Codex task.
4. Include `assignment_identity_source` and `assignment_sticky` in request traces.
5. Exclude non-sticky requests from promotion decisions unless explicitly allowed for a
   development-only experiment.
6. Add an integration test that makes multiple requests for one simulated Codex session and
   proves every request lands in the same arm.
7. Add a second test proving two different sessions can land in different arms.

### 2.3 Make task-quality feedback idempotent and automatic

Status: implemented in the admin feedback route and
`cutctx/evals/canary_feedback.py`; the before/after evaluation runner posts one
best-effort event per completed case when the documented feedback environment variables
are configured.

The feedback endpoint currently accepts aggregate arm data. For live use, feedback must be
linked to a unique task and must not be counted twice.

Extend `POST /savings-canary/feedback` to accept:

```json
{
  "event_id": "evaluation-run/task-id",
  "request_id": "request-id-or-null",
  "arm": "mutable_tail",
  "quality_success": true,
  "retries": 0,
  "user_corrections": 0,
  "evaluator": "coding-eval-v1",
  "evaluated_at": "2026-07-10T12:00:00Z"
}
```

Requirements:

1. Reject missing `event_id`, `arm`, or `quality_success` with HTTP 422.
2. Return HTTP 200 with `duplicate=true` for an already-recorded `event_id` without changing
   counters.
3. When `request_id` is supplied, verify that its trace arm matches the submitted arm.
4. Store only evaluation metadata, not prompt or response bodies.
5. Have the coding evaluation harness post feedback automatically after every completed task.
6. Treat evaluator infrastructure failures as missing data, not task failures.
7. Do not promote an arm until task-quality sample counts meet the minimum.

## 3. Prepare a releasable build

The repository may contain unrelated work. Do not deploy the entire dirty worktree without
reviewing it.

1. Create a clean branch or worktree from the intended release base.
2. Bring in only the savings attribution, dashboard, canary, report, tests, and generated
   dashboard assets required for this release.
3. Confirm that generated dashboard asset deletions and additions are intentional.
4. Review the diff for secrets and unrelated files.
5. Run whitespace validation:

```bash
git diff --check
```

6. Compile the modified Python modules:

```bash
uv run python -m py_compile \
  cutctx/proxy/savings_canary.py \
  cutctx/proxy/outcome.py \
  cutctx/proxy/savings_tracker.py \
  cutctx/proxy/model_router.py \
  cutctx/proxy/routes/admin.py \
  cutctx/proxy/server.py \
  scripts/generate_savings_canary_report.py
```

7. Run the focused backend suite:

```bash
uv run pytest -q \
  tests/test_savings_attribution_v6.py \
  tests/test_proxy_savings_history.py \
  tests/test_savings_tracker_schema_migration.py \
  tests/test_model_router.py \
  tests/test_request_outcome.py \
  tests/test_savings_breakdown_usd_parity.py \
  tests/test_openai_codex_routing.py \
  tests/test_anthropic_model_routing.py \
  tests/test_anthropic_semantic_cache_outcome.py \
  tests/test_proxy/test_request_logger.py \
  tests/test_proxy/test_request_trace_inspector.py \
  tests/test_route_modules.py
```

8. Build, lint, and embed the dashboard:

```bash
cd dashboard
npm run lint
npm run build
cd ..
make build-dashboard
```

9. Run dashboard verification:

```bash
uv run pytest -q \
  tests/test_dashboard_savings_period_and_metric_toggle.py \
  tests/test_dashboard_embedded_build.py
```

10. Run the complete repository CI suite before production deployment. Treat focused tests as
    necessary but not sufficient.

## 4. Create staging secrets and configuration

Use a staging environment with representative traffic and one long-lived proxy instance for
the first experiment.

Generate secrets once:

```bash
openssl rand -hex 32
```

Store separate values in the deployment secret manager for:

- `CUTCTX_ADMIN_API_KEY`
- `CUTCTX_SAVINGS_CANARY_SALT`

Do not commit either value to `.env`, shell history, logs, screenshots, or this runbook.

Configure the staging proxy:

```bash
export CUTCTX_ADMIN_API_KEY='<from-secret-manager>'
export CUTCTX_SAVINGS_CANARY_ENABLED=1
export CUTCTX_SAVINGS_CANARY_PERCENT=10
export CUTCTX_SAVINGS_CANARY_REGRESSION_LIMIT=0.01
export CUTCTX_SAVINGS_CANARY_MIN_SAMPLES=100
export CUTCTX_SAVINGS_CANARY_SALT='<from-secret-manager>'
export CUTCTX_SAVINGS_CANARY_PATH="$HOME/.cutctx/savings_canary-staging.json"
export CUTCTX_MODEL_ROUTING_PRESET='codex-gpt54mini-high'
```

Keep semantic response caching out of this initial experiment. Do not enable a separate
semantic-cache treatment while measuring these three arms.

## 5. Start the staging proxy

From the clean release checkout:

```bash
uv run cutctx proxy \
  --host 127.0.0.1 \
  --port 8787 \
  --model-routing-preset codex-gpt54mini-high
```

For a shared staging environment, bind to the approved internal interface instead of
`127.0.0.1`, terminate TLS at the approved ingress, and restrict admin endpoints to the
operator network.

Do not run multiple proxy workers until canary persistence has a tested multi-process lock.

In a second terminal, define helpers without printing the key:

```bash
export CUTCTX_URL='http://127.0.0.1:8787'
export CUTCTX_ADMIN_API_KEY='<from-secret-manager>'
```

Verify health:

```bash
curl --fail --silent --show-error "$CUTCTX_URL/health" | jq .
```

Verify the canary report is enabled and empty:

```bash
curl --fail --silent --show-error \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  "$CUTCTX_URL/savings-canary/report" | jq .
```

The initial response must show:

```json
{
  "enabled": true,
  "allocations": {
    "mutable_tail": 10,
    "tool_api_slimming": 10,
    "model_routing": 10
  },
  "control_percent": 70,
  "regression_limit_percent": 1.0,
  "minimum_samples": 100
}
```

Verify runtime flags:

```bash
curl --fail --silent --show-error \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  "$CUTCTX_URL/config/flags" | jq .
```

Enable the orchestrator if it is inactive:

```bash
curl --fail --silent --show-error \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  --data '{"orchestrator":true}' \
  "$CUTCTX_URL/config/flags" | jq .
```

Confirm `orchestrator` is enabled before sending model-routing treatment traffic.

## 6. Route representative traffic through staging

### 6.1 Codex CLI traffic

When using the standalone proxy above, launch Codex without starting another proxy:

```bash
uv run cutctx wrap codex --no-proxy --port 8787
```

Before relying on this for a production-quality canary, complete the stable Codex identity
work in section 2.2 and verify traces show `assignment_sticky=true`.

### 6.2 Generic OpenAI-compatible clients

Point the client at:

```text
http://127.0.0.1:8787/v1
```

For every logical task/session, send a stable header:

```text
X-Cutctx-Session-Id: <stable-random-session-id>
```

Use a random opaque value. Do not use an email, API key, prompt text, or repository path.

### 6.3 Workload matrix

Use the same task distribution for the control and treatment populations. Include:

| Workload | Minimum share | Required checks |
| --- | ---: | --- |
| Small code edit | 20% | Patch correctness, tests, tool validity |
| Repository search/debugging | 20% | Correct files found, cache value retained |
| Multi-turn implementation | 25% | Stable session assignment, mutable-tail benefit |
| Tool-heavy task | 20% | Tool names/arguments remain valid |
| Complex architecture/refactor | 15% | Router keeps work on requested model |

Include requested models `gpt-5.4`, `gpt-5.4-mini`, and `gpt-5.5`. Record the requested and
actual model from request traces. Do not count test fixtures, health probes, admin calls, or
short empty prompts as experiment samples.

## 7. Verify assignment and attribution before scaling traffic

After the first 20 eligible requests, inspect the live report:

```bash
curl --fail --silent --show-error \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  "$CUTCTX_URL/savings-canary/report" \
  | jq '{enabled, allocations, control_percent, metrics, decisions}'
```

Inspect individual traces:

```bash
curl --fail --silent --show-error \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  "$CUTCTX_URL/transformations/traces?limit=20" \
  | jq '.traces[] | {
      request_id,
      model: .provider.actual_model,
      arm: .canary.arm,
      eligible: .canary.eligible,
      created_tokens: .attribution.created_savings_tokens,
      observed_tokens: .attribution.observed_provider_savings_tokens,
      funnel: .compression.opportunity_funnel
    }'
```

Stop immediately and fix instrumentation if any of these occur:

- all eligible requests land in control;
- no requests appear in one or more treatment arms after a reasonable sample;
- created plus observed source totals do not reconcile;
- pricing basis is missing;
- tool/API and mutable-tail arms never record their corresponding transforms;
- routing-arm requests never show requested/actual model information;
- session requests move between arms;
- decline reasons remain absent when requests are known to be skipped.

## 8. Run task evaluation and submit feedback

Each logical coding task must produce one idempotent quality event. Do not submit one quality
event for every streaming frame or internal subrequest.

The evaluator should check at minimum:

1. Did the task finish successfully?
2. Did required tests pass?
3. Were tool calls syntactically and semantically valid?
4. Was a retry required because of model/compression behavior?
5. Did a human or automated reviewer correct the result?

For the built-in before/after evaluation harness, enable automatic best-effort feedback
before starting each arm-specific run:

```bash
export CUTCTX_SAVINGS_CANARY_FEEDBACK_URL="$CUTCTX_URL"
export CUTCTX_SAVINGS_CANARY_EVAL_ARM="model_routing"
export CUTCTX_SAVINGS_CANARY_EVALUATOR="coding-eval-v1"
export CUTCTX_SAVINGS_CANARY_EVAL_RUN_ID="staging-model-routing-001"
```

Change `CUTCTX_SAVINGS_CANARY_EVAL_ARM` and use a new run ID for each independent arm.
The harness posts after every completed case. Delivery failures are logged and treated as
missing quality data, never as task failures.

For external evaluators, submit the same contract directly:

```bash
curl --fail --silent --show-error \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  --data '{
    "event_id":"evaluation-run-001/task-0042",
    "request_id":"REQUEST_ID",
    "arm":"mutable_tail",
    "quality_success":true,
    "retries":0,
    "user_corrections":0,
    "evaluator":"coding-eval-v1",
    "evaluated_at":"2026-07-10T12:00:00Z"
  }' \
  "$CUTCTX_URL/savings-canary/feedback" | jq .
```

Retries are safe: the endpoint returns `duplicate=true` with HTTP 200 and does not change
counters when an `event_id` was already accepted. When `request_id` is supplied, a mismatch
between the trace arm and submitted arm is rejected with HTTP 422.

At the end of each evaluation batch, reconcile:

```text
completed evaluated tasks
= successful quality events
+ failed quality events
+ documented evaluator-infrastructure failures
```

## 9. Monitor the experiment

Poll the report every 5–15 minutes during active staging traffic and archive a snapshot at
least hourly.

```bash
mkdir -p artifacts/savings-canary-snapshots
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
curl --fail --silent --show-error \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  "$CUTCTX_URL/savings-canary/report" \
  > "artifacts/savings-canary-snapshots/$timestamp.json"
```

Monitor these fields for every arm:

- `requests`
- `input_tokens`
- `created_savings_usd_per_million_input_tokens`
- `created_savings_rate_95_percent_ci`
- `quality_samples`
- `quality_success_rate`
- `quality_success_95_percent_ci`
- `provider_cache_value_usd`
- `combined_savings_usd`
- `average_latency_ms`
- `retries`
- `user_corrections`
- `paused`
- `pause_reason`
- `rollout_decision`

An automatic pause is a hard stop. Do not manually promote a paused arm. Investigate the
request traces, correct the issue, start a new clean evaluation window, and document why the
old window was invalidated.

## 10. Produce the decision report

After all arms meet minimum request and quality sample counts:

```bash
uv run python scripts/generate_savings_canary_report.py \
  "$CUTCTX_URL/savings-canary/report" \
  --admin-key "$CUTCTX_ADMIN_API_KEY" \
  --json-output artifacts/savings-canary-report.json \
  --markdown-output artifacts/savings-canary-report.md
```

Review both files. The report is incomplete if any treatment has:

- fewer than 100 requests;
- fewer than 100 quality samples;
- no confidence interval;
- missing provider-cache data;
- missing combined savings data;
- a paused or unknown decision state.

Attach the following evidence to the release decision:

1. JSON report.
2. Markdown report.
3. Environment/config snapshot with secrets redacted.
4. Workload distribution summary.
5. Evaluator version and quality rubric.
6. List of excluded or invalidated samples with reasons.
7. Proxy version/commit SHA.
8. Start/end timestamps and restart history.

## 11. Promote a successful arm

Promote only one arm at a time so its incremental impact remains attributable.

### 11.1 Promote from 10% to 25%

```bash
curl --fail --silent --show-error \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  --data '{"arm":"model_routing","percent":25}' \
  "$CUTCTX_URL/savings-canary/promote" | jq .
```

Replace `model_routing` with the actual winning arm. Verify the returned allocations and
control percentage before continuing.

Collect a new full evaluation window at 25%. Do not reuse the 10% window as the sole evidence
for the next promotion.

### 11.2 Promote from 25% to 50%

After the 25% window independently passes all criteria:

```bash
curl --fail --silent --show-error \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  --data '{"arm":"model_routing","percent":50}' \
  "$CUTCTX_URL/savings-canary/promote" | jq .
```

Again collect a new evaluation window and publish a new report.

Do not promote multiple arms to 50% simultaneously. Their allocations may exceed 100%, and
overlapping behavior would make attribution ambiguous.

## 12. Rollback and emergency stop

Disable the experiment immediately if there is customer-visible degradation, corrupted
metrics, identity instability, or unexplained cache loss.

The fastest stop is to restart with:

```bash
export CUTCTX_SAVINGS_CANARY_ENABLED=0
```

Also disable the orchestrator if routing is implicated:

```bash
curl --fail --silent --show-error \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  --data '{"orchestrator":false}' \
  "$CUTCTX_URL/config/flags" | jq .
```

Preserve the state file and final report snapshot before restart. Never delete failed-canary
evidence. Mark the affected window invalid and document:

- triggering metric;
- affected arm;
- first and last affected timestamps;
- request IDs used for diagnosis;
- rollback time;
- root cause;
- corrective action;
- whether a new experiment ID/salt is required.

## 13. Troubleshooting

### Report says `enabled: false`

1. Confirm `CUTCTX_SAVINGS_CANARY_ENABLED=1` is set in the proxy process, not only the shell
   running curl.
2. Restart the proxy after changing environment variables.
3. Confirm the deployed binary contains the canary implementation.

### All requests remain in control

1. Confirm traffic is classified as client `codex` or uses a `gpt-5*` requested model.
2. Inspect traces for `canary.eligible`.
3. Confirm treatment allocations are nonzero.
4. Confirm arms have not been paused.
5. Check that the stable identity is not accidentally identical for all traffic.

### Model-routing arm records no routing savings

1. Confirm `CUTCTX_MODEL_ROUTING_PRESET=codex-gpt54mini-high`.
2. Confirm the orchestrator flag is enabled.
3. Confirm tasks classified as complex correctly remain on the requested model.
4. Inspect routing reasons in request traces.
5. Confirm requested and target model pricing is available.

### Tool/API arm records zero savings

1. Confirm requests contain tool definitions.
2. Confirm schemas contain compressible descriptions or metadata.
3. Confirm tool-history references force required tools to remain present.
4. Inspect `transforms_applied` and the opportunity funnel.

### Mutable-tail arm records zero savings

1. Confirm tasks are multi-turn or contain sufficiently large tool results.
2. Confirm stable prefixes are protected and mutable tool-result content is eligible.
3. Inspect decline reasons for `below_threshold`, `cache_protection`, or
   `no_eligible_content`.

### Quality sample count is lower than request count

This is expected when one logical task creates multiple requests. Compare quality samples to
completed tasks, not request count. Investigate only when completed tasks lack feedback.

### Metrics disappear after restart

Verify `CUTCTX_SAVINGS_CANARY_PATH` points to durable writable storage and that the service
user owns both the JSON file and its lock file. Inspect the directory for a `.quarantine`
file, which indicates corrupt or unsupported state was isolated. Do not merge pre-restart
and post-restart reports manually unless they share the same experiment identity, salt
fingerprint, schema, allocation window, and deduplicated feedback ledger.

## 14. Final completion checklist

The live canary program is complete only when every checked item below is true.

- [x] Canary state persists across restart.
- [x] Salt mismatch protection is tested.
- [x] Codex assignments are session-sticky.
- [x] Non-sticky requests are visible and excluded from promotion decisions.
- [x] Quality feedback is automatic and idempotent.
- [ ] A clean release build is deployed to staging.
- [ ] Dashboard and API report schema v6 attribution.
- [ ] Orchestrator and routing preset are verified.
- [ ] At least 1,000 representative eligible requests have been collected, or every arm has
      independently reached its required sample count.
- [ ] Every evaluated task reconciles to one quality outcome or a documented evaluator failure.
- [ ] Source totals reconcile with headline totals to the token and within $0.01.
- [ ] Provider-cache value is present for control and treatments.
- [ ] 95% confidence intervals are present.
- [ ] Winning arm shows at least 20% created-savings lift.
- [ ] Quality regression is no more than 1%.
- [ ] Provider-cache regression is no more than 1%.
- [ ] Combined savings do not decline.
- [ ] No promoted arm is paused.
- [ ] The 10% report is published and reviewed.
- [ ] The 25% window independently passes before 50% promotion.
- [ ] The 50% window independently passes before default-on consideration.
- [ ] Rollback has been rehearsed.
- [ ] Final evidence includes commit SHA, config, workload mix, evaluator version, exclusions,
      and restart history.
