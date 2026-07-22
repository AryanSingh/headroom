# Pilot Known Limitations

The pilot commitment covers OpenAI and Anthropic through Codex, Claude Code,
Claude Desktop MCP, and compatible SDKs on macOS and Linux.

- Claude Desktop hosted model calls cannot use a custom provider base URL.
  Cutctx supports Claude Desktop through MCP tools and the MCP tool-output
  gateway.
- Windows installation is outside the pilot support commitment.
- Providers other than OpenAI and Anthropic remain available without pilot
  certification.
- Cutctx does not operate a hosted service for this pilot. The customer owns
  Docker or Kubernetes operations, secrets, TLS termination, backup, and
  recovery.
- Live model routing requires capability, transport, account, policy, and price
  evidence. Uncertainty keeps the requested model.
- Large or unsupported payloads may use safe pass-through instead of
  compression.
- Self-serve payment, SOC 2 procurement, formal enterprise SLA, and round-the-
  clock support remain outside this assisted engagement.
- The customer and release owner must complete legal, payment, support-owner,
  change-window, live-provider, and restore-drill sign-offs before paid access.
