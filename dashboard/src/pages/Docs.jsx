import { BookOpen, ChevronRight, Cpu, Globe, Key, Package, Settings, Shield, Terminal, Zap } from 'lucide-react';
import { useState } from 'react';

const SECTIONS = [
  { id: 'quickstart', label: 'Quick Start', icon: Zap },
  { id: 'cli', label: 'CLI Reference', icon: Terminal },
  { id: 'env', label: 'Env Variables', icon: Settings },
  { id: 'agents', label: 'Agent Compatibility', icon: Cpu },
  { id: 'algorithms', label: 'Algorithms', icon: Package },
  { id: 'integrations', label: 'Integrations', icon: Globe },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'api', label: 'Admin API', icon: Key },
];

function Code({ children }) {
  return (
    <pre className="code-panel" style={{ fontSize: '0.78rem', lineHeight: 1.7, whiteSpace: 'pre', overflowX: 'auto' }}>
      {children}
    </pre>
  );
}

function Section({ id, title, children }) {
  return (
    <section id={id} className="panel" style={{ scrollMarginTop: '2rem' }}>
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function Table({ headers, rows }) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{typeof cell === 'string' && cell.startsWith('`') ? <code>{cell.slice(1, -1)}</code> : cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Tag({ children, color }) {
  const colors = {
    green: { color: 'var(--green)', background: 'rgba(5,150,105,0.1)', border: 'rgba(5,150,105,0.2)' },
    amber: { color: 'var(--amber)', background: 'rgba(217,119,6,0.1)', border: 'rgba(217,119,6,0.2)' },
    red: { color: 'var(--red)', background: 'rgba(220,38,38,0.1)', border: 'rgba(220,38,38,0.2)' },
    blue: { color: 'var(--accent)', background: 'rgba(96,165,250,0.1)', border: 'rgba(96,165,250,0.2)' },
  };
  const s = colors[color] || colors.blue;
  return (
    <span style={{ ...s, borderRadius: 4, border: `1px solid ${s.border}`, padding: '1px 6px', fontSize: '0.72rem', fontWeight: 600, whiteSpace: 'nowrap' }}>
      {children}
    </span>
  );
}

export default function Docs() {
  const [active, setActive] = useState('quickstart');

  return (
    <section className="page-stack" style={{ flexDirection: 'row', gap: '1.5rem', alignItems: 'flex-start' }}>

      {/* Sticky sidebar TOC */}
      <aside style={{ width: 180, flexShrink: 0, position: 'sticky', top: '1rem' }}>
        <div className="panel" style={{ padding: '0.75rem 0' }}>
          <div className="sidebar-label" style={{ padding: '0 1rem', marginBottom: '0.25rem' }}>Contents</div>
          <nav>
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <a
                key={id}
                href={`#${id}`}
                onClick={() => setActive(id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.4rem 1rem',
                  fontSize: '0.8rem',
                  fontWeight: active === id ? 600 : 400,
                  color: active === id ? 'var(--accent)' : 'var(--text-secondary)',
                  textDecoration: 'none',
                  borderLeft: active === id ? '2px solid var(--accent)' : '2px solid transparent',
                  transition: 'all 0.1s',
                }}
              >
                <Icon size={13} />
                {label}
              </a>
            ))}
          </nav>
        </div>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

        <div className="panel" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.25rem' }}>
          <BookOpen size={20} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '0.1rem' }}>Documentation</div>
            <div style={{ fontSize: '1rem', fontWeight: 600 }}>Cutctx — CLI, API, and configuration reference</div>
          </div>
        </div>

        {/* Quick Start */}
        <Section id="quickstart" title="Quick Start">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Three ways to use Cutctx — proxy, wrap, or inline library. Pick the one that matches your workflow.
          </p>
          <Code>{`# Install (Python)
pip install "cutctx-ai[all]"          # full install — all algorithms
pip install "cutctx-ai[proxy,ml]"     # proxy + Kompress-base only

# Install (Node / TypeScript)
npm install cutctx-ai

# Mode 1 — Proxy (zero code changes)
cutctx proxy --port 8787
# Then point your agent/client at http://localhost:8787

# Mode 2 — Wrap a coding agent
cutctx wrap claude                    # Claude Code
cutctx wrap codex                     # OpenAI Codex
cutctx wrap cursor                    # Cursor
cutctx wrap aider                     # Aider
cutctx wrap copilot                   # GitHub Copilot CLI

# Mode 3 — Inline Python library
from cutctx import compress
result = await compress(messages, model="claude-sonnet-4-6")

# Check savings
cutctx perf
cutctx savings --by-source --format json`}
          </Code>
        </Section>

        {/* CLI Reference */}
        <Section id="cli" title="CLI Reference">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            All top-level commands. Run <code>cutctx &lt;command&gt; --help</code> for full flag lists.
          </p>
          <Table
            headers={['Command', 'Description']}
            rows={[
              ['`cutctx proxy`', 'Start the drop-in proxy server (default port 8787)'],
              ['`cutctx proxy --port <n>`', 'Start proxy on a custom port'],
              ['`cutctx proxy --backend anthropic`', 'Route to Anthropic (also: openai, bedrock, gemini, anyllm)'],
              ['`cutctx proxy --mode token`', 'Compression mode: token (default), cost, accuracy, off'],
              ['`cutctx proxy --admin-key <key>`', 'Set admin API key (or use CUTCTX_ADMIN_API_KEY)'],
              ['`cutctx wrap <agent>`', 'Wrap a coding agent: claude, codex, cursor, aider, copilot, opencode'],
              ['`cutctx wrap <agent> --memory`', 'Enable cross-agent memory injection'],
              ['`cutctx wrap <agent> --code-graph`', 'Enable code-graph context (Claude Code)'],
              ['`cutctx wrap copilot --subscription`', 'Route Copilot CLI subscription traffic through the proxy'],
              ['`cutctx perf`', 'Show token savings metrics for the current session'],
              ['`cutctx savings --by-source`', 'Break down savings by attribution source (cache, compression, routing…)'],
              ['`cutctx report buyer --format json`', 'Generate a machine-readable buyer savings report'],
              ['`cutctx capabilities`', 'List all compression algorithms, formats, and config options'],
              ['`cutctx learn`', 'Analyze failed sessions and write corrections to CLAUDE.md / AGENTS.md'],
              ['`cutctx mcp install`', 'Install MCP tools (cutctx_compress, cutctx_retrieve, cutctx_status)'],
              ['`cutctx integrations status`', 'Show which parsers and integrations are wired'],
            ]}
          />

          <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <strong>Accuracy guard</strong> — <code>--accuracy-guard strict</code> (default in agent profiles) verifies that
            compressed output preserves identifiers and references.
            Use <code>--accuracy-guard balanced</code> or <code>off</code> to relax.
          </div>
        </Section>

        {/* Environment Variables */}
        <Section id="env" title="Environment Variables">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            All configuration can be set via env vars. CLI flags take precedence over env vars.
          </p>

          <div style={{ fontWeight: 600, fontSize: '0.78rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Core proxy
          </div>
          <Table
            headers={['Variable', 'Default', 'Description']}
            rows={[
              ['`CUTCTX_HOST`', '127.0.0.1', 'Bind address for the proxy server'],
              ['`CUTCTX_PORT`', '8787', 'Port the proxy listens on'],
              ['`CUTCTX_BACKEND`', 'anthropic', 'Upstream provider: anthropic, openai, bedrock, gemini, anyllm'],
              ['`CUTCTX_MODE`', 'token', 'Compression mode: token, cost, accuracy, off'],
              ['`CUTCTX_ADMIN_API_KEY`', '(auto-generated)', 'Admin API key — set to a fixed value for stable deployments'],
              ['`CUTCTX_LICENSE_KEY`', '—', 'Enterprise license key'],
              ['`CUTCTX_ENTITLEMENT_TIER`', 'self-hosted', 'Override entitlement tier: builder, team, business, enterprise'],
            ]}
          />

          <div style={{ fontWeight: 600, fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: '1rem 0 0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Compression & algorithms
          </div>
          <Table
            headers={['Variable', 'Default', 'Description']}
            rows={[
              ['`CUTCTX_DISABLE_KOMPRESS`', 'false', 'Disable the Kompress-base ML model (use rule-based only)'],
              ['`CUTCTX_USE_LLMLINGUA`', 'false', 'Enable LLMLingua for additional text compression'],
              ['`CUTCTX_ACCURACY_GUARD`', 'strict', 'Accuracy guard level: strict, balanced, off'],
              ['`CUTCTX_CODE_AWARE_ENABLED`', 'false', 'Enable AST-aware code compressor'],
              ['`CUTCTX_EMBEDDER_RUNTIME`', '—', 'pytorch_mps for Apple GPU memory embedder offload'],
              ['`CUTCTX_CCR_BACKEND`', 'local', 'CCR storage backend: local, redis, s3'],
              ['`CUTCTX_CONTEXT_BUDGET_POLICY`', '—', 'Override context budgeting policy'],
              ['`CUTCTX_EXCLUDE_TOOLS`', '—', 'Comma-separated tool names to skip from schema compression'],
            ]}
          />

          <div style={{ fontWeight: 600, fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: '1rem 0 0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Security & governance
          </div>
          <Table
            headers={['Variable', 'Default', 'Description']}
            rows={[
              ['`CUTCTX_FIREWALL_ENABLED`', 'false', 'Enable the LLM firewall (injection, jailbreak, PII detection)'],
              ['`CUTCTX_FIREWALL_OPT_OUT_WARNING`', '—', 'Set to 1 to suppress the firewall-not-enabled warning'],
              ['`CUTCTX_RBAC_DB_PATH`', '~/.cutctx/rbac.db', 'Path to the RBAC SQLite database'],
              ['`CUTCTX_AUDIT_DB_PATH`', '—', 'Path to the audit log database'],
              ['`CUTCTX_CORS_ORIGINS`', '—', 'Allowed CORS origins (comma-separated)'],
              ['`CUTCTX_SKIP_UPSTREAM_CHECK`', '—', 'Set to 1 to skip upstream connectivity check on startup'],
            ]}
          />

          <div style={{ fontWeight: 600, fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: '1rem 0 0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            SSO / Identity
          </div>
          <Table
            headers={['Variable', 'Description']}
            rows={[
              ['`CUTCTX_SSO_PROVIDER_TYPE`', 'SSO provider: oidc, saml, oauth2'],
              ['`CUTCTX_SSO_DISCOVERY_URL`', 'OIDC discovery endpoint (.well-known/openid-configuration)'],
              ['`CUTCTX_SSO_JWKS_URI`', 'JWKS endpoint for JWT public key verification'],
              ['`CUTCTX_SSO_ISSUER`', 'Expected JWT issuer claim'],
              ['`CUTCTX_SSO_AUDIENCE`', 'Expected JWT audience claim'],
              ['`CUTCTX_SSO_INTROSPECTION_URL`', 'RFC 7662 token introspection endpoint'],
              ['`CUTCTX_SSO_DEFAULT_ROLE`', 'Default RBAC role for SSO-authenticated users'],
              ['`CUTCTX_SSO_ROLE_MAPPING`', 'JSON map of SSO groups → RBAC roles'],
            ]}
          />
        </Section>

        {/* Agent Compatibility */}
        <Section id="agents" title="Agent Compatibility">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Cutctx wraps or proxies these agents with zero code changes.
          </p>
          <Table
            headers={['Agent', 'cutctx wrap', 'Notes']}
            rows={[
              ['Claude Code', <Tag color="green">✓ wrap</Tag>, 'Supports --memory and --code-graph flags'],
              ['OpenAI Codex', <Tag color="green">✓ wrap</Tag>, 'Shares memory store with Claude Code'],
              ['Cursor', <Tag color="green">✓ wrap</Tag>, 'Prints config — paste once into Cursor settings'],
              ['Aider', <Tag color="green">✓ wrap</Tag>, 'Starts proxy and launches Aider automatically'],
              ['GitHub Copilot CLI', <Tag color="green">✓ wrap</Tag>, 'Use --subscription for subscription traffic routing'],
              ['OpenCode', <Tag color="green">✓ wrap</Tag>, 'Installed as a ContextEngine plugin'],
              ['Windsurf / Zed', <Tag color="amber">via proxy</Tag>, 'Point base URL at the running proxy'],
              ['Any OpenAI client', <Tag color="green">✓ proxy</Tag>, 'Full /v1/chat/completions compatibility'],
              ['Any Anthropic client', <Tag color="green">✓ proxy</Tag>, 'Full /v1/messages compatibility'],
              ['LangChain', <Tag color="green">✓ library</Tag>, 'Cutctx LangChain chat wrapper'],
              ['Agno', <Tag color="green">✓ library</Tag>, 'Cutctx Agno model wrapper'],
              ['Vercel AI SDK', <Tag color="green">✓ library</Tag>, 'wrapLanguageModel with cutctxMiddleware()'],
              ['LiteLLM', <Tag color="green">✓ callback</Tag>, 'Cutctx callback integration for LiteLLM'],
              ['MCP clients', <Tag color="green">✓ mcp</Tag>, 'cutctx_compress, cutctx_retrieve, cutctx_status tools'],
            ]}
          />
        </Section>

        {/* Algorithms */}
        <Section id="algorithms" title="Compression Algorithms">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            The ContentRouter selects the best algorithm per content type. All algorithms are reversible via CCR.
          </p>
          <Table
            headers={['Algorithm', 'Best for', 'Typical savings']}
            rows={[
              ['SmartCrusher', 'JSON arrays, nested objects, repeated tool outputs', '40–70%'],
              ['CodeCompressor', 'Python, JS, Go, Rust, Java, C++ source — AST-aware', '30–60%'],
              ['Kompress-base', 'General prose, agentic traces — HuggingFace model', '20–50%'],
              ['LogCompressor', 'Structured logs, stack traces — Aho-Corasick patterns', '50–85%'],
              ['DiffCompressor', 'Git diffs, patch output — SIMD line splitting', '40–75%'],
              ['SearchCompressor', 'Search results — relevance scoring + BM25 ranking', '35–65%'],
              ['SchemaCompressor', 'OpenAI tool definitions — 32 metadata keys stripped', '~40%'],
              ['ImageCompressor', 'Inline base64 images — JPEG quality routing + format convert', '40–90%'],
              ['AudioCompressor', 'Inline base64 WAV/MP3/AAC — downsampling', '30–70%'],
              ['CacheAligner', 'All content — prefix stabilization for provider KV cache', 'Indirect'],
            ]}
          />

          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>Pipeline lifecycle</div>
            <Code>{`Setup → Pre-Start → Post-Start → Input Received → Input Cached
→ Input Routed → Input Compressed → Input Remembered
→ Pre-Send → Post-Send → Response Received`}
            </Code>
          </div>
        </Section>

        {/* Integrations */}
        <Section id="integrations" title="Integrations">
          <Table
            headers={['Your stack', 'How to integrate']}
            rows={[
              ['Python app', 'from cutctx import compress — await compress(messages, model=…)'],
              ['TypeScript / Node', 'import { compress } from "cutctx-ai" — await compress(messages, { model })'],
              ['Anthropic SDK', 'Use Cutctx client wrapper for existing Anthropic SDK clients'],
              ['OpenAI SDK', 'Set base_url="http://localhost:8787/v1" — no other changes needed'],
              ['Vercel AI SDK', 'wrapLanguageModel({ model, middleware: cutctxMiddleware() })'],
              ['LiteLLM', 'Register Cutctx as a LiteLLM callback integration'],
              ['LangChain', 'Use Cutctx LangChain chat model wrapper'],
              ['Agno', 'Use Cutctx Agno model wrapper'],
              ['Strands', 'See cutctx.dev/docs/strands'],
              ['ASGI apps', 'app.add_middleware(CompressionMiddleware)'],
              ['Multi-agent', 'SharedContext().put(key, value) / .get(key) — cross-agent KV store'],
              ['MCP clients', 'cutctx mcp install — adds compress, retrieve, status tools'],
            ]}
          />

          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>Install extras</div>
            <Code>{`pip install "cutctx-ai[proxy]"       # proxy server only
pip install "cutctx-ai[ml]"          # Kompress-base ML model
pip install "cutctx-ai[code]"        # AST-aware code compressor
pip install "cutctx-ai[memory]"      # cross-agent memory
pip install "cutctx-ai[image]"       # image compression
pip install "cutctx-ai[mcp]"         # MCP server tools
pip install "cutctx-ai[langchain]"   # LangChain wrapper
pip install "cutctx-ai[agno]"        # Agno wrapper
pip install "cutctx-ai[evals]"       # evaluation suite
pip install "cutctx-ai[pytorch-mps]" # Apple GPU embedder offload`}
            </Code>
          </div>
        </Section>

        {/* Security */}
        <Section id="security" title="Security & Governance">
          <Table
            headers={['Feature', 'Notes']}
            rows={[
              ['LLM Firewall', '27 regex patterns — injection, PII, jailbreak, data-exfil. Enable: CUTCTX_FIREWALL_ENABLED=1'],
              ['Structured output', 'JSON schema validation with 3× auto-retry on invalid responses'],
              ['Multi-model ensemble', 'asyncio.gather fan-out; evaluator model picks the best response'],
              ['Budget cut-offs', 'Token and cost hard limits with SSE streaming truncation'],
              ['SSO / OAuth2', 'JWT/JWKS, OIDC discovery, RFC 7662 introspection, timing-safe claim validation'],
              ['RBAC', 'Viewer / Operator / Admin roles, 15+ permissions, enforced on all admin endpoints'],
              ['Audit logging', 'SQLite WAL-backed events, queryable with filters, JSONL export, hash-chain verify'],
              ['Entitlements', '59-feature × 4-tier matrix (Builder / Team / Business / Enterprise)'],
              ['Data residency', 'Region pinning and egress blocklist via the residency proof route'],
              ['Air-gap deployment', 'Fully offline mode — no outbound calls, local-only models'],
            ]}
          />
        </Section>

        {/* Admin API */}
        <Section id="api" title="Admin API">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            All admin endpoints require the <code>x-cutctx-admin-key</code> header. Set
            the key with <code>CUTCTX_ADMIN_API_KEY</code> or read the auto-generated
            key from proxy startup logs.
          </p>
          <Table
            headers={['Endpoint', 'Description']}
            rows={[
              ['GET /stats', 'Full token savings and pipeline statistics'],
              ['GET /stats-history', 'Historical savings time-series'],
              ['GET /transformations/feed', 'Recent request transformation feed'],
              ['GET /audit/stats', 'Audit event counts and recent activity'],
              ['GET /audit/events', 'Query audit log (action, actor, since, until, limit)'],
              ['GET /audit/verify', 'Integrity check — lightweight + hash-chain'],
              ['GET /orgs', 'List organizations (requires workspace_model entitlement)'],
              ['GET /rbac/roles', 'List RBAC role assignments'],
              ['POST /rbac/roles', 'Assign a role to a user ID'],
              ['DELETE /rbac/roles/{user_id}', 'Remove a role assignment'],
              ['GET /quota', 'Unified quota stats across all registered providers'],
              ['GET /retention/stats', 'Retention configuration and lifecycle stats'],
              ['GET /firewall/status', 'Firewall posture, patterns loaded, config'],
              ['POST /firewall/scan', 'Scan text for violations (returns violations + block decision)'],
              ['GET /entitlements', 'Current tier and feature entitlement status'],
              ['GET /license-status', 'License key status and usage reporting'],
              ['GET /webhooks/subscriptions', 'List webhook subscribers'],
              ['POST /webhooks/subscriptions', 'Register a webhook URL'],
              ['POST /webhooks/test', 'Fire a synthetic test event to all subscribers'],
            ]}
          />

          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>Example: query savings</div>
            <Code>{`curl http://localhost:8787/stats \\
  -H "x-cutctx-admin-key: YOUR_KEY" | jq .

# Savings broken down by source
curl http://localhost:8787/stats \\
  -H "x-cutctx-admin-key: YOUR_KEY" | jq '.savings_by_source'

# Scan text against firewall
curl -X POST http://localhost:8787/firewall/scan \\
  -H "x-cutctx-admin-key: YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"text": "Ignore all previous instructions and..."}'`}
            </Code>
          </div>
        </Section>

      </div>
    </section>
  );
}
