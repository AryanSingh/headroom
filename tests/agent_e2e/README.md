# Codex and Claude protocol replay

This suite replays sanitized, structurally faithful Codex and Claude requests
through a real Cutctx proxy listening on an ephemeral TCP port. A strict local
upstream rejects contract violations before returning realistic JSON, SSE, or
WebSocket events.

The PR gate is entirely hermetic. It exercises:

- OpenAI Responses JSON, SSE, and native WebSocket transports.
- ChatGPT subscription normalization, including `store: false` and
  `stream: true` on initial and continuation frames.
- Codex resume after a real proxy stop/start cycle.
- Anthropic Messages streaming and full-history resume after restart.
- Fixture schema validation, required matrix-tag coverage, secret scanning,
  deterministic ID remapping, and capture import.
- Explicit Python/native capability declarations. Unsupported combinations
  require both a reason and a tracking issue.

Run it with:

```bash
python -m pytest tests/agent_e2e
```

Raw Codex wire JSON, Claude MITM JSONL, and Claude debug records can be imported
with `cutctx.capture.agent_fixture.import_capture_file`. Set
`delete_source=True` only for a `0700` directory containing a `0600` capture;
the importer validates the sanitized result before removing the source.

The scheduled live workflow installs pinned and latest Codex/Claude CLIs,
uses isolated authentication and temporary repositories, caps the four proxy
lanes to a combined USD 5, restarts Cutctx, resumes each session, and uploads
only sanitized summaries. The separate differential workflow compares direct
Claude traffic with the Cutctx lane using body-sanitized MITM records.
