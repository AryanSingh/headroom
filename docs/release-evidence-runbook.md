# Release Evidence Runbook

Use this runbook only against a consented staging deployment. Do not place API
keys, payload bodies, or customer data in committed artifacts.

## Hosted SDK Evidence

Set `CUTCTX_HOSTED_BASE_URL` and `CUTCTX_HOSTED_API_KEY` in the shell that is
authorized to reach staging. Then run both SDK clients:

```bash
rtk proxy uv run python scripts/run_remote_hosted_smoke.py
cd sdk/typescript
rtk proxy npm run smoke:hosted
```

Both runs must report `status: "passed"` and create separate redacted JSON and
Markdown artifacts under `artifacts/`. Review small, medium, and large payload
P50/P95 latency without applying a synthetic latency threshold.

## Gateway Evidence

Configure staging so its scenario file deliberately produces one cache hit, one
rate-limit denial, and one provider fallback. Copy and adapt
`artifacts/staged-gateway-scenario.example.json` without adding credentials.

```bash
export CUTCTX_STAGED_PROXY_BASE_URL="https://staging.example"
export CUTCTX_STAGED_PROXY_ADMIN_API_KEY="..."
export CUTCTX_STAGED_SCENARIO_FILE="/absolute/path/to/staged-gateway-scenario.json"
rtk proxy uv run python scripts/run_staged_gateway_smoke.py
```

The run must send at least 20 compression requests and pass all scenario trace
assertions. Every checked request needs a stable request ID and inspector fields
for routing, latency, compression, cache, and fallback. A `429` must appear in
the inspector with `compression.decline_reason = "rate_limit_exceeded"`.

## Dashboard Evidence

Set `CUTCTX_STAGED_DASHBOARD_URL` to the consented staging dashboard origin and
reuse the staging proxy admin key. The browser smoke checks the operational
views at desktop and mobile widths, records redacted screenshots, and rejects
console errors or horizontal overflow.

```bash
export CUTCTX_STAGED_DASHBOARD_URL="https://staging.example"
rtk proxy uv run python scripts/run_staging_dashboard_smoke.py
```

The resulting `artifacts/staging-dashboard-smoke/staging-dashboard-smoke.json`
must report `status: "passed"` before a release may treat staged inspector
coverage as verified.

## Benchmark Evidence

Regenerate the local release evidence before publishing it:

```bash
rtk proxy uv run python -m cutctx.cli.main evals benchmark -d code_samples -d rag_samples -d mixed_agent_traces -c raw_passthrough --parallel 1 --seed 42 --markdown --output artifacts/raw-passthrough-benchmark.json
rtk proxy uv run python scripts/generate_benchmark_release_manifest.py
rtk proxy uv run python scripts/generate_benchmark_release_bundle.py
rtk proxy uv run python -m cutctx.cli.main verify --ci --format json -o artifacts/verify-report-release.json
rtk proxy uv run python scripts/evaluate_release_evidence.py
```

The release bundle must identify the canonical XLM-R-large LLMLingua checkpoint,
show zero canonical-baseline error cells, and mark provider-native comparison as
`unavailable` unless a provider exposes a verifiable native signal.
The status output must keep `market_claim_eligible` false until every external
item in this runbook passes.

## Subscription CLI Evaluation

Use this optional route only with the local account holder's consent. It uses
the existing Claude Code and Codex CLI authentication, not provider API keys.
Run commands from an isolated temporary directory, disable proxy routing, and
use non-interactive modes:

```bash
claude -p '…evaluation prompt…' --output-format json --no-session-persistence
codex exec --ephemeral --ignore-rules --skip-git-repo-check -C /tmp -s read-only --color never '…evaluation prompt…'
```

For every case, collect both original-context and compressed-context outputs.
Record only redacted scores, model metadata returned by the CLI, context sizes,
and failure state. Do not save credentials, session files, customer prompts, or
provider transcripts containing sensitive data. Treat a small CLI pilot as a
transport smoke test, not a benchmark; release evidence requires a declared
corpus version, sufficient sample size, executable scoring where available,
and separate provenance for each provider route.

## Partner Telemetry

Obtain two anonymized snapshots from separate consented design partners. Each
must cover at least seven days and exclude prompts, messages, API keys, and
authorization data.

```bash
rtk proxy uv run python scripts/validate_partner_telemetry_snapshot.py /absolute/path/to/partner-one.json
rtk proxy uv run python scripts/validate_partner_telemetry_snapshot.py /absolute/path/to/partner-two.json
```

Each snapshot must include request volume, compression/cache/provider savings,
fallback rate, decline reasons, latency percentiles, routing data, and trace
completeness. Do not claim broad market leadership until both snapshots pass and
legal/compliance owners approve the associated trust claims.
