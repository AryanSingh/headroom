export const capabilityGroups = [
  {
    title: 'Core Deployment Modes',
    description: 'The main ways Cutctx shows up in a user workflow.',
    items: [
      { name: 'Proxy', detail: 'Drop-in OpenAI and Anthropic compatible proxy with live savings and observability.' },
      { name: 'Agent Wrap', detail: 'Wrap Codex, Claude, Copilot, OpenCode, and other agent shells without code changes.' },
      { name: 'Inline Libraries', detail: 'Python, TypeScript, and Go SDKs for direct compression inside apps.' },
      { name: 'MCP Server', detail: 'Expose compress, retrieve, and status tools to MCP clients.' },
    ],
  },
  {
    title: 'Compression & Optimization',
    description: 'The data-reduction layers that drive token savings.',
    items: [
      { name: 'SmartCrusher', detail: 'Structured JSON and repetitive tool output compression.' },
      { name: 'CodeCompressor', detail: 'AST-aware source code reduction across Python, JS, Go, Rust, Java, and C++.' },
      { name: 'Log & Diff Compression', detail: 'Structural log pattern analysis, semantic diff compression, and multi-format optimization across 40+ log and diff formats.' },
      { name: 'Schema Compaction', detail: 'Tool schema metadata stripping for OpenAI / Codex tool-heavy payloads.' },
      { name: 'Image Optimization & Audio Pass-through', detail: 'Inline base64 images are compressed; audio routes are proxied unchanged for fidelity.' },
      { name: 'Cache Alignment', detail: 'Prefix stabilization to improve provider prompt-cache hit rates.' },
    ],
  },
  {
    title: 'State, Retrieval, and Memory',
    description: 'Features that make compression reversible and persistent.',
    items: [
      { name: 'CCR Retrieval', detail: 'Compress-cache-retrieve markers with reversible expansion paths.' },
      { name: 'Cross-Agent Memory', detail: 'Shared memory backend across Claude, Codex, Gemini, and other agents.' },
      { name: 'Cutctx Learn', detail: 'Session mining and correction writing into AGENTS.md / CLAUDE.md.' },
      { name: 'Context Tools', detail: 'RTK and related context helpers surfaced alongside proxy activity.' },
    ],
  },
  {
    title: 'Governance & Operations',
    description: 'Controls, security, and reporting surfaces operators care about.',
    items: [
      { name: 'Firewall', detail: 'Prompt injection, jailbreak, PII, and data-exfil detection. Enable via CUTCTX_FIREWALL=1.' },
      { name: 'Rate Limiting', detail: 'Per-key token and request throttling. Active keys tracked live on the Governance page.' },
      { name: 'Audit & Telemetry', detail: 'Tamper-evident audit log with action counts, recent events, and hash-chain verification.' },
      { name: 'RBAC', detail: 'Role-based access control with admin, operator, and viewer tiers. Assignable per user ID.' },
      { name: 'Retention Controls', detail: 'Data lifecycle management and automated retention cleanup with configurable windows.' },
      { name: 'Observability', detail: 'Pipeline timing, waste signals, Codex websocket metrics, and display-session history.' },
    ],
  },
  {
    title: 'Intelligence Layer',
    description: 'Advanced compression intelligence modules. Each is independently toggleable via environment variable.',
    items: [
      { name: 'Task-aware compression', detail: 'Modulates compression depth by relevance to the active task. Critical context is protected; background material is aggressively reduced. Enable: CUTCTX_TASK_AWARE_ENABLED=1' },
      { name: 'Semantic deduplication', detail: 'Detects and collapses repeated content across messages using reversible CCR pointers. Enable: CUTCTX_DEDUP_ENABLED=1' },
      { name: 'Context budget controller', detail: 'Progressively increases compression as the context window fills — prevents silent truncation and cost spikes. Enable: CUTCTX_CONTEXT_BUDGET_ENABLED=1' },
      { name: 'Compression profiles', detail: 'Learns per-workspace compression patterns across sessions for improved accuracy over time. Enable: CUTCTX_PROFILES_ENABLED=1' },
    ],
  },
  {
    title: 'Provider & Protocol Coverage',
    description: 'APIs and transport formats the proxy speaks natively.',
    items: [
      { name: 'OpenAI-compatible API', detail: 'Full /v1/chat/completions compatibility — drop-in for any OpenAI client.' },
      { name: 'Anthropic Messages API', detail: 'Native /v1/messages support for Claude clients with content-block handling.' },
      { name: 'Responses API / Codex', detail: 'WebSocket streaming aliases for OpenAI Codex and Responses API traffic.' },
      { name: 'Google Gemini', detail: 'Gemini model routing with automatic token budget translation.' },
      { name: 'Streaming (SSE)', detail: 'Server-Sent Events passthrough with in-flight compression and PII redaction.' },
      { name: 'Structured Output', detail: 'JSON schema validation and retry loop for reliable structured completions.' },
    ],
  },
];
