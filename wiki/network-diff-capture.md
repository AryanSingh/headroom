# Differential Network Capture

Cutctx includes a containerized harness for comparing Claude Code traffic sent
directly to Anthropic with traffic sent through a Cutctx proxy. The harness
uses mitmproxy in two isolated lanes, writes sanitized JSONL captures, and then
generates Markdown/JSON reports with request route, header, body size, body hash,
and JSON payload differences.

## Run The Harness

```bash
cd docker/differential-network-capture
mkdir -p captures
export ANTHROPIC_API_KEY=...
export CLAUDE_PROMPT="Summarize this repository in one sentence."
docker compose up --build mitm-direct mitm-cutctx-upstream cutctx-proxy mitm-cutctx-client
docker compose --profile run run --rm claude-direct
docker compose --profile run run --rm claude-cutctx
```

The primary captures are written to:

- `docker/differential-network-capture/captures/direct.jsonl`
- `docker/differential-network-capture/captures/cutctx-client.jsonl`

The Cutctx lane also writes
`docker/differential-network-capture/captures/cutctx-upstream.jsonl`, which is
the request Cutctx forwards to Anthropic after proxy processing.

By default only `api.anthropic.com` is logged. Override
`CAPTURE_INCLUDE_HOSTS` with a comma-separated list to include other hosts.

## Generate A Report

```bash
cutctx capture network-diff \
  --direct docker/differential-network-capture/captures/direct.jsonl \
  --cutctx docker/differential-network-capture/captures/cutctx-client.jsonl \
  --output docker/differential-network-capture/captures/report.md \
  --json-output docker/differential-network-capture/captures/report.json
```

The report redacts sensitive header values and sensitive query values before
comparison. Request bodies are captured so structural payload differences can be
identified; keep the generated `captures/` directory out of commits because it
may contain prompts, tool outputs, and repository context.

For Claude Code deferred-tool investigations, the paired exchange table includes
top-level Anthropic `tools` counts and serialized tool bytes. A jump from
`tools=0->N` in the Cutctx client lane is evidence that Claude Code eagerly
materialized tool schemas before the request reached Cutctx.

## Custom Claude Invocation

Set `CLAUDE_COMMAND` to run the exact command under test in both lanes:

```bash
CLAUDE_COMMAND='claude -p "read README.md and summarize the proxy setup"' \
  docker compose --profile run run --rm claude-direct
CLAUDE_COMMAND='claude -p "read README.md and summarize the proxy setup"' \
  docker compose --profile run run --rm claude-cutctx
```

Use `CLAUDE_DIRECT_ARGS` and `CLAUDE_CUTCTX_ARGS` when each lane needs
different flags.
