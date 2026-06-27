import {
  ArrowRight,
  BarChart3,
  Coins,
  Inbox,
  Layers,
  PiggyBank,
  RefreshCw,
  Sparkles,
  Table2,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  formatCurrency,
  formatInteger,
  formatNumber,
  formatPercent,
  formatRelativeTime,
} from '../lib/format';
import { useDashboardData } from '../lib/use-dashboard-data';

/* ─── Helpers ─────────────────────────────────────────────────── */

function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton skeleton-line skeleton-line-sm" />
      <div className="skeleton skeleton-value" />
      <div className="skeleton skeleton-line skeleton-line-lg" />
    </div>
  );
}

function SkeletonBar() {
  return (
    <div style={{ display: 'grid', gap: '12px' }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: '140px 1fr 50px', gap: '16px', alignItems: 'center' }}>
          <div className="skeleton skeleton-line skeleton-line-sm" />
          <div className="skeleton" style={{ height: '8px', borderRadius: '999px' }} />
          <div className="skeleton skeleton-line" style={{ width: '40px' }} />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="overview-empty">
      <div className="overview-empty-illustration">
        <Icon size={28} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

/* ─── Source rows builder ─────────────────────────────────────── */

function buildSourceRows(stats) {
  const sourceTokens = stats?.savings_by_source?.tokens || {};
  const sourceUsd = stats?.savings_by_source?.usd || {};
  const tokens = stats?.tokens || {};
  const cost = stats?.summary?.cost || {};

  return [
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
}

/* ─── Mini sparkline (pure SVG, no dependencies) ──────────────── */

function Sparkline({ values, color = 'var(--accent)', height = 28, width = 80 }) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = width / (values.length - 1);

  const points = values
    .map((v, i) => `${i * step},${height - ((v - min) / range) * (height - 4) - 2}`)
    .join(' ');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="metric-sparkline"
      aria-hidden="true"
    >
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

/* ─── Trend chart ─────────────────────────────────────────────── */

function TrendChart({ stats }) {
  const [period, setPeriod] = useState('24h');

  const bars = useMemo(() => {
    const recentReqs = Array.isArray(stats?.recent_requests) ? stats.recent_requests : [];
    if (recentReqs.length === 0) {
      return Array.from({ length: 20 }, () => 0);
    }

    const now = Date.now();
    const periodMs = period === '24h' ? 86400000 : period === '7d' ? 604800000 : 2592000000;
    const bucketCount = 20;
    const bucketSize = periodMs / bucketCount;

    const buckets = new Array(bucketCount).fill(0);
    for (const req of recentReqs) {
      const ts = new Date(req.timestamp).getTime();
      const age = now - ts;
      if (age >= 0 && age <= periodMs) {
        const idx = Math.min(bucketCount - 1, Math.floor((periodMs - age) / bucketSize));
        buckets[idx] += req.tokens_saved || 0;
      }
    }
    return buckets;
  }, [stats, period]);

  const maxBar = Math.max(...bars, 1);

  return (
    <div>
      <div className="trend-chart-tabs">
        {['24h', '7d', '30d'].map((p) => (
          <button
            key={p}
            className={`trend-tab ${period === p ? 'active' : ''}`}
            onClick={() => setPeriod(p)}
            type="button"
          >
            {p}
          </button>
        ))}
      </div>

      {bars.every((b) => b === 0) ? (
        <EmptyState
          icon={TrendingUp}
          title="No trend data yet"
          description="Token savings over time will appear here once requests flow through the proxy."
        />
      ) : (
        <div className="trend-chart-container">
          {bars.map((value, i) => {
            const ratio = value / maxBar;
            // Use square root scaling to make smaller bars visible despite outliers
            const scaledHeight = value === 0 ? 4 : Math.max(4, Math.sqrt(ratio) * 100);
            return (
              <div
                key={i}
                className="trend-bar"
                style={{ height: `${scaledHeight}%` }}
                title={`${formatNumber(value)} tokens saved`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── Main Overview ───────────────────────────────────────────── */

export default function Overview() {
  const { stats, health, loading, error, lastUpdated } = useDashboardData();

  const summary = stats?.summary || {};
  const requests = stats?.requests || {};
  const tokens = stats?.tokens || {};
  const recentRequests = Array.isArray(stats?.recent_requests)
    ? stats.recent_requests.slice(0, 8)
    : [];

  const sourceRows = buildSourceRows(stats);
  const totalSourceTokens =
    sourceRows.reduce((sum, row) => sum + row.tokens, 0) ||
    Number(tokens.total_before_compression || 0);

  const compressionRatio = tokens.savings_percent
    ? (100 - Number(tokens.savings_percent || 0))
    : null;

  return (
    <section className="page-stack">
      {/* Error banner */}
      {error && (
        <div className="alert-card" role="alert">
          <span>Failed to load data: {error}</span>
          <button className="ghost-button" style={{ marginLeft: 'auto' }} onClick={() => window.location.reload()} type="button">
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      {/* Row 1: Key metrics */}
      {loading ? (
        <div className="metric-grid metric-grid-four">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <div className="metric-grid metric-grid-four">
          <MetricCard
            icon={PiggyBank}
            iconColor="green"
            label="Tokens saved"
            value={formatNumber(tokens.saved)}
            footnote={`${formatPercent(tokens.savings_percent)} total reduction`}
            sparkline={recentRequests.slice(0, 10).map((r) => r.tokens_saved || 0)}
            sparklineColor="var(--accent)"
          />
          <MetricCard
            icon={Table2}
            iconColor="blue"
            label="Requests today"
            value={formatInteger(requests.total)}
            footnote={`${formatInteger(requests.failed)} failed · ${formatInteger(requests.cached)} cached`}
          />
          <MetricCard
            icon={Layers}
            iconColor="purple"
            label="Compression ratio"
            value={compressionRatio != null ? `${compressionRatio.toFixed(1)}%` : '—'}
            footnote="Average token retention"
          />
          <MetricCard
            icon={Coins}
            iconColor="amber"
            label="Money saved"
            value={formatCurrency(summary?.cost?.total_saved_usd)}
            footnote={`vs ${formatCurrency(summary?.cost?.without_cutctx_usd)} without Cutctx`}
          />
        </div>
      )}

      {/* Row 2: Trend chart */}
      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Trend</div>
            <h2>Savings over time</h2>
          </div>
        </div>
        {loading ? (
          <div className="skeleton" style={{ height: '200px', borderRadius: 'var(--radius-lg)' }} />
        ) : (
          <TrendChart stats={stats} />
        )}
      </div>

      {/* Row 3: Attribution + Recent requests */}
      <div className="dashboard-grid">
        {/* Left: Savings attribution */}
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Attribution</div>
              <h2>Where savings come from</h2>
            </div>
          </div>

          {loading ? (
            <SkeletonBar />
          ) : totalSourceTokens === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No savings data yet"
              description="Savings attribution will populate as requests flow through compression and cache channels."
            />
          ) : (
            <div className="source-stack">
              {sourceRows
                .filter((row) => row.tokens > 0)
                .map((row) => {
                  const pct = totalSourceTokens > 0 ? (row.tokens / totalSourceTokens) * 100 : 0;
                  return (
                    <div key={row.key} className="source-row">
                      <div className="source-labels">
                        <div className="source-name">{row.label}</div>
                        <div className="source-meta">
                          {formatInteger(row.tokens)} tokens · {formatCurrency(row.usd)}
                        </div>
                      </div>
                      <div className="source-bar-track">
                        <div
                          className="source-bar-fill"
                          style={{ width: `${Math.min(100, pct)}%` }}
                        />
                      </div>
                      <div className="source-percent">{formatPercent(pct)}</div>
                    </div>
                  );
                })}
            </div>
          )}
        </section>

        {/* Right: Recent requests */}
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Activity</div>
              <h2>Recent requests</h2>
            </div>
          </div>

          {loading ? (
            <div className="skeleton" style={{ height: '200px', borderRadius: 'var(--radius-lg)' }} />
          ) : recentRequests.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No requests yet"
              description="Start using the proxy to see request activity here."
            />
          ) : (
            <div className="table-shell">
              <table className="request-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Tokens</th>
                    <th>Saved</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {recentRequests.map((req, index) => (
                    <tr key={req.request_id || index}>
                      <td className="model-name">{req.model || '—'}</td>
                      <td>{formatInteger(req.input_tokens_original)}</td>
                      <td className="savings-value">
                        {formatInteger(req.tokens_saved)}
                        <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: '4px', fontSize: 'var(--text-xs)' }}>
                          {formatPercent(Math.min(100, Math.max(0, req.savings_percent || 0)))}
                        </span>
                      </td>
                      <td>{formatRelativeTime(req.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* Row 4: Quick actions */}
      <div className="metric-grid metric-grid-three">
        <QuickAction
          to="/playground"
          icon={Zap}
          label="Run compression"
          description="Test a live compression request with the playground."
        />
        <QuickAction
          to="/capabilities"
          icon={Layers}
          label="Product surfaces"
          description="See the full map of available features and capabilities."
        />
        <QuickAction
          to="/memory"
          icon={BarChart3}
          label="Memory signals"
          description="Inspect cross-session memory and correction entries."
        />
      </div>
    </section>
  );
}

/* ─── Metric Card Component ───────────────────────────────────── */

function MetricCard({ icon: Icon, iconColor = '', label, value, footnote, sparkline, sparklineColor }) {
  return (
    <article className="metric-card">
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className={`metric-icon ${iconColor}`}>
          <Icon size={16} />
        </div>
      </div>
      <div className="metric-value">{value}</div>
      {sparkline && <Sparkline values={sparkline} color={sparklineColor} />}
      <div className="metric-footnote">{footnote}</div>
    </article>
  );
}

/* ─── Quick Action Component ──────────────────────────────────── */

function QuickAction({ to, icon: Icon, label, description }) {
  return (
    <Link to={to} className="card" style={{ padding: 'var(--space-xl)', display: 'grid', gap: 'var(--space-sm)', textDecoration: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-xs)' }}>
        <div className="metric-icon">
          <Icon size={16} />
        </div>
        <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{label}</span>
      </div>
      <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', margin: 0, lineHeight: '1.5' }}>{description}</p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--accent)', fontSize: 'var(--text-sm)', fontWeight: 600, marginTop: 'var(--space-sm)' }}>
        Open
        <ArrowRight size={14} />
      </div>
    </Link>
  );
}
