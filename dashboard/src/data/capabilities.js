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
      { name: 'Log & Diff Compression', detail: 'LogCompressor, Drain3, Difftastic, and structural diff paths.' },
      { name: 'Schema Compaction', detail: 'Tool schema metadata stripping for OpenAI / Codex tool-heavy payloads.' },
      { name: 'Image & Audio Optimization', detail: 'Multimodal input shrinking for inline base64 images and audio.' },
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
      { name: 'Firewall', detail: 'Prompt injection, jailbreak, and PII-aware request interception.' },
      { name: 'Rate Limiting', detail: 'Request and token-based throttling with active-key tracking.' },
      { name: 'Audit & Telemetry', detail: 'Savings attribution, recent requests, audit events, and TOIN pattern tracking.' },
      { name: 'Observability', detail: 'Pipeline timing, waste signals, Codex websocket metrics, and display-session history.' },
    ],
  },
];
