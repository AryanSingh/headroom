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
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  formatCurrency,
  formatInteger,
  formatNumber,
  formatPercent,
  formatRelativeTime,
} from '../lib/format';
import { useDashboardData } from '../lib/use-dashboard-data';

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
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          style={{
            display: 'grid',
            gridTemplateColumns: '140px minmax(0, 1fr) 50px',
            gap: '16px',
            alignItems: 'center',
          }}
        >
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

function buildSourceRows(stats) {
  const sourceTokens = stats?.savings_by_source?.tokens || {};
  const sourceUsd = stats?.savings_by_source?.usd || {};
  const costBreakdown = stats?.summary?.cost?.breakdown || {};
  const sessionTokens = stats?.tokens || {};
  const prefixTotals = stats?.prefix_cache?.totals || {};

  // savings_by_source is file-backed (lifetime). Session counters track the
  // same signals in-memory for the active run. Always take the higher of the
  // two so the attribution bars reflect both fresh sessions and prior history.
  const sessionCompression = Number(sessionTokens.proxy_compression_saved || 0);
  const sessionSchemaCompaction = Number(sessionTokens.schema_compaction_saved || 0);
  const sessionCacheRead = Number(prefixTotals.cache_read_tokens || 0);
  const sessionCliFiltering = Number(sessionTokens.cli_filtering_saved || 0);

  return [
    {
      key: 'cutctx_compression',
      label: 'Direct compression',
      tokens: Math.max(Number(sourceTokens.cutctx_compression || 0), sessionCompression),
      usd: Number(sourceUsd.cutctx_compression || costBreakdown.compression_savings_usd || 0),
      session: sessionCompression,
    },
    {
      key: 'tool_schema_compaction',
      label: 'Tool schema compaction',
      tokens: Math.max(Number(sourceTokens.tool_schema_compaction || 0), sessionSchemaCompaction),
      usd: Number(sourceUsd.tool_schema_compaction || 0),
      session: sessionSchemaCompaction,
    },
    {
      key: 'provider_prompt_cache',
      label: 'Provider prompt cache',
      tokens: Math.max(Number(sourceTokens.provider_prompt_cache || 0), sessionCacheRead),
      usd: Number(sourceUsd.provider_prompt_cache || costBreakdown.cache_savings_usd || 0),
      session: sessionCacheRead,
    },
    {
      key: 'cli_filtering',
      label: 'CLI output filtering',
      tokens: Math.max(Number(sourceTokens.cli_filtering || 0), sessionCliFiltering),
      usd: 0,
      session: sessionCliFiltering,
    },
    {
      key: 'api_surface_slimming',
      label: 'API surface slimming',
      tokens: Number(sourceTokens.api_surface_slimming || 0),
      usd: Number(sourceUsd.api_surface_slimming || 0),
    },
    {
      key: 'semantic_cache',
      label: 'Semantic cache',
      tokens: Number(sourceTokens.semantic_cache || 0),
      usd: Number(sourceUsd.semantic_cache || 0),
    },
    {
      key: 'model_routing',
      label: 'Model routing',
      tokens: Number(sourceTokens.model_routing || 0),
      usd: Number(sourceUsd.model_routing || 0),
    },
  ];
}

function buildClientRows(stats) {
  const byClient =
    stats?.summary?.cost?.savings_by_client || stats?.savings_by_client || {};

  return Object.entries(byClient)
    .map(([client, data]) => ({
      key: client,
      label: client,
      tokens: Number(data.total_tokens || 0),
      usd: Number(data.total_usd || 0),
    }))
    .sort((a, b) => b.tokens - a.tokens);
}

function getRequestDirectSaved(request) {
  if (request?.tokens_saved == null) {
    return null;
  }

  return Number(request.tokens_saved || 0);
}

function getRequestScaffoldingTokens(request) {
  if (request?.scaffolding_tokens == null) {
    return null;
  }

  return Number(request.scaffolding_tokens || 0);
}

function getRequestGhostTokens(request) {
  if (request?.ghost_tokens == null) {
    return null;
  }

  return Number(request.ghost_tokens || 0);
}

function getRequestIndirectSaved(request) {
  return (
    Number(request?.cache_saved_tokens || 0)
    + Number(request?.semantic_cache_saved_tokens || 0)
    + Number(request?.self_hosted_prefix_cache_saved_tokens || 0)
    + Number(request?.model_routing_saved_tokens || 0)
  );
}

function getBucketRequestCount(entry) {
  const requestCount = entry?.requests ?? entry?.request_count ?? entry?.count ?? null;
  if (requestCount != null) {
    return Number(requestCount || 0);
  }

  const modelRequestCount = Object.values(entry?.by_model || {}).reduce(
    (sum, value) => sum + Number(value?.requests || 0),
    0,
  );
  if (modelRequestCount > 0) {
    return modelRequestCount;
  }

  const providerRequestCount = Object.values(entry?.by_provider || {}).reduce(
    (sum, value) => sum + Number(value?.requests || 0),
    0,
  );
  if (providerRequestCount > 0) {
    return providerRequestCount;
  }

  if (Number(entry?.tokens_saved || 0) > 0 || Number(entry?.total_tokens_saved || 0) > 0) {
    return 1;
  }

  return null;
}

function addBucketModelContribution(bucket, model, tokensSaved, requests = 0) {
  const key = model || 'unknown';
  const current = bucket.models[key] || { tokens: 0, requests: 0 };
  bucket.models[key] = {
    tokens: current.tokens + Number(tokensSaved || 0),
    requests: current.requests + Number(requests || 0),
  };
}

function getBucketTopModels(bucket, limit = 2) {
  return Object.entries(bucket?.models || {})
    .map(([model, value]) => ({
      model,
      tokens: Number(value?.tokens || 0),
      requests: Number(value?.requests || 0),
    }))
    .filter((entry) => entry.tokens > 0 || entry.requests > 0)
    .sort((a, b) => b.tokens - a.tokens || b.requests - a.requests)
    .slice(0, limit);
}

function buildDiagnosticsFallback(prefixCache) {
  const totals = prefixCache?.totals || {};
  const totalRequests = Number(totals.requests || 0);
  const totalReads = Number(totals.cache_read_tokens || 0);
  const totalWrites = Number(totals.cache_write_tokens || 0);
  const bustCount = Number(totals.bust_count || 0);
  const hitRate = Number(totals.hit_rate || 0);
  const findings = [];

  if (totalRequests === 0) {
    findings.push({
      severity: 'info',
      code: 'no_prefix_cache_traffic',
      title: 'No provider cache traffic yet',
      detail: 'Prompt-cache diagnostics appear once repeated requests flow through the proxy.',
      recommendation: 'Run a few repeated requests with a stable prefix to populate this panel.',
    });
    return findings;
  }

  if (totalWrites === 0 && totalReads === 0) {
    findings.push({
      severity: 'high',
      code: 'cache_not_engaged',
      title: 'Provider prompt caching is not engaging',
      detail: 'The proxy is seeing requests, but providers are not reporting prompt-cache reads or writes.',
      recommendation: 'Verify cache breakpoints and keep the reusable prompt prefix byte-stable.',
    });
  }

  if (totalWrites > 0 && totalReads === 0) {
    findings.push({
      severity: 'high',
      code: 'warming_without_hits',
      title: 'The cache is warming but not being reused',
      detail: 'Providers are reporting cache writes, but not cache reads.',
      recommendation: 'Keep system prompts, tool schemas, and earlier turns stable between requests.',
    });
  }

  if (hitRate > 0 && hitRate < 20) {
    findings.push({
      severity: 'medium',
      code: 'low_hit_rate',
      title: 'Prompt-cache hit rate is still low',
      detail: `Only ${hitRate.toFixed(1)}% of observed prompt tokens are being served from cache.`,
      recommendation: 'Reduce prefix churn so more repeated prompt volume lands in the cached region.',
    });
  }

  if (bustCount > 0) {
    findings.push({
      severity: 'medium',
      code: 'cache_busts_detected',
      title: 'Cache busts are eroding savings',
      detail: `${formatInteger(bustCount)} cache busts were observed in recent provider traffic.`,
      recommendation: 'Avoid mutating earlier cached messages once the prefix is warm.',
    });
  }

  if (findings.length === 0) {
    findings.push({
      severity: 'info',
      code: 'cache_healthy',
      title: 'Provider prompt caching looks healthy',
      detail: 'The proxy is observing cache activity without an obvious anti-pattern dominating savings.',
      recommendation: 'Most additional gains now come from direct compression and other optimization layers.',
    });
  }

  return findings;
}

function Sparkline({ values, color = 'var(--accent)', height = 28, width = 80 }) {
  if (!values || values.length < 2) {
    return null;
  }

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const points = values
    .map((value, index) => {
      const y = height - ((value - min) / range) * (height - 4) - 2;
      return `${index * step},${y}`;
    })
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

function formatBucketLabel(date, period) {
  const options =
    period === '24h'
      ? { hour: 'numeric', minute: '2-digit' }
      : { month: 'short', day: 'numeric' };

  return new Intl.DateTimeFormat('en-US', options).format(date);
}

function buildTrendBuckets({ period, referenceTime, historyData, recentRequestsSource }) {
  const periodMs =
    period === '24h' ? 86_400_000 : period === '7d' ? 604_800_000 : 2_592_000_000;
  const bucketCount = 20;
  const bucketSize = periodMs / bucketCount;
  const buckets = Array.from({ length: bucketCount }, (_, index) => {
    const start = new Date(referenceTime - periodMs + index * bucketSize);
    const end = new Date(referenceTime - periodMs + (index + 1) * bucketSize);
    return {
      index,
      start,
      end,
      tokens: 0,
      requests: null,
      hasRequestData: false,
      models: {},
      label: `${formatBucketLabel(start, period)} - ${formatBucketLabel(end, period)}`,
    };
  });

  const series = historyData?.series;
  if (series) {
    const sourceData =
      period === '24h'
        ? series.hourly || []
        : period === '7d'
          ? series.daily || []
          : series.daily || series.weekly || [];
    for (const entry of sourceData) {
      const timestamp = new Date(entry.timestamp).getTime();
      const age = referenceTime - timestamp;
      if (age < 0 || age > periodMs) {
        continue;
      }

      const index = Math.min(bucketCount - 1, Math.floor((periodMs - age) / bucketSize));
      buckets[index].tokens += Number(entry.tokens_saved || 0);
      const requestCount = getBucketRequestCount(entry);
      if (requestCount != null) {
        buckets[index].requests =
          Number(buckets[index].requests || 0) + requestCount;
        buckets[index].hasRequestData = true;
      }
      for (const [model, data] of Object.entries(entry.by_model || {})) {
        addBucketModelContribution(
          buckets[index],
          model,
          Number(data?.tokens_saved || 0),
          Number(data?.requests || 0),
        );
      }
    }
  }

  const recentRequests = Array.isArray(recentRequestsSource) ? recentRequestsSource : [];
  for (const request of recentRequests) {
    const timestamp = new Date(request.timestamp).getTime();
    const age = referenceTime - timestamp;
    if (age < 0 || age > periodMs) {
      continue;
    }

      const index = Math.min(bucketCount - 1, Math.floor((periodMs - age) / bucketSize));
      if (!series) {
        const totalSaved = getRequestTotalSaved(request);
        buckets[index].tokens += totalSaved;
        addBucketModelContribution(buckets[index], request.model, totalSaved, 1);
      }
      if (!series) {
        buckets[index].requests = Number(buckets[index].requests || 0) + 1;
        buckets[index].hasRequestData = true;
      }
  }

  return buckets;
}

function TrendChart({ stats, historyData }) {
  const [period, setPeriod] = useState('24h');
  const [referenceTime, setReferenceTime] = useState(() => Date.now());
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const recentRequestsSource = stats?.recent_requests;

  const buckets = useMemo(
    () =>
      buildTrendBuckets({
        period,
        referenceTime,
        historyData,
        recentRequestsSource,
      }),
    [historyData, period, recentRequestsSource, referenceTime],
  );

  const maxBar = Math.max(...buckets.map((bucket) => bucket.tokens), 1);
  const yAxisTicks = [maxBar, Math.round(maxBar / 2), 0];
  const activeBucket =
    hoveredIndex != null
      ? buckets[hoveredIndex]
      : buckets.findLast((bucket) => bucket.tokens > 0) || buckets.at(-1);
  const activeBucketTopModels = activeBucket ? getBucketTopModels(activeBucket) : [];

  if (buckets.every((bucket) => bucket.tokens === 0)) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="No trend data yet"
        description="Token savings over time will appear here once requests flow through the proxy."
      />
    );
  }

  return (
    <div className="trend-chart-shell">
      <div className="trend-chart-header">
        <div className="trend-chart-tabs">
          {['24h', '7d', '30d'].map((nextPeriod) => (
            <button
              key={nextPeriod}
              className={`trend-tab ${period === nextPeriod ? 'active' : ''}`}
              onClick={() => {
                setPeriod(nextPeriod);
                setReferenceTime(Date.now());
                setHoveredIndex(null);
              }}
              type="button"
            >
              {nextPeriod}
            </button>
          ))}
        </div>

        {activeBucket ? (
          <div className="trend-hover-summary">
            <div className="trend-hover-label">{activeBucket.label}</div>
            <div className="trend-hover-metrics">
              <span>{formatInteger(activeBucket.tokens)} tokens saved</span>
              <span>
                {activeBucket.hasRequestData
                  ? `${formatInteger(activeBucket.requests)} requests`
                  : 'Request count unavailable'}
              </span>
              <span>
                {activeBucketTopModels.length > 0
                  ? `Top model: ${activeBucketTopModels
                      .map((entry) => `${entry.model} (${formatInteger(entry.tokens)})`)
                      .join(', ')}`
                  : 'Model mix unavailable'}
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="trend-chart">
        <div className="trend-y-axis" aria-hidden="true">
          {yAxisTicks.map((tick) => (
            <span key={tick}>{formatNumber(tick)}</span>
          ))}
        </div>

        <div className="trend-plot-area">
          <div className="trend-grid-lines" aria-hidden="true">
            {yAxisTicks.map((tick, index) => (
              <span key={`${tick}-${index}`} />
            ))}
          </div>

          <div className="trend-chart-container">
            {buckets.map((bucket, index) => {
              const ratio = bucket.tokens / maxBar;
              const scaledHeight = bucket.tokens === 0 ? 4 : Math.max(4, Math.sqrt(ratio) * 100);
              const isActive = index === hoveredIndex;
              const requestText = bucket.hasRequestData
                ? `${formatInteger(bucket.requests)} requests`
                : 'Request count unavailable';
              const topModels = getBucketTopModels(bucket);
              const modelText = topModels.length > 0
                ? `Top model${topModels.length > 1 ? 's' : ''}: ${topModels
                    .map((entry) => `${entry.model} (${formatInteger(entry.tokens)})`)
                    .join(', ')}`
                : 'Model mix unavailable';

              return (
                <button
                  key={`${period}-${index}`}
                  className={`trend-bar ${isActive ? 'active' : ''}`}
                  style={{ height: `${scaledHeight}%` }}
                  title={`${bucket.label}: ${formatInteger(bucket.tokens)} tokens saved${bucket.hasRequestData ? ` across ${formatInteger(bucket.requests)} requests` : ''}${topModels.length > 0 ? ` · ${modelText}` : ''}`}
                  type="button"
                  onMouseEnter={() => setHoveredIndex(index)}
                  onFocus={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  onBlur={() => setHoveredIndex(null)}
                >
                  <span className="trend-bar-tooltip">
                    <strong>{bucket.label}</strong>
                    <span>{formatInteger(bucket.tokens)} tokens saved</span>
                    <span>{requestText}</span>
                    <span>{modelText}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="trend-x-axis" aria-hidden="true">
            <span>{formatBucketLabel(buckets[0].start, period)}</span>
            <span>{formatBucketLabel(buckets[Math.floor(buckets.length / 2)].start, period)}</span>
            <span>Now</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  iconColor = '',
  label,
  value,
  footnote,
  sparkline,
  sparklineColor,
}) {
  return (
    <article className="metric-card">
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className={`metric-icon ${iconColor}`}>
          <Icon size={16} />
        </div>
      </div>

      <div className="metric-value">{value}</div>
      {sparkline ? <Sparkline values={sparkline} color={sparklineColor} /> : null}
      <div className="metric-footnote">{footnote}</div>
    </article>
  );
}

function QuickAction({ to, icon: Icon, label, description }) {
  return (
    <Link
      to={to}
      className="card"
      style={{
        padding: 'var(--space-xl)',
        display: 'grid',
        gap: 'var(--space-sm)',
        textDecoration: 'none',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-md)',
          marginBottom: 'var(--space-xs)',
        }}
      >
        <div className="metric-icon">
          <Icon size={16} />
        </div>
        <span
          style={{
            fontWeight: 600,
            fontSize: 'var(--text-sm)',
            color: 'var(--text-primary)',
          }}
        >
          {label}
        </span>
      </div>

      <p
        style={{
          color: 'var(--text-tertiary)',
          fontSize: 'var(--text-sm)',
          margin: 0,
          lineHeight: '1.5',
        }}
      >
        {description}
      </p>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          color: 'var(--accent)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          marginTop: 'var(--space-sm)',
        }}
      >
        Open <ArrowRight size={14} />
      </div>
    </Link>
  );
}

function SavingsPanel({ title, eyebrow, rows, totalTokens, emptyIcon, emptyTitle, emptyDescription }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className="source-stack">
          {rows.map((row) => {
            const percent = totalTokens > 0 ? (row.tokens / totalTokens) * 100 : 0;
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
                    style={{ width: `${Math.min(100, percent)}%` }}
                  />
                </div>

                <div className="source-percent">{formatPercent(percent)}</div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}


function RouterDiagnosticsPanel({ routeCounts }) {
  if (!routeCounts || Object.keys(routeCounts).length === 0) {
    return null;
  }

  // Group metrics
  const protectionKeys = ['user_msg', 'system_msg', 'recent_code'];
  const constraintKeys = ['small', 'ratio_too_high', 'already_compressed'];
  const formatKeys = ['non_string', 'content_blocks', 'excluded_tool', 'analysis_ctx'];

  const getGroupSum = (keys) => keys.reduce((sum, key) => sum + (routeCounts[key] || 0), 0);

  const protectionTotal = getGroupSum(protectionKeys);
  const constraintTotal = getGroupSum(constraintKeys);
  const formatTotal = getGroupSum(formatKeys);
  
  const totalBypassed = protectionTotal + constraintTotal + formatTotal;

  if (totalBypassed === 0) {
    return null;
  }

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Router diagnostics</div>
          <h2>Bypassed Messages</h2>
          <p>Why certain messages skipped the compressor</p>
        </div>
      </div>

      <div className="diagnostic-stack">
        {protectionTotal > 0 && (
          <div className="diagnostic-card severity-info">
            <div className="diagnostic-title-row">
              <strong>User / System Protection</strong>
              <span className="diagnostic-severity">{formatInteger(protectionTotal)} msgs</span>
            </div>
            <p>Messages intentionally protected from compression to preserve high-fidelity context.</p>
            <div className="provider-status-meta" style={{ marginTop: '0.5rem', gap: '1rem', display: 'flex', fontSize: '0.875rem' }}>
              {protectionKeys.map(k => routeCounts[k] ? <span key={k}>{k}: {routeCounts[k]}</span> : null)}
            </div>
          </div>
        )}

        {constraintTotal > 0 && (
          <div className="diagnostic-card severity-medium">
            <div className="diagnostic-title-row">
              <strong>Compression Constraints</strong>
              <span className="diagnostic-severity">{formatInteger(constraintTotal)} msgs</span>
            </div>
            <p>Messages that failed heuristic checks (e.g., too small or insufficient expected savings).</p>
            <div className="provider-status-meta" style={{ marginTop: '0.5rem', gap: '1rem', display: 'flex', fontSize: '0.875rem' }}>
              {constraintKeys.map(k => routeCounts[k] ? <span key={k}>{k}: {routeCounts[k]}</span> : null)}
            </div>
          </div>
        )}

        {formatTotal > 0 && (
          <div className="diagnostic-card severity-high">
            <div className="diagnostic-title-row">
              <strong>Format Constraints</strong>
              <span className="diagnostic-severity">{formatInteger(formatTotal)} msgs</span>
            </div>
            <p>Payload formats that the compressor currently ignores or bypasses by policy.</p>
            <div className="provider-status-meta" style={{ marginTop: '0.5rem', gap: '1rem', display: 'flex', fontSize: '0.875rem' }}>
              {formatKeys.map(k => routeCounts[k] ? <span key={k}>{k}: {routeCounts[k]}</span> : null)}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function DiagnosticsPanel({ prefixCache }) {
  const diagnostics = prefixCache?.diagnostics || {};
  const findings = Array.isArray(diagnostics.findings) && diagnostics.findings.length > 0
    ? diagnostics.findings
    : buildDiagnosticsFallback(prefixCache);
  const providerStates = Array.isArray(diagnostics.by_provider) ? diagnostics.by_provider : [];

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Savings diagnosis</div>
          <h2>Why savings look low</h2>
          <p>These findings come from provider prompt-cache reads, writes, busts, and uncached volume.</p>
        </div>
      </div>

      {findings.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No diagnostics yet"
          description="Run a few repeated requests and the dashboard will explain where cache savings are being lost."
        />
      ) : (
        <div className="diagnostic-stack">
          {findings.map((finding) => (
            <div
              key={finding.code || finding.title}
              className={`diagnostic-card severity-${finding.severity || 'info'}`}
            >
              <div className="diagnostic-title-row">
                <strong>{finding.title}</strong>
                <span className="diagnostic-severity">{finding.severity || 'info'}</span>
              </div>
              <p>{finding.detail}</p>
              {finding.recommendation ? (
                <div className="diagnostic-recommendation">{finding.recommendation}</div>
              ) : null}
            </div>
          ))}

          {providerStates.length > 0 ? (
            <div className="provider-status-grid">
              {providerStates.map((provider) => (
                <div key={provider.provider} className="provider-status-card">
                  <div className="provider-status-header">
                    <strong>{provider.provider}</strong>
                    <span className={`status-pill status-${provider.status || 'neutral'}`}>
                      {provider.status || 'unknown'}
                    </span>
                  </div>
                  <p>{provider.reason}</p>
                  <div className="provider-status-meta">
                    <span>{formatInteger(provider.requests)} requests</span>
                    <span>{formatPercent(provider.hit_rate || 0)} hit rate</span>
                    <span>{formatInteger(provider.bust_count || 0)} busts</span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

// Maps API feature-availability keys to user-facing display labels.
// All keys use branded names — no underlying library names appear here.
const STRATEGY_DISPLAY = new Map([
  ['knowledge_graph', 'Knowledge Graph'],
  ['log_template_mining', 'Log pattern analysis'],
  ['structural_diff_engine', 'Structural diff'],
  ['text_compression_engine', 'Semantic text compression'],
  ['multimodal_image', 'Image / OCR'],
  ['smart_crusher', 'SmartCrusher'],
  ['kompress', 'ML compression'],
  ['html_extractor', 'HTML Extractor'],
  ['voice_filler', 'Voice Filler'],
  ['code_ast', 'Code AST'],
  ['audio', 'Audio (proxy)'],
]);

function getStrategyLabel(key) {
  return STRATEGY_DISPLAY.get(key) || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function FeatureAvailabilityPanel({ featureAvailability }) {
  if (!featureAvailability || Object.keys(featureAvailability).length === 0) return null;
  const entries = Object.entries(featureAvailability);
  const availableCount = entries.filter(
    ([, value]) => value?.available && value?.compression !== 'pass-through',
  ).length;
  const passthroughCount = entries.filter(([, value]) => value?.compression === 'pass-through').length;
  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Runtime capabilities</div>
          <h2>Feature availability</h2>
          <p>Which optional Python extras and binaries are installed and active in this runtime.</p>
        </div>
        <span className="stat-badge">
          {availableCount} available{passthroughCount > 0 ? ` · ${passthroughCount} pass-through` : ''}
        </span>
      </div>
      <div className="graphify-kv-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
        {entries.map(([key, val]) => {
          const isAudio = val?.compression === 'pass-through';
          const available = val?.available;
          const pillClass = isAudio ? 'status-pill status-info' : available ? 'status-pill status-ready' : 'status-pill status-degraded';
          const pillLabel = isAudio ? 'pass-through' : available ? 'available' : 'missing';
          return (
            <div key={key} className="graphify-kv" title={val?.install_hint || val?.reason || ''}>
              <span>{getStrategyLabel(key)}</span>
              <strong><span className={pillClass}>{pillLabel}</span></strong>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function formatKnowledgeGraphStatus(knowledgeGraph) {
  const status = knowledgeGraph?.status || 'disabled';
  switch (status) {
    case 'ready':
      return 'Ready';
    case 'building':
      return 'Building';
    case 'unavailable':
      return 'Unavailable';
    case 'degraded':
      return 'Degraded';
    default:
      return 'Disabled';
  }
}

function GraphStatusPanel({ knowledgeGraph }) {
  const status = knowledgeGraph?.status || 'disabled';
  const countsAvailable = Number(knowledgeGraph?.node_count || 0) > 0 || Number(knowledgeGraph?.edge_count || 0) > 0;

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Graphify</div>
          <h2>Knowledge graph status</h2>
          <p>Clear state for requested, available, building, and live graph-backed compression behavior.</p>
        </div>
      </div>

      <div className="graphify-status-shell">
        <div className="graphify-status-row">
          <span className={`status-pill status-${status}`}>{formatKnowledgeGraphStatus(knowledgeGraph)}</span>
          <span className="graphify-status-copy">
            {knowledgeGraph?.reason
              ? knowledgeGraph.reason
              : knowledgeGraph?.active
                ? 'Interceptor is live and graph summaries can replace large tool output.'
                : knowledgeGraph?.requested
                  ? 'Requested, but not yet active.'
                  : 'Not enabled for this proxy.'}
          </span>
        </div>

        <div className="graphify-kv-grid">
          <div className="graphify-kv">
            <span>Requested</span>
            <strong>{knowledgeGraph?.requested ? 'Yes' : 'No'}</strong>
          </div>
          <div className="graphify-kv">
            <span>Available</span>
            <strong>{knowledgeGraph?.available ? 'Yes' : 'No'}</strong>
          </div>
          <div className="graphify-kv">
            <span>Interceptor</span>
            <strong>{knowledgeGraph?.interceptor_registered ? 'Registered' : 'Not registered'}</strong>
          </div>
          <div className="graphify-kv">
            <span>Version</span>
            <strong>{knowledgeGraph?.version || '—'}</strong>
          </div>
          {countsAvailable ? (
            <>
              <div className="graphify-kv">
                <span>Nodes</span>
                <strong>{formatInteger(knowledgeGraph?.node_count || 0)}</strong>
              </div>
              <div className="graphify-kv">
                <span>Edges</span>
                <strong>{formatInteger(knowledgeGraph?.edge_count || 0)}</strong>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function getRequestTotalSaved(request) {
  if (request?.total_saved_tokens != null) {
    return Number(request.total_saved_tokens || 0);
  }

  return Number(getRequestDirectSaved(request) || 0) + getRequestIndirectSaved(request);
}

function getRequestTotalSavingsPercent(request) {
  if (request?.total_savings_percent != null) {
    return Number(request.total_savings_percent || 0);
  }

  const originalTokens = Number(request?.input_tokens_original || 0);
  const totalSaved = getRequestTotalSaved(request);
  return originalTokens > 0 ? (totalSaved / originalTokens) * 100 : 0;
}

function formatMaybeInteger(value) {
  return value == null ? '—' : formatInteger(value);
}

function formatMaybePercent(value) {
  return value == null ? '—' : formatPercent(Math.min(100, Math.max(0, Number(value || 0))));
}

export default function Overview() {
  const {
    stats,
    historyData,
    historyLoading,
    historyError,
    loading,
    error,
  } = useDashboardData();
  const summary = stats?.summary || {};
  const requests = stats?.requests || {};
  const tokens = stats?.tokens || {};
  const persistent = stats?.persistent_savings || {};
  const lifetime = persistent.lifetime || {};
  const prefixCache = stats?.prefix_cache || {};
  const knowledgeGraph = stats?.knowledge_graph || {};
  const featureAvailability = stats?.feature_availability || {};

  const effectiveTokensSaved = Math.max(
    Number(tokens.saved || 0),
    Number(lifetime.tokens_saved || 0),
  );
  const effectiveRequests = Math.max(
    Number(requests.total || 0),
    Number(lifetime.requests || 0),
  );
  const sessionCostWithoutCutctx = Number(summary?.cost?.without_cutctx_usd || 0);
  const sessionCostWithCutctx = Number(summary?.cost?.with_cutctx_usd || 0);
  const sessionCostBreakdown = summary?.cost?.breakdown || {};
  const sessionSavingsUsd = Math.max(
    Number(summary?.cost?.total_saved_usd || 0),
    Number(sessionCostBreakdown.compression_savings_usd || 0)
      + Number(sessionCostBreakdown.cache_savings_usd || 0),
  );
  const lifetimeSavingsUsd = Number(lifetime.compression_savings_usd || 0);
  const effectiveSavingsUsd = sessionCostWithoutCutctx > 0
    ? sessionSavingsUsd
    : lifetimeSavingsUsd;
  const moneySavedFootnote = sessionCostWithoutCutctx > 0
    ? `from ${formatCurrency(sessionCostWithoutCutctx)} down to ${formatCurrency(sessionCostWithCutctx)}`
    : lifetimeSavingsUsd > 0
      ? 'Lifetime compression savings'
      : 'No cost data yet';

  const persistentHistory = Array.isArray(persistent.recent_history)
    ? persistent.recent_history.slice(-8).reverse().map((entry) => ({
        model: entry.model,
        input_tokens_original: null,
        tokens_saved: null,
        total_saved_tokens: entry.delta_tokens_saved,
        total_savings_percent: null,
        savings_percent: null,
        scaffolding_tokens: null,
        ghost_tokens: null,
        timestamp: entry.timestamp,
        synthetic: true,
      }))
    : [];

  const recentRequests =
    Array.isArray(stats?.recent_requests) && stats.recent_requests.length > 0
      ? stats.recent_requests.slice(0, 8)
      : persistentHistory;

  const sourceRows = buildSourceRows(stats);
  const activeSourceRows = sourceRows.filter((row) => row.tokens > 0);
  const clientRows = buildClientRows(stats);
  const activeClientRows = clientRows.filter((row) => row.tokens > 0);
  const totalSourceTokens =
    activeSourceRows.reduce((sum, row) => sum + row.tokens, 0) ||
    Number(tokens.total_before_compression || 0);
  const totalClientTokens =
    activeClientRows.reduce((sum, row) => sum + row.tokens, 0) || totalSourceTokens;
  const activeCompressionPercent =
    tokens.active_savings_percent != null ? Number(tokens.active_savings_percent || 0) : null;
  const proxyCompressionPercent =
    tokens.proxy_savings_percent != null ? Number(tokens.proxy_savings_percent || 0) : null;
  const directCompressionRow = sourceRows.find((row) => row.key === 'cutctx_compression');
  const toolSchemaRow = sourceRows.find((row) => row.key === 'tool_schema_compaction');
  const providerCacheRow = sourceRows.find((row) => row.key === 'provider_prompt_cache');

  return (
    <section className="page-stack">
      {error ? (
        <div className="alert-card" role="alert">
          <span>Failed to load data: {error}</span>
          <button
            className="ghost-button"
            style={{ marginLeft: 'auto' }}
            onClick={() => window.location.reload()}
            type="button"
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="metric-grid metric-grid-four">
          {Array.from({ length: 4 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : (
        <div className="metric-grid metric-grid-four">
          <MetricCard
            icon={PiggyBank}
            iconColor="green"
            label="Tokens saved"
            value={formatNumber(effectiveTokensSaved)}
            footnote={`${formatPercent(tokens.savings_percent || 0)} total reduction`}
            sparkline={recentRequests.slice(0, 10).map((request) => getRequestTotalSaved(request))}
            sparklineColor="var(--accent)"
          />
          <MetricCard
            icon={Table2}
            iconColor="blue"
            label="Requests"
            value={formatInteger(effectiveRequests)}
            footnote={`${formatInteger(requests.failed || 0)} failed · ${formatInteger(requests.cached || 0)} cached`}
          />
          <MetricCard
            icon={Layers}
            iconColor="purple"
            label="Active compression"
            value={activeCompressionPercent != null ? `${activeCompressionPercent.toFixed(1)}%` : '—'}
            footnote={
              proxyCompressionPercent != null
                ? `${formatPercent(proxyCompressionPercent)} whole-request proxy reduction`
                : 'Compressible-token savings rate'
            }
          />
          <MetricCard
            icon={Coins}
            iconColor="amber"
            label="Money saved"
            value={formatCurrency(effectiveSavingsUsd)}
            footnote={moneySavedFootnote}
          />
        </div>
      )}

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Trend</div>
            <h2>Savings over time</h2>
          </div>
        </div>

        {loading || historyLoading ? (
          <div className="skeleton" style={{ height: '260px', borderRadius: 'var(--radius-lg)' }} />
        ) : historyError ? (
          <EmptyState
            icon={TrendingUp}
            title="Trend data unavailable"
            description={`The history feed failed to load: ${historyError}`}
          />
        ) : (
          <TrendChart stats={stats} historyData={historyData} />
        )}
      </div>

      <div className="overview-bottom-grid">
        <div className="overview-side-stack">
          <section className="panel panel-compact">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Attribution</div>
                <h2>Where savings come from</h2>
                <p>Direct compression and provider-side cache wins are split out so total savings stays legible.</p>
              </div>
            </div>

            {loading ? (
              <SkeletonBar />
            ) : activeSourceRows.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No savings data yet"
                description="Savings attribution will populate as requests flow through compression and cache channels."
              />
            ) : (
              <>
                <div className="attribution-note">
                  <span>Direct compression: {formatInteger(directCompressionRow?.tokens || 0)} tokens</span>
                  <span>Tool schema: {formatInteger(toolSchemaRow?.tokens || 0)} tokens</span>
                  <span>Provider cache: {formatInteger(providerCacheRow?.tokens || 0)} tokens</span>
                </div>

                <div className="source-stack">
                  {activeSourceRows.map((row) => {
                    const percent = totalSourceTokens > 0 ? (row.tokens / totalSourceTokens) * 100 : 0;
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
                            style={{ width: `${Math.min(100, percent)}%` }}
                          />
                        </div>
                        <div className="source-percent">{formatPercent(percent)}</div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </section>

          {activeClientRows.length > 0 ? (
            <SavingsPanel
              title="Savings by client"
              eyebrow="Attribution"
              rows={activeClientRows}
              totalTokens={totalClientTokens}
              emptyIcon={Sparkles}
              emptyTitle="No client data yet"
              emptyDescription="Client-level attribution appears once requests include client tags."
            />
          ) : null}

          <DiagnosticsPanel prefixCache={prefixCache} />
          <RouterDiagnosticsPanel routeCounts={stats?.router?.route_counts} />
          <GraphStatusPanel knowledgeGraph={knowledgeGraph} />
          <FeatureAvailabilityPanel featureAvailability={featureAvailability} />
        </div>

        <section className="panel panel-expanded">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Activity</div>
              <h2>Recent requests</h2>
            </div>
          </div>

          {loading ? (
            <div className="skeleton" style={{ height: '260px', borderRadius: 'var(--radius-lg)' }} />
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
                    <th>Input</th>
                    <th>Saved</th>
                    <th>Proxy</th>
                    <th>Cache</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {recentRequests.map((request, index) => {
                    const indirect = getRequestIndirectSaved(request);
                    const inputTokens = request.input_tokens_original;
                    // Cap displayed savings at input size — provider cache credits
                    // can accumulate across turns and exceed the per-request input count.
                    const rawSaved = getRequestTotalSaved(request);
                    const displaySaved = inputTokens != null
                      ? Math.min(rawSaved, inputTokens)
                      : rawSaved;
                    return (
                      <tr
                        key={`${request.request_id || 'request'}-${request.timestamp || 'unknown'}-${index}`}
                      >
                        <td className="model-name" title={request.model || '—'}>
                          {request.model || '—'}
                        </td>
                        <td>{formatMaybeInteger(inputTokens)}</td>
                        <td className="savings-value">
                          <div className="request-savings-stack">
                            <span>{formatInteger(displaySaved)}</span>
                            <span className="request-savings-percent">
                              {formatMaybePercent(
                                request.synthetic ? null : getRequestTotalSavingsPercent(request),
                              )}
                            </span>
                          </div>
                        </td>
                        <td>
                          <div className="request-savings-stack request-savings-stack-muted">
                            <span>{formatMaybeInteger(getRequestDirectSaved(request))}</span>
                            <span className="request-savings-percent">
                              {formatMaybePercent(request.savings_percent)}
                            </span>
                          </div>
                        </td>
                        <td>{indirect > 0 ? formatInteger(indirect) : '—'}</td>
                        <td>{formatRelativeTime(request.timestamp)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="request-table-note">
                Saved = proxy compression + cache combined.
                Proxy = tokens Cutctx compressed. Cache = provider prompt-cache or semantic-cache savings.
              </div>
            </div>
          )}

          <div className="metric-grid metric-grid-three" style={{ marginTop: 'var(--space-xl)' }}>
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
      </div>
    </section>
  );
}
