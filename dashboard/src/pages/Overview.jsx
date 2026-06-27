import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Clock3,
  Database,
  ShieldCheck,
  Sparkles,
  Waves,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  formatCurrency,
  formatDurationMs,
  formatInteger,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  titleize,
} from '../lib/format';
import { useDashboardData } from '../lib/use-dashboard-data';

const strategyLabels = {
  smart_crusher: 'SmartCrusher',
  mixed: 'Mixed router',
  log_compressor: 'LogCompressor',
  code_compressor: 'CodeCompressor',
  image: 'Image optimization',
  preserve: 'Preserve',
  noop: 'No-op',
  openai: 'OpenAI responses',
};

function buildSourceRows(stats) {
  const sourceTokens = stats?.savings_by_source?.tokens || {};
  const sourceUsd = stats?.savings_by_source?.usd || {};
  const tokens = stats?.tokens || {};
  const cost = stats?.summary?.cost || {};

  const rows = [
    {
      key: 'cutctx_compression',
      label: 'Compression',
      tokens: Number(sourceTokens.cutctx_compression || tokens.proxy_compression_saved || 0),
      usd: Number(sourceUsd.cutctx_compression || cost?.breakdown?.compression_savings_usd || 0),
    },
    {
      key: 'provider_prompt_cache',
      label: 'Provider cache',
      tokens: Number(sourceTokens.provider_prompt_cache || 0),
      usd: Number(sourceUsd.provider_prompt_cache || cost?.breakdown?.cache_savings_usd || 0),
    },
    {
      key: 'semantic_cache',
      label: 'Semantic cache',
      tokens: Number(sourceTokens.semantic_cache || 0),
      usd: Number(sourceUsd.semantic_cache || 0),
    },
    {
      key: 'prefix_cache_self_hosted',
      label: 'Prefix cache',
      tokens: Number(sourceTokens.prefix_cache_self_hosted || 0),
      usd: Number(sourceUsd.prefix_cache_self_hosted || 0),
    },
    {
      key: 'model_routing',
      label: 'Model routing',
      tokens: Number(sourceTokens.model_routing || 0),
      usd: Number(sourceUsd.model_routing || 0),
    },
  ];

  return rows;
}

function buildStrategyRows(stats) {
  const compressionCounts = stats?.compressions_by_strategy || {};
  const savedByStrategy = stats?.tokens_saved_by_strategy || {};
  const keys = Array.from(
    new Set([
      ...Object.keys(compressionCounts),
      ...Object.keys(savedByStrategy),
      'smart_crusher',
      'mixed',
      'image',
      'noop',
    ]),
  );

  return keys
    .map((key) => ({
      key,
      label: strategyLabels[key] || titleize(key),
      requests: Number(compressionCounts[key] || 0),
      saved: Number(savedByStrategy[key] || 0),
    }))
    .filter((row) => row.requests > 0 || row.saved > 0 || ['smart_crusher', 'mixed', 'image'].includes(row.key));
}

export default function Overview() {
  const { stats, health, loading, error, lastUpdated } = useDashboardData();

  const summary = stats?.summary || {};
  const requests = stats?.requests || {};
  const tokens = stats?.tokens || {};
  const codexWs = stats?.codex_ws || {};
  const rateLimiter = stats?.rate_limiter || {};
  const compressionCache = stats?.compression_cache || {};
  const contextTool = stats?.context_tool || {};
  const recentRequests = Array.isArray(stats?.recent_requests) ? stats.recent_requests.slice(0, 4) : [];

  const sourceRows = buildSourceRows(stats);
  const strategyRows = buildStrategyRows(stats);

  const topMetrics = [
    {
      label: 'Requests',
      value: formatInteger(requests.total),
      note: `${formatInteger(requests.failed)} failed, ${formatInteger(requests.cached)} cached`,
      icon: Database,
    },
    {
      label: 'Tokens saved',
      value: formatNumber(tokens.saved),
      note: `${formatPercent(tokens.savings_percent)} total reduction`,
      icon: Sparkles,
    },
    {
      label: 'USD saved',
      value: formatCurrency(summary?.cost?.total_saved_usd),
      note: `${formatCurrency(summary?.cost?.without_cutctx_usd)} without Cutctx`,
      icon: BarChart3,
    },
    {
      label: 'Proxy health',
      value: health?.status || 'unknown',
      note: `${health?.ready ? 'Ready' : 'Not ready'} • refreshed ${formatRelativeTime(lastUpdated)}`,
      icon: ShieldCheck,
    },
  ];

  const totalSourceTokens = sourceRows.reduce((sum, row) => sum + row.tokens, 0) || Number(tokens.total_before_compression || 0);

  return (
    <section className="page-stack">
      <div className="page-header-card page-header-card-rich">
        <div>
          <div className="eyebrow">Live observability</div>
          <h1>Cutctx Command Center</h1>
          <p>
            This control surface tracks compression, cache leverage, Codex websocket flows, memory, firewall
            posture, and multimodal token savings from the running proxy.
          </p>
          <div className="hero-pill-row">
            <span className="hero-pill">Mode: {summary.mode || 'token'}</span>
            <span className="hero-pill">Primary model: {summary.primary_model || '—'}</span>
            <span className="hero-pill">API requests: {formatInteger(summary.api_requests)}</span>
          </div>
        </div>

        <div className="hero-sidecard">
          <div className="hero-sidecard-label">System health</div>
          <div className="hero-sidecard-value">{health?.status || 'connecting'}</div>
          <p>{health?.ready ? 'Proxy is healthy and reporting live telemetry.' : 'Waiting for a healthy proxy.'}</p>
          <div className="hero-sidecard-meta">
            <div>Updated {formatRelativeTime(lastUpdated)}</div>
            <div>Rust core: {health?.rust_core || 'loaded'}</div>
          </div>
        </div>
      </div>

      {error && <div className="alert-card">Failed to load command center data: {error}</div>}

      <div className="metric-grid metric-grid-four">
        {topMetrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <article key={metric.label} className="metric-card">
              <div className="metric-header">
                <span className="metric-label">{metric.label}</span>
                <div className="metric-icon">
                  <Icon size={18} />
                </div>
              </div>
              <div className="metric-value">{loading ? '—' : metric.value}</div>
              <div className="metric-footnote">{metric.note}</div>
            </article>
          );
        })}
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Savings attribution</div>
              <h2>Where token savings are coming from</h2>
            </div>
            <p>Compression and cache channels are broken out separately so value stays visible.</p>
          </div>

          <div className="source-stack">
            {sourceRows.map((row) => {
              const pct = totalSourceTokens > 0 ? (row.tokens / totalSourceTokens) * 100 : 0;
              return (
                <div key={row.key} className="source-row">
                  <div className="source-labels">
                    <div className="source-name">{row.label}</div>
                    <div className="source-meta">
                      {formatInteger(row.tokens)} tokens • {formatCurrency(row.usd)}
                    </div>
                  </div>
                  <div className="source-bar-track">
                    <div className="source-bar-fill" style={{ width: `${Math.min(100, pct)}%` }} />
                  </div>
                  <div className="source-percent">{formatPercent(pct)}</div>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Live control rail</div>
              <h2>Operational status</h2>
            </div>
          </div>

          <div className="stack-list">
            <StatusTile
              icon={<Waves size={16} />}
              label="Codex websocket"
              value={`${formatInteger(codexWs.frames_attempted_total)} frames`}
              detail={`${formatInteger(codexWs.frames_failed_total)} failed • ${formatInteger(codexWs.frames_compressed_total)} compressed`}
            />
            <StatusTile
              icon={<Clock3 size={16} />}
              label="Rate limiter"
              value={`${formatInteger(rateLimiter.active_keys)} active keys`}
              detail={`${formatInteger(rateLimiter.requests_per_minute)} rpm • ${formatInteger(rateLimiter.tokens_per_minute)} tpm`}
            />
            <StatusTile
              icon={<BrainCircuit size={16} />}
              label="Context tool"
              value={titleize(contextTool.configured || 'none')}
              detail={contextTool.available ? 'Available in workspace' : 'Unavailable'}
            />
            <StatusTile
              icon={<Database size={16} />}
              label="Compression cache"
              value={titleize(compressionCache.mode || 'unknown')}
              detail={`${formatInteger(compressionCache.total_hits)} hits • ttl ${formatInteger(compressionCache.ttl_seconds)}s`}
            />
          </div>
        </aside>
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Compression mix</div>
              <h2>Strategy activity</h2>
            </div>
          </div>

          <div className="capability-grid">
            {strategyRows.map((row) => (
              <article key={row.key} className="capability-card">
                <div className="capability-name">{row.label}</div>
                <p>
                  {formatInteger(row.requests)} requests • {formatInteger(row.saved)} tokens saved
                </p>
              </article>
            ))}
          </div>
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Quick paths</div>
              <h2>Next actions</h2>
            </div>
          </div>

          <div className="stack-list">
            <QuickLink to="/playground" label="Run a live compression check" />
            <QuickLink to="/capabilities" label="See the full product surface map" />
            <QuickLink to="/memory" label="Inspect cross-session memory signals" />
          </div>
        </aside>
      </div>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Recent activity</div>
            <h2>Latest requests</h2>
          </div>
        </div>

        <div className="capability-grid">
          {recentRequests.length > 0 ? (
            recentRequests.map((request) => (
              <article key={request.request_id} className="capability-card">
                <div className="capability-name">{request.model || 'Unknown model'}</div>
                <p>
                  Saved {formatInteger(request.tokens_saved)} tokens • {formatPercent(request.savings_percent)} •{' '}
                  {formatRelativeTime(request.timestamp)}
                </p>
                <p>
                  Latency {formatDurationMs(request.total_latency_ms)} • input{' '}
                  {formatInteger(request.input_tokens_original)}
                </p>
              </article>
            ))
          ) : (
            <div className="empty-copy">No recent requests yet.</div>
          )}
        </div>
      </section>
    </section>
  );
}

function StatusTile({ icon, label, value, detail }) {
  return (
    <article className="status-bullet">
      <div className="capability-name">
        {icon}
        {label}
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function QuickLink({ to, label }) {
  return (
    <Link to={to} className="nav-card">
      <div className="nav-card-title">{label}</div>
      <div className="nav-card-copy">
        Open
        <ArrowRight size={14} />
      </div>
    </Link>
  );
}
