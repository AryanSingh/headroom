import {
  AlertTriangle,
  ArrowUpRight,
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
  Calendar,
  Clock,
  Activity,
} from 'lucide-react';
import { useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  formatCurrency,
  formatInteger,
  formatNumber,
  formatPercent,
  formatRelativeTime,
} from '../lib/format';
import { useDashboardData, fetchDashboardJson } from '../lib/use-dashboard-data';
import { fetchPeriodStats } from '../lib/period-stats';
import {
  getAttributionCoverage,
  getCreatedObservedSavingsTokens,
  getCreatedObservedSavingsUsd,
  getDurationSavingsUsd,
  LIFETIME_SAVINGS_SOURCES,
  isVisibleSavingsRow,
  sumCreatedSavingsObservedUsd,
  sumObservedProviderSavingsObservedUsd,
  sumSavingsUsd,
  sumSavingsObservedUsd,
} from '../lib/savings-sources';

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


function getSessionSavingsUsd(stats) {
  const cost = stats?.cost || {};
  const summaryCost = stats?.summary?.cost || {};
  const breakdown = cost?.breakdown || summaryCost?.breakdown || {};
  const prefixTotals = stats?.prefix_cache?.totals || {};
  const sourceUsd = {
    ...(summaryCost?.savings_by_source?.usd || {}),
    ...(cost?.savings_by_source?.usd || {}),
  };

  const compressionUsd = Math.max(
    Number(cost?.compression_savings_usd || 0),
    Number(cost?.savings_usd || 0),
    Number(sourceUsd.cutctx_compression || 0),
    Number(breakdown.compression_savings_usd || 0),
  );
  const cacheUsd = Math.max(
    Number(cost?.cache_savings_usd || 0),
    Number(sourceUsd.provider_prompt_cache || 0),
    Number(breakdown.cache_savings_usd || 0),
    Number(prefixTotals.net_savings_usd || 0),
    Number(prefixTotals.savings_usd || 0),
  );
  const semanticUsd = Math.max(
    Number(cost?.semantic_cache_savings_usd || 0),
    Number(sourceUsd.semantic_cache || 0),
    Number(breakdown.semantic_cache_savings_usd || 0),
  );
  const selfHostedPrefixUsd = Math.max(
    Number(cost?.self_hosted_prefix_cache_savings_usd || 0),
    Number(sourceUsd.prefix_cache_self_hosted || 0),
    Number(breakdown.self_hosted_prefix_cache_savings_usd || 0),
  );
  const modelRoutingUsd = Math.max(
    Number(cost?.model_routing_savings_usd || 0),
    Number(sourceUsd.model_routing || 0),
    Number(breakdown.model_routing_savings_usd || 0),
  );
  const normalizationUsd = Math.max(
    Number(cost?.normalization_savings_usd || 0),
    Number(sourceUsd.normalization || 0),
    Number(breakdown.normalization_savings_usd || 0),
  );
  const batchRoutingUsd = Math.max(
    Number(cost?.batch_routing_savings_usd || 0),
    Number(sourceUsd.batch_routing || 0),
    Number(breakdown.batch_routing_savings_usd || 0),
  );
  const memoizationUsd = Math.max(
    Number(cost?.memoization_savings_usd || 0),
    Number(sourceUsd.memoization || 0),
    Number(breakdown.memoization_savings_usd || 0),
  );
  const outputOptimizationUsd = Math.max(
    Number(cost?.output_optimization_savings_usd || 0),
    Number(sourceUsd.output_optimization || 0),
    Number(breakdown.output_optimization_savings_usd || 0),
  );
  const toolSchemaUsd = Math.max(
    Number(cost?.tool_schema_compaction_savings_usd || 0),
    Number(sourceUsd.tool_schema_compaction || 0),
    Number(breakdown.tool_schema_compaction_savings_usd || 0),
  );
  const apiSurfaceUsd = Math.max(
    Number(cost?.api_surface_slimming_savings_usd || 0),
    Number(sourceUsd.api_surface_slimming || 0),
    Number(breakdown.api_surface_slimming_savings_usd || 0),
  );
  // Estimated (session's most-used model list price), not tied to a
  // single upstream request like the other rows — see
  // cli_filtering_savings_usd in the backend.
  const cliFilteringUsd = Number(stats?.tokens?.cli_filtering_savings_usd || 0);

  return Math.max(
    Number(cost?.total_savings_usd || 0),
    Number(cost?.total_saved_usd || 0),
    Number(summaryCost?.total_saved_usd || 0),
    compressionUsd
      + cacheUsd
      + semanticUsd
      + selfHostedPrefixUsd
      + modelRoutingUsd
      + normalizationUsd
      + batchRoutingUsd
      + memoizationUsd
      + outputOptimizationUsd
      + toolSchemaUsd
      + apiSurfaceUsd
      + cliFilteringUsd,
  );
}

function getSessionAttributionTotals(stats) {
  const cost = stats?.cost || stats?.summary?.cost || {};
  const source = cost?.savings_by_source || stats?.savings_by_source || {};
  const sourceTokens = source?.tokens || {};
  const sourceTokenTotal = Number(source?.total_tokens || 0);
  const summedSourceTokens = Object.values(sourceTokens).reduce(
    (sum, value) => sum + Number(value || 0),
    0,
  );

  return {
    totalTokensSaved: Math.max(
      sourceTokenTotal,
      summedSourceTokens,
      Number(stats?.tokens?.all_layers_saved || 0),
      Number(stats?.tokens?.saved || 0),
    ),
    totalSavingsUsd: getSessionSavingsUsd(stats),
  };
}

function getLifetimeTotalSavingsUsd(stats) {
  const lifetime = stats?.persistent_savings?.lifetime || {};
  const sourceUsd = stats?.savings_by_source?.usd || {};

  return LIFETIME_SAVINGS_SOURCES.reduce((sum, [lifetimeKey, sourceKey]) => {
    return sum + Math.max(Number(lifetime[lifetimeKey] || 0), Number(sourceUsd[sourceKey] || 0));
  }, 0);
}

function buildSourceRows(stats, periodRecord = null, duration = 'lifetime') {
const scoped = duration !== 'lifetime';
const cost = scoped ? (periodRecord || {}) : (stats?.cost || stats?.summary?.cost || {});
const costSavingsBySource = cost?.savings_by_source || {};
const sourceTokens = {
  ...(scoped ? periodRecord?.savings_by_source_tokens : costSavingsBySource?.tokens || {}),
  ...(scoped ? {} : stats?.savings_by_source?.tokens || {}),
};
const sourceUsd = {
  ...(scoped ? periodRecord?.savings_by_source_usd : costSavingsBySource?.usd || {}),
  ...(scoped ? {} : stats?.savings_by_source?.usd || {}),
};
const costBreakdown = cost?.breakdown || {};
const sessionTokens = scoped ? {} : stats?.tokens || {};
const prefixTotals = scoped ? {} : stats?.prefix_cache?.totals || {};
const cliFilteringLabel =
  stats?.savings?.by_layer?.cli_filtering?.label
  || stats?.context_tool?.label
  || stats?.context_tool?.configured
  || 'RTK / CLI filtering';

  const sessionCompression = scoped
    ? Number(periodRecord?.tokens_saved || 0)
    : Number(sessionTokens.proxy_compression_saved || 0);
  const sessionSchemaCompaction = Number(sessionTokens.schema_compaction_saved || 0);
  const sessionCacheRead = Number(prefixTotals.cache_read_tokens || 0);
  const sessionCliFiltering = Number(sessionTokens.cli_filtering_saved || 0);

  return [
    {
      key: 'cutctx_compression',
      label: 'Direct compression',
      tokens: Math.max(Number(sourceTokens.cutctx_compression || 0), sessionCompression),
usd: Math.max(
  Number(cost.compression_savings_usd || 0),
  Number(sourceUsd.cutctx_compression || 0),
  Number(costBreakdown.compression_savings_usd || 0),
),
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
usd: Math.max(
  Number(cost.cache_savings_usd || 0),
  Number(sourceUsd.provider_prompt_cache || 0),
  Number(costBreakdown.cache_savings_usd || 0),
  Number(prefixTotals.net_savings_usd || 0),
  Number(prefixTotals.savings_usd || 0),
),
      session: sessionCacheRead,
    },
    {
      key: 'rtk_cli_filtering',
      label: cliFilteringLabel,
      tokens: Math.max(
        Number(sourceTokens.rtk_cli_filtering || sourceTokens.cli_filtering || 0),
        sessionCliFiltering,
      ),
      // Estimated: RTK/lean-ctx run outside the request/response cycle, so
      // this isn't tied to one upstream request's exact price like the
      // other rows — see cli_filtering_savings_usd in the backend.
      usd: Number(sessionTokens.cli_filtering_savings_usd || 0),
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
      label: 'Response cache',
      tokens: Number(sourceTokens.semantic_cache || 0),
usd: Math.max(
  Number(cost.semantic_cache_savings_usd || 0),
  Number(sourceUsd.semantic_cache || 0),
),
    },
    {
      key: 'model_routing',
      label: 'Model routing',
      tokens: Number(sourceTokens.model_routing || 0),
usd: Math.max(
  Number(cost.model_routing_savings_usd || 0),
  Number(sourceUsd.model_routing || 0),
),
    },
    {
      key: 'normalization',
      label: 'Tokenizer normalization',
      tokens: Number(sourceTokens.normalization || 0),
      usd: Math.max(
        Number(cost.normalization_savings_usd || 0),
        Number(sourceUsd.normalization || 0),
      ),
    },
    {
      key: 'batch_routing',
      label: 'Batch routing',
      tokens: Number(sourceTokens.batch_routing || 0),
      usd: Math.max(
        Number(cost.batch_routing_savings_usd || 0),
        Number(sourceUsd.batch_routing || 0),
      ),
    },
    {
      key: 'memoization',
      label: 'Tool memoization',
      tokens: Number(sourceTokens.memoization || 0),
      usd: Math.max(
        Number(cost.memoization_savings_usd || 0),
        Number(sourceUsd.memoization || 0),
      ),
    },
    {
      key: 'output_optimization',
      label: 'Output optimization',
      tokens: Number(sourceTokens.output_optimization || 0),
      usd: Math.max(
        Number(cost.output_optimization_savings_usd || 0),
        Number(sourceUsd.output_optimization || 0),
      ),
    },
  ];
}

function buildClientRows(stats) {
  const cost = stats?.cost || stats?.summary?.cost || {};
  const byClient =
    cost?.savings_by_client || stats?.summary?.cost?.savings_by_client || stats?.savings_by_client || {};
  // Real per-client (tool/harness identity, e.g. "claude-code"/"opencode")
  // attribution, durable across restarts — see SavingsTracker.clients.
  // Takes priority over the legacy `byClient`/`byProject` shapes below,
  // neither of which is real client data: `byClient` is never populated
  // by the backend, and `byProject` is per-working-directory, not per-tool.
  const realByClient = stats?.persistent_savings?.clients || {};
  const byProject = stats?.savings?.per_project || stats?.persistent_savings?.projects || {};
  const { totalTokensSaved, totalSavingsUsd } = getSessionAttributionTotals(stats);
  const usdPerToken =
    totalTokensSaved > 0 && totalSavingsUsd > 0 ? totalSavingsUsd / totalTokensSaved : 0;
  const estimateUsd = (tokens, explicitUsd = 0) => (
    explicitUsd > 0 ? explicitUsd : tokens > 0 ? tokens * usdPerToken : 0
  );

  const realRows = Object.entries(realByClient)
    .map(([client, data]) => ({
      key: client,
      label: client,
      tokens: Number(data?.tokens_saved || data?.total_tokens_saved || 0),
      usd: estimateUsd(
        Number(data?.tokens_saved || data?.total_tokens_saved || 0),
        sumSavingsUsd(data),
      ),
      requests: Number(data?.requests || 0),
    }))
    .sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);

  if (realRows.length > 0) {
    return realRows;
  }

  const rows = Object.entries(byClient)
    .map(([client, data]) => ({
      key: client,
      label: client,
      tokens:
        Number(data?.total_tokens || 0)
        || Object.values(data?.tokens || {}).reduce((sum, value) => sum + Number(value || 0), 0),
      usd: estimateUsd(
        Number(data?.total_tokens || 0)
          || Object.values(data?.tokens || {}).reduce((sum, value) => sum + Number(value || 0), 0),
        Number(data?.total_usd || 0)
          || Object.values(data?.usd || {}).reduce((sum, value) => sum + Number(value || 0), 0),
      ),
      requests: Number(data?.requests || data?.request_count || 0),
    }))
    .sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);

  if (rows.length > 0) {
    return rows;
  }

  // Last resort: no identified-harness data at all (e.g. Codex-only
  // traffic, which the User-Agent classifier can't attribute yet).
  // Falling back to per-project data here is a known mislabeling — it's
  // directory names, not tool identity — but it's still more useful
  // than an empty panel.
  const projectRows = Object.entries(byProject)
    .map(([project, data]) => ({
      key: project,
      label: project,
      tokens: Number(data?.tokens_saved || data?.total_tokens_saved || 0),
      usd: estimateUsd(
        Number(data?.tokens_saved || data?.total_tokens_saved || 0),
        sumSavingsUsd(data),
      ),
      requests: Number(data?.requests || 0),
    }))
    .sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);

  if (projectRows.length > 0) {
    return projectRows;
  }

  const requestBuckets = new Map();
  for (const request of stats?.recent_requests || []) {
    const client =
      request?.client
      || request?.client_id
      || request?.tags?.client
      || request?.tags?.client_id;
    if (!client) {
      continue;
    }

    const current = requestBuckets.get(client) || {
      key: client,
      label: client,
      tokens: 0,
      usd: 0,
      requests: 0,
    };
    current.tokens += Number(request?.total_saved_tokens ?? request?.tokens_saved ?? 0);
    current.usd += Number(request?.total_savings_usd ?? request?.savings_usd ?? 0);
    current.requests += 1;
    requestBuckets.set(client, current);
  }

  return Array.from(requestBuckets.values())
    .sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);
}

function buildModelRows(stats) {
const cost = stats?.cost || stats?.summary?.cost || {};
const byModel = cost?.per_model || stats?.summary?.cost?.per_model || {};
const requestCountsByModel = stats?.requests?.by_model || {};

// Real per-model lifetime attribution, durable across restarts — see
// SavingsTracker.models. Takes priority over the fallbacks below, which
// either read a field the backend never populates (`byModel`) or bucket
// only the last ~10 requests (`stats.recent_requests`), a recency sample
// that made a brief burst of cheap-model traffic look bigger than a
// model that had actually run for far longer.
const realByModel = stats?.persistent_savings?.models || {};
const realRows = Object.entries(realByModel)
.map(([model, data]) => ({
key: model,
label: model,
tokens: Number(data?.tokens_saved || data?.total_tokens_saved || 0),
usd: sumSavingsUsd(data),
requests: Number(data?.requests || 0),
}))
.sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);

if (realRows.length > 0) {
return realRows;
}

const rows = Object.entries(byModel)
.map(([model, data]) => ({
key: model,
label: model,
tokens:
  Number(data?.tokens_saved || 0)
  || Number(data?.total_tokens_saved || 0)
  || Number(data?.total_tokens || 0),
usd:
  Number(data?.savings_usd || 0)
  || Number(data?.total_usd || 0),
requests: Number(requestCountsByModel[model] ?? data?.requests ?? data?.request_count ?? 0),
}))
.sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);

if (rows.length > 0) {
return rows;
}

const requestBuckets = new Map();
for (const request of stats?.recent_requests || []) {
const model = request?.model;
if (!model) {
  continue;
}

const current = requestBuckets.get(model) || {
  key: model,
  label: model,
  tokens: 0,
  usd: 0,
  requests: 0,
};
current.tokens += Number(request?.total_saved_tokens ?? request?.tokens_saved ?? 0);
current.usd += Number(request?.total_savings_usd ?? request?.savings_usd ?? 0);
current.requests += 1;
requestBuckets.set(model, current);
}

if (requestBuckets.size > 0) {
return Array.from(requestBuckets.values())
.sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);
}

const historyBuckets = new Map();
for (const entry of stats?.persistent_savings?.recent_history || []) {
const model = entry?.model;
if (!model || model === 'unknown') {
  continue;
}

const current = historyBuckets.get(model) || {
  key: model,
  label: model,
  tokens: 0,
  usd: 0,
  requests: 0,
};
current.tokens += Number(entry?.delta_tokens_saved ?? entry?.total_tokens_saved ?? 0);
current.usd += Number(
  entry?.delta_savings_usd
  ?? entry?.compression_savings_usd
  ?? 0,
);
current.requests += Number(entry?.requests ?? 1);
historyBuckets.set(model, current);
}

if (historyBuckets.size > 0) {
return Array.from(historyBuckets.values())
.sort((a, b) => b.tokens - a.tokens || b.requests - a.requests);
}

return Object.entries(stats?.requests?.by_model || {})
.map(([model, count]) => ({
key: model,
label: model,
tokens: 0,
usd: 0,
requests: Number(count || 0),
}))
.sort((a, b) => b.requests - a.requests);
}

function getRequestDirectSaved(request) {
  if (request?.tokens_saved == null) {
    return null;
  }

  return Number(request.tokens_saved || 0);
}

function getRequestIndirectSaved(request) {
  return (
    Number(request?.cache_saved_tokens || 0)
    + Number(request?.semantic_cache_saved_tokens || 0)
    + Number(request?.self_hosted_prefix_cache_saved_tokens || 0)
    + Number(request?.model_routing_saved_tokens || 0)
    + Number(request?.normalization_saved_tokens || 0)
    + Number(request?.batch_routing_saved_tokens || 0)
    + Number(request?.memoization_saved_tokens || 0)
    + Number(request?.output_optimization_saved_tokens || 0)
  );
}

function searchMatches(query, ...values) {
  const normalizedQuery = String(query ?? '').trim().toLowerCase();
  return normalizedQuery === ''
    || values.some((value) => String(value ?? '').toLowerCase().includes(normalizedQuery));
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

function buildTrendBuckets({
  period,
  referenceTime,
  historyData,
  recentRequestsSource,
  mode = 'historical',
}) {
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

  const series = mode === 'historical' ? historyData?.series : null;
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

function TrendChart({ stats, historyData, duration }) {
  const [referenceTime] = useState(() => Date.now());
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const recentRequestsSource = stats?.recent_requests;

  const mode = duration === 'session' ? 'session' : 'historical';
  const period = duration === 'daily' ? '24h' : duration === 'weekly' ? '7d' : '30d';

  const buckets = useMemo(
    () =>
      buildTrendBuckets({
        period,
        referenceTime,
        historyData,
        recentRequestsSource,
        mode,
      }),
    [historyData, mode, period, recentRequestsSource, referenceTime],
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
              const moveTrendFocus = (event) => {
                let nextIndex = null;
                if (event.key === 'ArrowRight') {
                  nextIndex = Math.min(index + 1, buckets.length - 1);
                }
                if (event.key === 'ArrowLeft') {
                  nextIndex = Math.max(index - 1, 0);
                }
                if (event.key === 'Home') {
                  nextIndex = 0;
                }
                if (event.key === 'End') {
                  nextIndex = buckets.length - 1;
                }
                if (nextIndex == null) {
                  return;
                }

                event.preventDefault();
                setHoveredIndex(nextIndex);
                const bars = event.currentTarget.parentElement?.querySelectorAll('.trend-bar');
                bars?.[nextIndex]?.focus();
              };

              return (
                <button
                  key={`${period}-${index}`}
                  className={`trend-bar ${isActive ? 'active' : ''}`}
                  style={{ height: `${scaledHeight}%` }}
                  title={`${bucket.label}: ${formatInteger(bucket.tokens)} tokens saved${bucket.hasRequestData ? ` across ${formatInteger(bucket.requests)} requests` : ''}${topModels.length > 0 ? ` · ${modelText}` : ''}`}
                  type="button"
                  aria-label={`${bucket.label}: ${formatInteger(bucket.tokens)} tokens saved, ${requestText}. ${modelText}`}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onFocus={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  onBlur={() => setHoveredIndex(null)}
                  onKeyDown={moveTrendFocus}
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

function AttributionMetricToggle({ metric, onChange }) {
  return (
    <div className="attribution-toolbar">
      <span className="attribution-toolbar-label">Show by</span>
      <div className="tab-group tab-group-compact">
        <button
          className={`tab-button tab-button-compact ${metric === 'tokens' ? 'active' : ''}`}
          onClick={() => onChange('tokens')}
        >
          Tokens
        </button>
        <button
          className={`tab-button tab-button-compact ${metric === 'usd' ? 'active' : ''}`}
          onClick={() => onChange('usd')}
        >
          Cost
        </button>
      </div>
    </div>
  );
}

function SavingsPanel({ title, eyebrow, rows, totalTokens, totalUsd, metric, emptyIcon, emptyTitle, emptyDescription, searchQuery = '' }) {
  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
  const visibleRows = normalizedQuery
    ? rows.filter((row) =>
        searchMatches(normalizedQuery, title, eyebrow, row.label, row.key, row.requests, row.tokens, row.usd))
    : rows;
  if (normalizedQuery !== '' && visibleRows.length === 0) {
    return null;
  }
  const byUsd = metric === 'usd';
  const total = byUsd ? totalUsd : totalTokens;
  const sortedRows = [...visibleRows].sort((a, b) => (byUsd ? b.usd - a.usd : b.tokens - a.tokens));

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
        </div>
      </div>

      {sortedRows.length === 0 ? (
        <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className="source-stack">
          {sortedRows.map((row) => {
            const value = byUsd ? row.usd : row.tokens;
            const percent = total > 0 ? (value / total) * 100 : 0;
            const requestsPart = row.requests > 0 ? ` · ${formatInteger(row.requests)} requests` : '';
            return (
              <div key={row.key} className="source-row">
                <div className="source-labels">
                  <div className="source-name">{row.label}</div>
                  <div className="source-meta">
                    {byUsd
                      ? `${formatCurrency(row.usd)}${requestsPart} · ${formatInteger(row.tokens)} tokens`
                      : `${formatInteger(row.tokens)} tokens${requestsPart} · ${formatCurrency(row.usd)}`}
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

function SavingsSplitPanel({ metric, created, observed, coverage }) {
  const byUsd = metric === 'usd';
  const createdValue = byUsd ? created.usd : created.tokens;
  const observedValue = byUsd ? observed.usd : observed.tokens;
  const total = createdValue + observedValue;
  const createdPercent = total > 0 ? (createdValue / total) * 100 : 0;
  const observedPercent = total > 0 ? (observedValue / total) * 100 : 0;
  const valueLabel = (value, usd) =>
    byUsd ? `${formatCurrency(usd)} · ${formatInteger(value)} tokens` : `${formatInteger(value)} tokens · ${formatCurrency(usd)}`;

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Savings mix</div>
          <h2>Cutctx share of attributed savings</h2>
          <p>Created savings come from Cutctx features. Observed savings come from upstream provider prompt-cache hits.</p>
          {!coverage.complete ? (
            <p className="metric-footnote">
              Partial historical coverage · {formatPercent(coverage.percent)} of requests attributed
            </p>
          ) : null}
        </div>
      </div>

      <div className="source-stack">
        {[
          {
            key: 'created',
            label: 'Created by Cutctx',
            percent: createdPercent,
            tokens: created.tokens,
            usd: created.usd,
          },
          {
            key: 'observed',
            label: 'Observed at provider',
            percent: observedPercent,
            tokens: observed.tokens,
            usd: observed.usd,
          },
        ].map((row) => (
          <div key={row.key} className="source-row">
            <div className="source-labels">
              <div className="source-name">{row.label}</div>
              <div className="source-meta">{valueLabel(row.tokens, row.usd)}</div>
            </div>

            <div className="source-bar-track">
              <div className="source-bar-fill" style={{ width: `${Math.min(100, row.percent)}%` }} />
            </div>
            <div className="source-percent">{formatPercent(row.percent)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}


const DECLINE_REASON_LABELS = {
  bypass_header: 'Bypass header',
  compression_disabled: 'Compression disabled',
  no_messages: 'No messages',
  license_denied: 'License denied',
  unknown: 'Unknown',
};

function extractDeclineReasons(stats) {
  const candidates = [
    stats?.compression_declined_total,
    stats?.summary?.compression_declined_total,
    stats?.compression?.declined_total,
    stats?.compression?.decline_reasons,
    stats?.savings?.decline_reasons,
    stats?.tokens?.compression_declined_total,
    stats?.summary?.compression_decline_reasons,
  ];

  const counts = new Map();

  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== 'object') {
      continue;
    }

    for (const [reason, value] of Object.entries(candidate)) {
      const count = Number(
        value && typeof value === 'object'
          ? value.count ?? value.total ?? value.value ?? value.tokens ?? 0
          : value,
      );

      if (Number.isFinite(count) && count > 0) {
        counts.set(reason, (counts.get(reason) || 0) + count);
      }
    }

    if (counts.size > 0) {
      break;
    }
  }

  return Array.from(counts.entries())
    .map(([reason, count]) => ({
      key: reason,
      reason,
      label: DECLINE_REASON_LABELS[reason] || reason.replace(/_/g, ' '),
      count,
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function CompressionDeclineStrip({ stats }) {
  const reasons = extractDeclineReasons(stats);
  if (reasons.length === 0) {
    return null;
  }

  return (
    <div className="decline-reason-strip" aria-label="Compression decline reasons">
      <div className="decline-reason-heading">
        <AlertTriangle size={14} />
        <span>Declines</span>
      </div>
      <div className="decline-reason-list">
        {reasons.map((reason) => (
          <span key={reason.key} className="decline-reason-chip" title={reason.reason}>
            <strong>{reason.label}</strong>
            <span>{formatInteger(reason.count)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function RouterDiagnosticsPanel({ routeCounts, searchQuery = '' }) {
  if (!routeCounts || Object.keys(routeCounts).length === 0) {
    return null;
  }

  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
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

  const panelMatches =
    normalizedQuery === '' ||
    ['router', 'diagnostics', 'bypassed', 'messages', 'compression', 'constraints'].some((value) =>
      value.includes(normalizedQuery),
    ) ||
    Object.keys(routeCounts).some((key) => String(key).toLowerCase().includes(normalizedQuery));

  const protectionVisible =
    protectionTotal > 0 &&
    (normalizedQuery === '' ||
      protectionKeys.some((key) =>
        searchMatches(normalizedQuery, key, routeCounts[key], 'protection', 'user', 'system'),
      ));
  const constraintVisible =
    constraintTotal > 0 &&
    (normalizedQuery === '' ||
      constraintKeys.some((key) =>
        searchMatches(normalizedQuery, key, routeCounts[key], 'constraint', 'savings', 'compression'),
      ));
  const formatVisible =
    formatTotal > 0 &&
    (normalizedQuery === '' ||
      formatKeys.some((key) =>
        searchMatches(normalizedQuery, key, routeCounts[key], 'format', 'analysis', 'tool'),
      ));

  if (normalizedQuery !== '' && !panelMatches && !protectionVisible && !constraintVisible && !formatVisible) {
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
        {protectionVisible && (
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

        {constraintVisible && (
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

        {formatVisible && (
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

function DiagnosticsPanel({ prefixCache, searchQuery = '' }) {
  const diagnostics = prefixCache?.diagnostics || {};
  const findings = Array.isArray(diagnostics.findings) && diagnostics.findings.length > 0
    ? diagnostics.findings
    : buildDiagnosticsFallback(prefixCache);
  const providerStates = Array.isArray(diagnostics.by_provider) ? diagnostics.by_provider : [];
  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
  const filteredFindings = normalizedQuery
    ? findings.filter((finding) =>
        searchMatches(
          normalizedQuery,
          finding.code,
          finding.title,
          finding.detail,
          finding.recommendation,
          finding.severity,
        ))
    : findings;
  const filteredProviders = normalizedQuery
    ? providerStates.filter((provider) =>
        searchMatches(
          normalizedQuery,
          provider.provider,
          provider.status,
          provider.reason,
          provider.hit_rate,
          provider.bust_count,
          provider.requests,
        ))
    : providerStates;

  if (normalizedQuery !== '' && filteredFindings.length === 0 && filteredProviders.length === 0) {
    return null;
  }

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Savings diagnosis</div>
          <h2>Why savings look low</h2>
          <p>These findings come from provider prompt-cache reads, writes, busts, and uncached volume.</p>
        </div>
      </div>

      {filteredFindings.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No diagnostics yet"
          description="Run a few repeated requests and the dashboard will explain where cache savings are being lost."
        />
      ) : (
        <div className="diagnostic-stack">
          {filteredFindings.map((finding) => (
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

          {filteredProviders.length > 0 ? (
            <div className="provider-status-grid">
              {filteredProviders.map((provider) => (
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
// Developer Note:
// This map intentionally rebrands internal compression strategy names to more
// user-friendly, UX-optimized marketing names. For example, 'drain3' is displayed
// as 'Log Structure Inference', and 'kompress' as 'Semantic Minification'.
// This progressive disclosure prevents users from needing to understand the underlying ML model names.
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
['stack_graph', 'Stack Graph'],
['usearch', 'Usearch'],
['model_routing', 'Model Routing'],
['audio', 'Audio (proxy)'],
]);

const FEATURE_ORDER = [
'knowledge_graph',
'log_template_mining',
'structural_diff_engine',
'text_compression_engine',
'multimodal_image',
'smart_crusher',
'kompress',
'html_extractor',
'voice_filler',
'code_ast',
'stack_graph',
'usearch',
'model_routing',
'audio',
];

function getStrategyLabel(key) {
return STRATEGY_DISPLAY.get(key) || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeFeatureAvailability(featureAvailability) {
if (!featureAvailability || Object.keys(featureAvailability).length === 0) {
  return [];
}

const normalized = new Map(
  FEATURE_ORDER.map((key) => [
    key,
    {
      available: false,
      reason: 'not_reported_by_runtime',
    },
  ]),
);

for (const [key, value] of Object.entries(featureAvailability)) {
  normalized.set(key, value || {});
}

return Array.from(normalized.entries());
}

function FeatureAvailabilityPanel({ featureAvailability, searchQuery = '' }) {
const entries = normalizeFeatureAvailability(featureAvailability);
if (entries.length === 0) {
  return null;
}
  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
  const filteredEntries = normalizedQuery
    ? entries.filter(([key, value]) =>
        searchMatches(
          normalizedQuery,
          key,
          getStrategyLabel(key),
          value?.reason,
          value?.install_hint,
          value?.compression,
          value?.available ? 'available' : 'missing',
        ))
    : entries;
  if (normalizedQuery !== '' && filteredEntries.length === 0) {
    return null;
  }
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
        {filteredEntries.map(([key, val]) => {
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

function GraphStatusPanel({ knowledgeGraph, searchQuery = '' }) {
  const status = knowledgeGraph?.status || 'disabled';
  const countsAvailable = Number(knowledgeGraph?.node_count || 0) > 0 || Number(knowledgeGraph?.edge_count || 0) > 0;
  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
  const panelText = [
    status,
    formatKnowledgeGraphStatus(knowledgeGraph),
    knowledgeGraph?.reason,
    knowledgeGraph?.version,
    knowledgeGraph?.available ? 'available' : 'unavailable',
    knowledgeGraph?.requested ? 'requested' : 'not requested',
    knowledgeGraph?.active ? 'active' : 'inactive',
    knowledgeGraph?.interceptor_registered ? 'registered' : 'not registered',
    knowledgeGraph?.node_count,
    knowledgeGraph?.edge_count,
  ];

  if (normalizedQuery !== '' && !panelText.some((value) => String(value ?? '').toLowerCase().includes(normalizedQuery))) {
    return null;
  }

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

function formatAutopilotTaskType(taskType) {
  switch (taskType) {
    case 'code':
      return 'Code';
    case 'search':
      return 'Search';
    case 'summarize':
      return 'Summaries';
    default:
      return 'General';
  }
}

function getAutopilotSummary(stats) {
  const autopilot = stats?.intelligence?.autopilot || {};
  const taskStats = autopilot.task_stats || {};
  const taskRows = Object.entries(autopilot.task_levels || {})
    .map(([taskType, level]) => ({
      taskType,
      label: formatAutopilotTaskType(taskType),
      level: Number(level || 0),
      signals: Number(taskStats?.[taskType]?.signal_count || 0),
      adjustments: Number(taskStats?.[taskType]?.adjustment_count || 0),
    }))
    .sort((a, b) => b.level - a.level || b.signals - a.signals || a.label.localeCompare(b.label));
  const recentLevels = Array.isArray(autopilot.recent_levels)
    ? autopilot.recent_levels
        .slice(-12)
        .map((entry) => Number(entry?.level || 0))
        .filter((value) => value > 0)
    : [];
  const recentAdjustments = Array.isArray(autopilot.recent_adjustments)
    ? autopilot.recent_adjustments
    : [];
  const latestAdjustment = recentAdjustments.at(-1) || null;

  return {
    enabled: Boolean(autopilot.enabled),
    minLevel: Number(autopilot.min_level || 1),
    maxLevel: Number(autopilot.max_level || 5),
    hysteresisWindow: Number(autopilot.hysteresis_window || 10),
    taskRows,
    recentLevels,
    latestAdjustment,
    totalSignals: taskRows.reduce((sum, row) => sum + row.signals, 0),
    totalAdjustments: taskRows.reduce((sum, row) => sum + row.adjustments, 0),
  };
}

function getPoliciesSummary(stats) {
  const policies = stats?.intelligence?.policies || {};
  const byAggressiveness = policies.by_aggressiveness || {};
  const byAlgorithmHint = policies.by_algorithm_hint || {};

  const aggressivenessLabelMap = {
    aggressive: 'Aggressive',
    balanced: 'Balanced',
    conservative: 'Conservative',
  };

  const formatAlgorithmLabel = (key) =>
    key
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');

  const aggressivenessRows = Object.entries(byAggressiveness)
    .map(([key, count]) => ({
      label: aggressivenessLabelMap[key] || formatAlgorithmLabel(key),
      count: Number(count || 0),
    }))
    .sort((a, b) => b.count - a.count);

  const algorithmRows = Object.entries(byAlgorithmHint)
    .map(([key, count]) => ({
      label: formatAlgorithmLabel(key),
      count: Number(count || 0),
    }))
    .sort((a, b) => b.count - a.count);

  return {
    count: Number(policies.count || 0),
    enabled: Boolean(policies.enabled),
    totalSamples: Number(policies.total_samples || 0),
    aggressivenessRows,
    algorithmRows,
  };
}

function AutopilotPanel({ autopilot, searchQuery = '' }) {
  const statusLabel = autopilot.enabled ? 'Active' : 'Disabled';
  const latestAdjustment = autopilot.latestAdjustment;
  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
  const panelText = [
    'autopilot',
    'compression autopilot',
    statusLabel,
    autopilot.enabled ? 'enabled' : 'disabled',
    autopilot.minLevel,
    autopilot.maxLevel,
    autopilot.hysteresisWindow,
    latestAdjustment?.task_type,
    latestAdjustment?.signal_kind,
    latestAdjustment?.old_level,
    latestAdjustment?.new_level,
    ...autopilot.taskRows.flatMap((row) => [row.taskType, row.label, row.level, row.signals, row.adjustments]),
  ];
  if (normalizedQuery !== '' && !panelText.some((value) => String(value ?? '').toLowerCase().includes(normalizedQuery))) {
    return null;
  }
  const filteredTaskRows =
    normalizedQuery === ''
      ? autopilot.taskRows
      : autopilot.taskRows.filter((row) =>
          searchMatches(normalizedQuery, row.taskType, row.label, row.level, row.signals, row.adjustments),
        );

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Intelligence</div>
          <h2>Compression autopilot</h2>
          <p>WS19 keeps a live per-task setpoint so compression can react instead of staying static.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
          <span className={`status-pill status-${autopilot.enabled ? 'ready' : 'disabled'}`}>{statusLabel}</span>
          <Sparkline values={autopilot.recentLevels} color="var(--accent-2)" />
        </div>

        {!autopilot.enabled ? (
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            Enable <code>CUTCTX_AUTOPILOT=1</code> to adapt compression aggressiveness from recent quality signals.
          </p>
        ) : filteredTaskRows.length === 0 ? (
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            Autopilot is enabled and waiting for enough request flow to establish task-level setpoints.
          </p>
        ) : (
          <>
            <div className="graphify-kv-grid">
              <div className="graphify-kv">
                <span>Signals</span>
                <strong>{formatInteger(autopilot.totalSignals)}</strong>
              </div>
              <div className="graphify-kv">
                <span>Adjustments</span>
                <strong>{formatInteger(autopilot.totalAdjustments)}</strong>
              </div>
              <div className="graphify-kv">
                <span>Level range</span>
                <strong>
                  L{autopilot.minLevel}-L{autopilot.maxLevel}
                </strong>
              </div>
              <div className="graphify-kv">
                <span>Hysteresis</span>
                <strong>{formatInteger(autopilot.hysteresisWindow)} clean reqs</strong>
              </div>
            </div>

            <div style={{ display: 'grid', gap: '10px' }}>
              {filteredTaskRows.map((row) => (
                <div
                  key={row.taskType}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, 1fr) auto',
                    gap: '12px',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div className="source-name">{row.label}</div>
                    <div className="source-meta">
                      {formatInteger(row.signals)} signals · {formatInteger(row.adjustments)} adjustments
                    </div>
                  </div>
                  <strong>L{row.level}</strong>
                </div>
              ))}
            </div>

            <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
              {latestAdjustment
                ? `Latest adjustment: ${formatAutopilotTaskType(latestAdjustment.task_type)} moved from L${latestAdjustment.old_level} to L${latestAdjustment.new_level} after a ${latestAdjustment.signal_kind.replace('_', ' ')} signal.`
                : 'No task setpoint changes have been required yet.'}
            </p>
          </>
        )}
      </div>
    </section>
  );
}

function PoliciesPanel({ policies, searchQuery = '' }) {
  const normalizedQuery = String(searchQuery ?? '').trim().toLowerCase();
  const filteredAggressivenessRows =
    normalizedQuery === ''
      ? policies.aggressivenessRows
      : policies.aggressivenessRows.filter((row) =>
          searchMatches(normalizedQuery, row.label, row.count, 'aggressiveness'),
        );
  const filteredAlgorithmRows =
    normalizedQuery === ''
      ? policies.algorithmRows
      : policies.algorithmRows.filter((row) => searchMatches(normalizedQuery, row.label, row.count, 'algorithm'));

  if (
    normalizedQuery !== '' &&
    filteredAggressivenessRows.length === 0 &&
    filteredAlgorithmRows.length === 0 &&
    !searchMatches(normalizedQuery, policies.enabled ? 'active' : 'disabled', policies.count, policies.totalSamples)
  ) {
    return null;
  }

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Intelligence</div>
          <h2>Learned policies</h2>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className={`status-pill status-${policies.enabled ? 'ready' : 'disabled'}`}>
            {policies.enabled ? 'Active' : 'Disabled'}
          </span>
        </div>

        {!policies.enabled ? (
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            No learned policies yet. Train with <code>cutctx policies train &lt;events.jsonl&gt;</code> or enable --watch mode.
          </p>
        ) : policies.count === 0 ? (
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            Policies are enabled but no policy definitions have been learned yet.
          </p>
        ) : (
          <>
            <div className="graphify-kv-grid">
              <div className="graphify-kv">
                <span>Policies</span>
                <strong>{formatInteger(policies.count)}</strong>
              </div>
              <div className="graphify-kv">
                <span>Total samples</span>
                <strong>{formatInteger(policies.totalSamples)}</strong>
              </div>
            </div>

            {filteredAggressivenessRows.length > 0 ? (
              <div style={{ display: 'grid', gap: '10px' }}>
                {filteredAggressivenessRows.map((row) => (
                  <div
                    key={row.label}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(0, 1fr) auto',
                      gap: '12px',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div className="source-name">{row.label}</div>
                      <div className="source-meta">aggressiveness</div>
                    </div>
                    <strong>{formatInteger(row.count)}</strong>
                  </div>
                ))}
              </div>
            ) : null}

            {filteredAlgorithmRows.length > 0 ? (
              <div style={{ display: 'grid', gap: '10px' }}>
                {filteredAlgorithmRows.map((row) => (
                  <div
                    key={row.label}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(0, 1fr) auto',
                      gap: '12px',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div className="source-name">{row.label}</div>
                      <div className="source-meta">algorithm hint</div>
                    </div>
                    <strong>{formatInteger(row.count)}</strong>
                  </div>
                ))}
              </div>
            ) : null}
          </>
        )}
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

const TRACE_SOURCE_LABELS = {
  cutctx_compression: 'Direct compression',
  provider_prompt_cache: 'Provider prompt cache',
  semantic_cache: 'Response cache',
  prefix_cache_self_hosted: 'Self-hosted prefix cache',
  model_routing: 'Model routing',
  tool_schema_compaction: 'Tool schema compaction',
  api_surface_slimming: 'API surface slimming',
  normalization: 'Tokenizer normalization',
  memoization: 'Tool memoization',
  output_optimization: 'Output optimization',
  batch_routing: 'Batch routing',
};

function formatTraceTimestamp(timestamp) {
  if (!timestamp) {
    return 'Unknown time';
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return String(timestamp);
  }
  return date.toLocaleString();
}

function formatTracePayload(payload) {
  if (payload == null) {
    return 'No payload captured.';
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

function RequestTraceInspector({ request, trace, loading, error, onClose }) {
  if (!request && !trace && !loading && !error) {
    return null;
  }

  const detail = trace?.trace || null;
  const sourceRows = Object.entries(detail?.compression?.savings_by_source_tokens || {})
    .map(([key, tokens]) => ({
      key,
      label: TRACE_SOURCE_LABELS[key] || key.replace(/_/g, ' '),
      tokens: Number(tokens || 0),
      usd: Number(detail?.compression?.savings_by_source_usd?.[key] || 0),
    }))
    .filter((row) => row.tokens > 0 || row.usd > 0)
    .sort((a, b) => b.tokens - a.tokens || b.usd - a.usd);

  return (
    <section className="panel request-trace-panel">
      <div className="request-trace-header">
        <div>
          <div className="eyebrow">Inspector</div>
          <h2>Request trace</h2>
          <p className="request-trace-subtitle">
            {request?.request_id || detail?.request_id || 'No request selected'}
            {request?.timestamp ? ` · ${formatTraceTimestamp(request.timestamp)}` : ''}
          </p>
        </div>
        <button className="ghost-button" onClick={onClose} type="button">
          Hide inspector
        </button>
      </div>

      {loading ? (
        <div className="skeleton" style={{ height: '320px', borderRadius: 'var(--radius-lg)' }} />
      ) : error ? (
        <div className="alert-card" role="alert">
          <span>Failed to load trace: {error}</span>
        </div>
      ) : detail ? (
        <>
          <div className="metric-grid metric-grid-four request-trace-metrics">
            <MetricCard
              icon={Layers}
              iconColor="blue"
              label="Requested model"
              value={detail.provider?.requested_model || '—'}
              footnote={
                detail.routing?.routed
                  ? `Actual: ${detail.provider?.actual_model || '—'}`
                  : 'No routing override'
              }
            />
            <MetricCard
              icon={PiggyBank}
              iconColor="green"
              label="Total saved"
              value={formatInteger(
                detail.compression?.total_saved_tokens || detail.compression?.tokens_saved || 0,
              )}
              footnote={`${formatMaybePercent(detail.compression?.total_savings_percent || detail.compression?.savings_percent)} reduction`}
            />
            <MetricCard
              icon={Coins}
              iconColor="amber"
              label="Request cost"
              value={formatCurrency(detail.cost?.request_cost_usd || 0)}
              footnote={`${formatCurrency(detail.routing?.saved_usd || 0)} routing savings observed`}
            />
            <MetricCard
              icon={Clock}
              iconColor="purple"
              label="Latency"
              value={`${Number(detail.latency?.total_ms || 0).toFixed(1)} ms`}
              footnote={`Compression ${Number(detail.latency?.optimization_ms || 0).toFixed(1)} ms`}
            />
          </div>

          <div className="overview-bottom-grid request-trace-grid">
            <div className="overview-side-stack">
              <section className="panel panel-compact">
                <div className="section-heading">
                  <div>
                    <div className="eyebrow">Routing</div>
                    <h2>Path taken</h2>
                    <p>
                      {detail.routing?.routed
                        ? `${detail.routing?.source_model || '—'} to ${detail.routing?.target_model || '—'}`
                        : 'The request stayed on its requested model.'}
                    </p>
                  </div>
                </div>
                <div className="diagnostic-stack">
                  <div className="diagnostic-row">
                    <span>Reason</span>
                    <strong>{detail.routing?.reason || '—'}</strong>
                  </div>
                  <div className="diagnostic-row">
                    <span>Decline reason</span>
                    <strong>{detail.compression?.decline_reason || '—'}</strong>
                  </div>
                  <div className="diagnostic-row">
                    <span>Fallback</span>
                    <strong>
                      {detail.fallback
                        ? detail.fallback?.attempted
                          ? `${detail.fallback?.provider || 'provider'} · ${detail.fallback?.reason || 'attempted'}`
                          : [
                              detail.fallback?.active_provider || detail.fallback?.provider,
                              detail.fallback?.circuit_breaker_state
                                ? `circuit ${detail.fallback.circuit_breaker_state}`
                                : null,
                              detail.fallback?.reason,
                            ]
                              .filter(Boolean)
                              .join(' · ') || 'Tracked only'
                        : 'Not used'}
                    </strong>
                  </div>
                  {detail.fallback?.circuit_breaker_retry_after_s != null ? (
                    <div className="diagnostic-row">
                      <span>Retry after</span>
                      <strong>{Number(detail.fallback.circuit_breaker_retry_after_s).toFixed(1)} s</strong>
                    </div>
                  ) : null}
                  {detail.fallback?.active_base_url ? (
                    <div className="diagnostic-row diagnostic-row-wrap">
                      <span>Active upstream</span>
                      <strong>{detail.fallback.active_base_url}</strong>
                    </div>
                  ) : null}
                  <div className="diagnostic-row diagnostic-row-wrap">
                    <span>Transforms</span>
                    <strong>
                      {(detail.compression?.transforms_applied || []).join(', ') || '—'}
                    </strong>
                  </div>
                </div>
              </section>

              <section className="panel panel-compact">
                <div className="section-heading">
                  <div>
                    <div className="eyebrow">Savings</div>
                    <h2>Source breakdown</h2>
                  </div>
                </div>
                {sourceRows.length === 0 ? (
                  <EmptyState
                    icon={Sparkles}
                    title="No trace attribution"
                    description="This request did not persist a source-level savings breakdown."
                  />
                ) : (
                  <div className="source-stack request-trace-source-stack">
                    {sourceRows.map((row) => (
                      <div key={row.key} className="source-row">
                        <div className="source-labels">
                          <div className="source-name">{row.label}</div>
                          <div className="source-meta">
                            {`${formatInteger(row.tokens)} tokens · ${formatCurrency(row.usd)}`}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            <div className="overview-side-stack">
              <section className="panel panel-compact">
                <div className="section-heading">
                  <div>
                    <div className="eyebrow">Payloads</div>
                    <h2>Before and after compression</h2>
                    <p>Compare the original request payload with the compressed upstream payload.</p>
                  </div>
                </div>
                <div className="request-trace-payload-grid">
                  <div className="request-trace-payload-card">
                    <div className="request-trace-payload-title">Original request</div>
                    <pre className="request-trace-payload-block">
                      {formatTracePayload(detail.messages?.request_messages)}
                    </pre>
                  </div>
                  <div className="request-trace-payload-card">
                    <div className="request-trace-payload-title">Compressed upstream payload</div>
                    <pre className="request-trace-payload-block">
                      {formatTracePayload(detail.messages?.compressed_messages)}
                    </pre>
                  </div>
                </div>
              </section>

              <section className="panel panel-compact">
                <div className="section-heading">
                  <div>
                    <div className="eyebrow">Metadata</div>
                    <h2>Headers and timings</h2>
                  </div>
                </div>
                <div className="diagnostic-stack">
                  <div className="diagnostic-row diagnostic-row-wrap">
                    <span>Turn ID</span>
                    <strong>{detail.turn_id || '—'}</strong>
                  </div>
                  <div className="diagnostic-row diagnostic-row-wrap">
                    <span>Tags</span>
                    <strong>
                      {Object.keys(detail.tags || {}).length > 0
                        ? Object.entries(detail.tags)
                            .map(([key, value]) => `${key}:${value}`)
                            .join(', ')
                        : '—'}
                    </strong>
                  </div>
                  <div className="diagnostic-row diagnostic-row-wrap">
                    <span>Pipeline timings</span>
                    <strong>
                      {Object.keys(detail.latency?.pipeline_timing || {}).length > 0
                        ? Object.entries(detail.latency.pipeline_timing)
                            .map(([key, value]) => `${key} ${Number(value || 0).toFixed(1)}ms`)
                            .join(', ')
                        : '—'}
                    </strong>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </>
      ) : (
        <EmptyState
          icon={Activity}
          title="Select a request"
          description="Choose a recent request to inspect routing, compression, and savings details."
        />
      )}
    </section>
  );
}

export default function Overview({ searchQuery = '' }) {
  const {
    stats,
    historyData,
    historyLoading,
    historyError,
    loading: contextLoading,
    error: contextError,
  } = useDashboardData();

  const [duration, setDuration] = useState('lifetime');
  const [durationData, setDurationData] = useState(null);
  const [durationLoading, setDurationLoading] = useState(true);
  const [durationError, setDurationError] = useState(null);
  const [attributionMetric, setAttributionMetric] = useState('tokens'); // 'tokens' | 'usd'
  const [selectedRequestId, setSelectedRequestId] = useState(null);
  const [requestTrace, setRequestTrace] = useState(null);
  const [requestTraceLoading, setRequestTraceLoading] = useState(false);
  const [requestTraceError, setRequestTraceError] = useState(null);

  useEffect(() => {
    let active = true;
    
    async function fetchData() {
      setDurationLoading(true);
      setDurationError(null);
      
      if (duration === 'session') {
        if (active) {
          setDurationData(
            historyData?.display_session
            || stats?.display_session
            || stats?.persistent_savings?.display_session
            || {},
          );
        }
        setDurationLoading(false);
        return;
      }
      
      if (duration === 'lifetime') {
        if (active) {
          setDurationData(historyData?.lifetime || stats?.persistent_savings?.lifetime || {});
        }
        setDurationLoading(false);
        return;
      }
      
      try {
        const period = await fetchPeriodStats(fetchDashboardJson, duration);
        if (active) {
          setDurationData(period);
        }
      } catch (err) {
        if (active) {
          setDurationError(err.message || String(err));
        }
      } finally {
        if (active) {
          setDurationLoading(false);
        }
      }
    }
    
    fetchData();
    
    return () => {
      active = false;
    };
  }, [duration, historyData, stats]);

  const loading = contextLoading || (durationLoading && !durationData);
  const error = contextError || durationError;
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const matchesQuery = (...values) =>
    normalizedQuery === '' ||
    values.some((value) => String(value ?? '').toLowerCase().includes(normalizedQuery));

  const summary = stats?.summary || {};
  const cost = stats?.cost || summary?.cost || {};
  const requests = stats?.requests || {};
  const tokens = stats?.tokens || {};
  const persistent = stats?.persistent_savings || {};
  const displaySession = persistent.display_session || {};
  const prefixCache = stats?.prefix_cache || {};
  const knowledgeGraph = stats?.knowledge_graph || {};
  const featureAvailability = stats?.feature_availability || {};
  const autopilot = getAutopilotSummary(stats);
  const policies = getPoliciesSummary(stats);
  const historyFreshnessLabel = historyData?.generated_at
    ? `History synced ${formatRelativeTime(historyData.generated_at)} from proxy`
    : 'Waiting for proxy history';
  const lifetimeSavingsUsd = getLifetimeTotalSavingsUsd(stats);
  const isLifetimeMode = duration === 'lifetime';
  const selectedRecord = duration === 'session'
    ? (historyData?.display_session || stats?.display_session || stats?.persistent_savings?.display_session || {})
    : duration === 'lifetime'
      ? (historyData?.lifetime || stats?.persistent_savings?.lifetime || {})
      : durationData || {};
  const tokensHeadline = { tokens: selectedRecord.tokens_saved || 0 };
  const requestsHeadline = { requests: selectedRecord.requests || 0 };
  const inputHeadline = { input: selectedRecord.total_input_tokens || 0 };
  const savingsHeadline = {
    key: duration,
    savingsUsd: getDurationSavingsUsd(selectedRecord),
    savingsObservedUsd:
      sumSavingsObservedUsd(selectedRecord)
      || Number(selectedRecord.compression_savings_observed_usd || 0),
    createdSavingsUsd: getCreatedObservedSavingsUsd(selectedRecord).createdUsd,
    createdSavingsObservedUsd:
      sumCreatedSavingsObservedUsd(selectedRecord)
      || Number(selectedRecord.compression_savings_observed_usd || 0),
    observedProviderSavingsUsd: getCreatedObservedSavingsUsd(selectedRecord).observedUsd,
    observedProviderSavingsObservedUsd: sumObservedProviderSavingsObservedUsd(selectedRecord),
  };

  const effectiveTokensSaved = Number(tokensHeadline.tokens || 0);
  const effectiveRequests = Number(requestsHeadline.requests || 0);
  const effectiveInputTokens = Number(inputHeadline.input || 0);
  const effectiveSavingsPercent = selectedRecord.savings_percent != null && !isLifetimeMode
    ? selectedRecord.savings_percent
    : (effectiveInputTokens > 0 || effectiveTokensSaved > 0 ? (effectiveTokensSaved / Math.max(effectiveInputTokens, effectiveTokensSaved)) * 100 : Number(tokens.savings_percent || displaySession.savings_percent || 0));

  const sessionCostWithoutCutctx = Number(summary?.cost?.without_cutctx_usd || 0);
  const sessionCostWithCutctx = Number(summary?.cost?.with_cutctx_usd || 0);
  const effectiveSavingsUsd = Number(savingsHeadline.savingsUsd || 0);
  const effectiveCreatedSavingsUsd = Number(savingsHeadline.createdSavingsUsd || 0);
  const effectiveObservedProviderSavingsUsd = Number(savingsHeadline.observedProviderSavingsUsd || 0);
  
  const moneySavedFootnote = isLifetimeMode ? (
    savingsHeadline.key === 'session'
      ? sessionCostWithoutCutctx > 0
        ? `from ${formatCurrency(sessionCostWithoutCutctx)} down to ${formatCurrency(sessionCostWithCutctx)}`
        : Number(cost.cache_savings_usd || 0) > 0
          ? 'Includes provider-cache savings in current session'
          : 'Current proxy-session savings'
      : savingsHeadline.key === 'display_session'
        ? 'Rolling session savings across created Cutctx savings plus observed provider cache'
        : lifetimeSavingsUsd > 0
          ? 'Lifetime savings split between created Cutctx savings and observed provider cache'
          : 'No cost data yet'
  ) : (
    duration === 'session' ? 'Current proxy-session savings' : `Estimated savings for the ${duration} period`
  );

  const requestsFootnote = isLifetimeMode ? (
    requestsHeadline.key === 'session'
      ? `${formatInteger(requests.failed || 0)} failed · ${formatInteger(requests.cached || 0)} cached`
      : requestsHeadline.key === 'display_session'
        ? 'Rolling session requests tracked'
        : effectiveRequests > 0
          ? 'Lifetime requests tracked'
          : 'No request data yet'
  ) : (
    `${formatInteger(effectiveRequests)} requests in the ${duration} period`
  );
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
      ? stats.recent_requests
      : persistentHistory;
  const filteredRecentRequests = normalizedQuery
    ? recentRequests.filter((request) =>
        matchesQuery(
          request?.request_id,
          request?.model,
          request?.client,
          request?.client_id,
          request?.provider,
          request?.status,
          request?.timestamp,
        )
      )
    : recentRequests;
  const traceableRequests = filteredRecentRequests.filter(
    (request) => request?.request_id && !request?.synthetic,
  );
  // A request summary can outlive the detailed trace (for example after a proxy
  // restart or log retention cleanup).  Do not automatically fetch the first
  // summary row: it creates a misleading 404 inspector before the user has
  // selected anything, and makes the inspector impossible to dismiss.
  const activeRequestId = selectedRequestId;
  const selectedRequest =
    traceableRequests.find((request) => request.request_id === activeRequestId) || null;

  useEffect(() => {
    if (!activeRequestId) {
      return undefined;
    }

    let active = true;

    async function fetchTrace() {
      setRequestTraceLoading(true);
      setRequestTraceError(null);

      try {
        const detail = await fetchDashboardJson(
          `/transformations/traces/${encodeURIComponent(activeRequestId)}`,
        );
        if (active) {
          setRequestTrace(detail);
        }
      } catch (err) {
        if (active) {
          setRequestTrace(null);
          setRequestTraceError(err.message || String(err));
        }
      } finally {
        if (active) {
          setRequestTraceLoading(false);
        }
      }
    }

    fetchTrace();

    return () => {
      active = false;
    };
  }, [activeRequestId]);

  const sourceRows = buildSourceRows(stats, selectedRecord, duration);
  const activeSourceRows = sourceRows.filter(isVisibleSavingsRow);
  const clientRows = duration === 'lifetime' ? buildClientRows(stats) : [];
  const activeClientRows = clientRows;
  const modelRows = duration === 'lifetime' ? buildModelRows(stats) : [];
  const activeModelRows = modelRows;
  const filteredSourceRows = normalizedQuery
    ? activeSourceRows.filter((row) => matchesQuery(row?.label, row?.key))
    : activeSourceRows;
  const filteredClientRows = normalizedQuery
    ? activeClientRows.filter((row) => matchesQuery(row?.label, row?.key))
    : activeClientRows;
  const filteredModelRows = normalizedQuery
    ? activeModelRows.filter((row) => matchesQuery(row?.label, row?.key))
    : activeModelRows;
  const totalSourceTokens =
    activeSourceRows.reduce((sum, row) => sum + row.tokens, 0) ||
    Number(tokens.total_before_compression || 0);
  const totalSourceUsd = activeSourceRows.reduce((sum, row) => sum + row.usd, 0);
  const sourceByUsd = attributionMetric === 'usd';
  const totalActiveSourceValue = sourceByUsd ? totalSourceUsd : totalSourceTokens;
  const totalClientTokens =
    activeClientRows.reduce((sum, row) => sum + row.tokens, 0) || totalSourceTokens;
  const totalModelTokens =
    activeModelRows.reduce((sum, row) => sum + row.tokens, 0) || totalSourceTokens;
  const totalClientUsd = activeClientRows.reduce((sum, row) => sum + row.usd, 0);
  const totalModelUsd = activeModelRows.reduce((sum, row) => sum + row.usd, 0);
  const activeCompressionPercent =
    tokens.active_savings_percent != null ? Number(tokens.active_savings_percent || 0) : null;
  const effectiveActiveCompressionPercent =
    activeCompressionPercent != null
      ? Math.max(activeCompressionPercent, effectiveSavingsPercent)
      : effectiveSavingsPercent;
  const proxyCompressionPercent =
    tokens.proxy_savings_percent != null ? Number(tokens.proxy_savings_percent || 0) : null;
  const directCompressionRow = sourceRows.find((row) => row.key === 'cutctx_compression');
  const toolSchemaRow = sourceRows.find((row) => row.key === 'tool_schema_compaction');
  const providerCacheRow = sourceRows.find((row) => row.key === 'provider_prompt_cache');
  const splitTokens = getCreatedObservedSavingsTokens(selectedRecord, activeSourceRows);
  const attributionCoverage = getAttributionCoverage(selectedRecord);
  const savingsSplit = {
    created: {
      tokens: splitTokens.createdTokens,
      usd: effectiveCreatedSavingsUsd,
    },
    observed: {
      tokens: splitTokens.observedTokens,
      usd: effectiveObservedProviderSavingsUsd,
    },
  };

  return (
    <section className="page-stack">
      <div className="tab-group" style={{ marginBottom: 'var(--space-md)' }}>
        <button 
          className={`tab-button ${duration === 'session' ? 'active' : ''}`}
          onClick={() => setDuration('session')}
        >
          <Activity size={16} /> Current Session
        </button>
        <button 
          className={`tab-button ${duration === 'daily' ? 'active' : ''}`}
          onClick={() => setDuration('daily')}
        >
          <Clock size={16} /> Last 24 Hours
        </button>
        <button 
          className={`tab-button ${duration === 'weekly' ? 'active' : ''}`}
          onClick={() => setDuration('weekly')}
        >
          <Calendar size={16} /> Last 7 Days
        </button>
        <button 
          className={`tab-button ${duration === 'monthly' ? 'active' : ''}`}
          onClick={() => setDuration('monthly')}
        >
          <Calendar size={16} /> Last 30 Days
        </button>
        <button 
          className={`tab-button ${duration === 'lifetime' ? 'active' : ''}`}
          onClick={() => setDuration('lifetime')}
        >
          <PiggyBank size={16} /> Lifetime (All Time)
        </button>
      </div>
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
            footnote={`${formatPercent(effectiveSavingsPercent)} total reduction`}
            sparkline={filteredRecentRequests.slice(0, 10).map((request) => getRequestTotalSaved(request))}
            sparklineColor="var(--accent)"
          />
          <MetricCard
            icon={Table2}
            iconColor="blue"
            label="Requests"
            value={formatInteger(effectiveRequests)}
            footnote={requestsFootnote}
          />
          <MetricCard
            icon={Layers}
            iconColor="purple"
            label="Active compression"
            value={
              Number.isFinite(effectiveActiveCompressionPercent)
                ? `${effectiveActiveCompressionPercent.toFixed(1)}%`
                : '—'
            }
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
            footnote={`${moneySavedFootnote} · ${formatCurrency(effectiveCreatedSavingsUsd)} created by Cutctx, ${formatCurrency(effectiveObservedProviderSavingsUsd)} observed at provider`}
          />
        </div>
      )}

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Trend</div>
            <h2>Savings over time</h2>
            <p>{historyFreshnessLabel}</p>
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
          <TrendChart key={duration} stats={stats} historyData={historyData} duration={duration} />
        )}
      </div>

        <div className="overview-bottom-grid">
        <div className="overview-side-stack">
          <SavingsSplitPanel
            metric={attributionMetric}
            created={savingsSplit.created}
            observed={savingsSplit.observed}
            coverage={attributionCoverage}
          />

          <CompressionDeclineStrip stats={stats} />

          <section className="panel panel-compact">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Attribution</div>
                <h2>Where savings come from</h2>
                <p>Created savings are broken out from provider-cache savings so the product contribution stays legible.</p>
              </div>
            </div>

            <AttributionMetricToggle metric={attributionMetric} onChange={setAttributionMetric} />

            {loading ? (
              <SkeletonBar />
            ) : filteredSourceRows.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title={normalizedQuery ? "No matching savings data" : "No savings data yet"}
                description={
                  normalizedQuery
                    ? "Try a broader search term to match source labels and keys."
                    : "Savings attribution will populate as requests flow through compression, cache, routing, and optimization channels."
                }
              />
            ) : (
              <>
                <div className="attribution-note">
                  <span>Direct compression: {formatInteger(directCompressionRow?.tokens || 0)} tokens</span>
                  <span>Tool schema: {formatInteger(toolSchemaRow?.tokens || 0)} tokens</span>
                  <span>Provider cache: {formatInteger(providerCacheRow?.tokens || 0)} observed tokens</span>
                </div>

                <div className="attribution-note">
                  <span>CLI filtering stays separate from proxy compression so RTK savings do not inflate Cutctx compression totals.</span>
                  <span>Response cache reflects exact-match reused responses, not semantic retrieval yet.</span>
                </div>

                <div className="source-stack">
                  {filteredSourceRows
                    .slice()
                    .sort((a, b) => (sourceByUsd ? b.usd - a.usd : b.tokens - a.tokens))
                    .map((row) => {
                    const value = sourceByUsd ? row.usd : row.tokens;
                    const percent = totalActiveSourceValue > 0 ? (value / totalActiveSourceValue) * 100 : 0;
                    return (
                      <div key={row.key} className="source-row">
                        <div className="source-labels">
                          <div className="source-name">{row.label}</div>
                          <div className="source-meta">
                            {sourceByUsd
                              ? `${formatCurrency(row.usd)} · ${formatInteger(row.tokens)} tokens`
                              : `${formatInteger(row.tokens)} tokens · ${formatCurrency(row.usd)}`}
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

          <SavingsPanel
            title="Savings by client"
            eyebrow="Attribution"
            rows={filteredClientRows}
            totalTokens={totalClientTokens}
            totalUsd={totalClientUsd}
            metric={attributionMetric}
            emptyIcon={Sparkles}
            emptyTitle="No client data yet"
            emptyDescription="Client-level attribution appears once requests include client tags."
            searchQuery={normalizedQuery}
          />

          <SavingsPanel
            title="Savings by model"
            eyebrow="Attribution"
            rows={filteredModelRows}
            totalTokens={totalModelTokens}
            totalUsd={totalModelUsd}
            metric={attributionMetric}
            emptyIcon={Layers}
            emptyTitle="No model data yet"
            emptyDescription="Model-level attribution appears once requests flow through the proxy."
            searchQuery={normalizedQuery}
          />

          <DiagnosticsPanel prefixCache={prefixCache} searchQuery={normalizedQuery} />
          <RouterDiagnosticsPanel routeCounts={stats?.router?.route_counts} searchQuery={normalizedQuery} />
          <GraphStatusPanel knowledgeGraph={knowledgeGraph} searchQuery={normalizedQuery} />
          <FeatureAvailabilityPanel featureAvailability={featureAvailability} searchQuery={normalizedQuery} />
          <AutopilotPanel autopilot={autopilot} searchQuery={normalizedQuery} />
          <PoliciesPanel policies={policies} searchQuery={normalizedQuery} />
        </div>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Activity</div>
              <h2>Recent requests</h2>
            </div>
          </div>

          {loading ? (
            <div className="skeleton" style={{ height: '260px', borderRadius: 'var(--radius-lg)' }} />
          ) : filteredRecentRequests.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title={normalizedQuery ? "No matching requests" : "No requests yet"}
              description={
                normalizedQuery
                  ? "Try a broader search term to match models, request IDs, clients, providers, or timestamps."
                  : "Start using the proxy to see request activity here."
              }
            />
          ) : (
            <div className="table-shell request-table-shell">
              <table className="request-table">
                  <thead>
                    <tr>
                      <th>Routed model</th>
                      <th>Input</th>
                      <th>Saved</th>
                      <th>Proxy</th>
                    <th>Cache</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRecentRequests.map((request, index) => {
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
                          {request.request_id && !request.synthetic ? (
                            <button
                              className={`request-row-button ${activeRequestId === request.request_id ? 'active' : ''}`}
                              onClick={() => setSelectedRequestId(request.request_id)}
                              type="button"
                            >
                              <span>{request.model || '—'}</span>
                              <ArrowUpRight size={14} />
                            </button>
                          ) : (
                            request.model || '—'
                          )}
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
                  Saved = direct compression plus tracked created savings and observed provider-cache savings.
                  Proxy = tokens Cutctx compressed. Cache = provider prompt-cache or Cutctx response-cache savings.
                  Model = the routed model CutCtx observed on the request.
                </div>
              </div>
          )}

          <RequestTraceInspector
            request={selectedRequest}
            trace={activeRequestId ? requestTrace : null}
            loading={activeRequestId ? requestTraceLoading : false}
            error={activeRequestId ? requestTraceError : null}
            onClose={() => setSelectedRequestId(null)}
          />

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
