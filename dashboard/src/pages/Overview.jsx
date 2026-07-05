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

const LIFETIME_SAVINGS_SOURCES = [
  ['compression_savings_usd', 'cutctx_compression'],
  ['cache_savings_usd', 'provider_prompt_cache'],
  ['semantic_cache_savings_usd', 'semantic_cache'],
  ['self_hosted_prefix_cache_savings_usd', 'prefix_cache_self_hosted'],
  ['model_routing_savings_usd', 'model_routing'],
  ['tool_schema_compaction_savings_usd', 'tool_schema_compaction'],
  ['api_surface_slimming_savings_usd', 'api_surface_slimming'],
  ['normalization_savings_usd', 'normalization'],
  ['batch_routing_savings_usd', 'batch_routing'],
  ['memoization_savings_usd', 'memoization'],
  ['output_optimization_savings_usd', 'output_optimization'],
];

function sumSavingsUsd(record) {
  return LIFETIME_SAVINGS_SOURCES.reduce(
    (sum, [key]) => sum + Number(record?.[key] || 0),
    0,
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
      + apiSurfaceUsd,
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

function buildSourceRows(stats) {
const cost = stats?.cost || stats?.summary?.cost || {};
const costSavingsBySource = cost?.savings_by_source || {};
const sourceTokens = {
  ...(costSavingsBySource?.tokens || {}),
  ...(stats?.savings_by_source?.tokens || {}),
};
const sourceUsd = {
  ...(costSavingsBySource?.usd || {}),
  ...(stats?.savings_by_source?.usd || {}),
};
const costBreakdown = cost?.breakdown || {};
const sessionTokens = stats?.tokens || {};
const prefixTotals = stats?.prefix_cache?.totals || {};

  const sessionCompression = Number(sessionTokens.proxy_compression_saved || 0);
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
  const byProject = stats?.savings?.per_project || stats?.persistent_savings?.projects || {};
  const { totalTokensSaved, totalSavingsUsd } = getSessionAttributionTotals(stats);
  const usdPerToken =
    totalTokensSaved > 0 && totalSavingsUsd > 0 ? totalSavingsUsd / totalTokensSaved : 0;
  const estimateUsd = (tokens, explicitUsd = 0) => (
    explicitUsd > 0 ? explicitUsd : tokens > 0 ? tokens * usdPerToken : 0
  );

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
{formatInteger(row.tokens)} tokens
{row.requests > 0 ? ` · ${formatInteger(row.requests)} requests` : ''}
· {formatCurrency(row.usd)}
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

function FeatureAvailabilityPanel({ featureAvailability }) {
const entries = normalizeFeatureAvailability(featureAvailability);
if (entries.length === 0) {
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

function AutopilotPanel({ autopilot }) {
  const statusLabel = autopilot.enabled ? 'Active' : 'Disabled';
  const latestAdjustment = autopilot.latestAdjustment;

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
        ) : autopilot.taskRows.length === 0 ? (
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
              {autopilot.taskRows.map((row) => (
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

function PoliciesPanel({ policies }) {
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

            {policies.aggressivenessRows.length > 0 ? (
              <div style={{ display: 'grid', gap: '10px' }}>
                {policies.aggressivenessRows.map((row) => (
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

            {policies.algorithmRows.length > 0 ? (
              <div style={{ display: 'grid', gap: '10px' }}>
                {policies.algorithmRows.map((row) => (
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

export default function Overview() {
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

  useEffect(() => {
    let active = true;
    
    async function fetchData() {
      setDurationLoading(true);
      setDurationError(null);
      
      if (duration === 'session') {
        if (historyData?.display_session) {
          setDurationData(historyData.display_session);
        }
        setDurationLoading(false);
        return;
      }
      
      if (duration === 'lifetime') {
        if (historyData?.lifetime) {
          setDurationData(historyData.lifetime);
        }
        setDurationLoading(false);
        return;
      }
      
      try {
        const data = await fetchDashboardJson(`/stats-history?series=${duration}`);
        if (active) {
          setDurationData(data?.history_summary || data?.lifetime || null);
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
  }, [duration, historyData]);

  const loading = contextLoading || (durationLoading && !durationData);
  const error = contextError || durationError;

  const summary = stats?.summary || {};
  const cost = stats?.cost || summary?.cost || {};
  const requests = stats?.requests || {};
  const tokens = stats?.tokens || {};
  const persistent = stats?.persistent_savings || {};
  const displaySession = persistent.display_session || {};
  const lifetime = persistent.lifetime || {};
  const prefixCache = stats?.prefix_cache || {};
  const knowledgeGraph = stats?.knowledge_graph || {};
  const featureAvailability = stats?.feature_availability || {};
  const autopilot = getAutopilotSummary(stats);
  const policies = getPoliciesSummary(stats);
  const historyFreshnessLabel = historyData?.generated_at
    ? `History synced ${formatRelativeTime(historyData.generated_at)} from proxy`
    : 'Waiting for proxy history';
  const sessionTokensSaved = Number(tokens.saved || 0);
  const sessionRequests = Number(requests.total || 0);
  const sessionSavingsUsd = getSessionSavingsUsd(stats);
  const displaySessionTokensSaved = Number(displaySession.tokens_saved || 0);
  const displaySessionRequests = Number(displaySession.requests || 0);
  const displaySessionSavingsUsd = sumSavingsUsd(displaySession);
  const lifetimeTokensSaved = Number(lifetime.tokens_saved || 0);
  const sessionInputTokens = Math.max(
    Number(tokens.total_before_compression || 0),
    Number(tokens.input || 0),
  );
  const displaySessionInputTokens = Number(displaySession.total_input_tokens || 0);
  const lifetimeInputTokens = Number(lifetime.total_input_tokens || 0);
  const lifetimeSavingsUsd = getLifetimeTotalSavingsUsd(stats);
  const headlineSources = [
    {
      key: 'session',
      tokens: sessionTokensSaved,
      requests: sessionRequests,
      input: sessionInputTokens,
      savingsUsd: sessionSavingsUsd,
    },
    {
      key: 'display_session',
      tokens: displaySessionTokensSaved,
      requests: displaySessionRequests,
      input: displaySessionInputTokens,
      savingsUsd: displaySessionSavingsUsd,
    },
    {
      key: 'lifetime',
      tokens: lifetimeTokensSaved,
      requests: Number(lifetime.requests || 0),
      input: lifetimeInputTokens,
      savingsUsd: lifetimeSavingsUsd,
    },
  ];
  const pickHeadlineSource = (field) =>
    headlineSources.reduce((best, candidate) =>
      Number(candidate[field] || 0) >= Number(best[field] || 0) ? candidate : best,
    );

  const isLifetimeMode = duration === 'lifetime';

  const tokensHeadline = isLifetimeMode ? pickHeadlineSource('tokens') : { tokens: durationData?.tokens_saved || 0 };
  const requestsHeadline = isLifetimeMode ? pickHeadlineSource('requests') : { requests: durationData?.requests || 0 };
  const inputHeadline = isLifetimeMode ? pickHeadlineSource('input') : { input: durationData?.total_input_tokens || 0 };
  const savingsHeadline = isLifetimeMode ? pickHeadlineSource('savingsUsd') : { savingsUsd: durationData?.compression_savings_usd || 0 };

  const effectiveTokensSaved = Number(tokensHeadline.tokens || 0);
  const effectiveRequests = Number(requestsHeadline.requests || 0);
  const effectiveInputTokens = Number(inputHeadline.input || 0);
  const effectiveSavingsPercent = durationData?.savings_percent != null && !isLifetimeMode
    ? durationData.savings_percent 
    : (effectiveInputTokens > 0 || effectiveTokensSaved > 0 ? (effectiveTokensSaved / Math.max(effectiveInputTokens, effectiveTokensSaved)) * 100 : Number(tokens.savings_percent || displaySession.savings_percent || 0));

  const sessionCostWithoutCutctx = Number(summary?.cost?.without_cutctx_usd || 0);
  const sessionCostWithCutctx = Number(summary?.cost?.with_cutctx_usd || 0);
  const effectiveSavingsUsd = Number(savingsHeadline.savingsUsd || 0);
  
  const moneySavedFootnote = isLifetimeMode ? (
    savingsHeadline.key === 'session'
      ? sessionCostWithoutCutctx > 0
        ? `from ${formatCurrency(sessionCostWithoutCutctx)} down to ${formatCurrency(sessionCostWithCutctx)}`
        : Number(cost.cache_savings_usd || 0) > 0
          ? 'Includes provider-cache savings in current session'
          : 'Current proxy-session savings'
      : savingsHeadline.key === 'display_session'
        ? 'Rolling session savings across compression, cache, routing, and optimization'
        : lifetimeSavingsUsd > 0
          ? 'Lifetime savings across compression, cache, routing, and optimization'
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

  const sourceRows = buildSourceRows(stats);
  const activeSourceRows = sourceRows.filter((row) => row.tokens > 0);
  const clientRows = buildClientRows(stats);
  const activeClientRows = clientRows;
  const modelRows = buildModelRows(stats);
  const activeModelRows = modelRows;
  const totalSourceTokens =
    activeSourceRows.reduce((sum, row) => sum + row.tokens, 0) ||
    Number(tokens.total_before_compression || 0);
  const totalClientTokens =
    activeClientRows.reduce((sum, row) => sum + row.tokens, 0) || totalSourceTokens;
  const totalModelTokens =
    activeModelRows.reduce((sum, row) => sum + row.tokens, 0) || totalSourceTokens;
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
            sparkline={recentRequests.slice(0, 10).map((request) => getRequestTotalSaved(request))}
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
            footnote={moneySavedFootnote}
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
          <section className="panel panel-compact">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Attribution</div>
                <h2>Where savings come from</h2>
                <p>Compression, cache, routing, and optimization passes are split out so total savings stays legible.</p>
              </div>
            </div>

            {loading ? (
              <SkeletonBar />
            ) : activeSourceRows.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No savings data yet"
                description="Savings attribution will populate as requests flow through compression, cache, routing, and optimization channels."
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

          <SavingsPanel
            title="Savings by client"
            eyebrow="Attribution"
            rows={activeClientRows}
            totalTokens={totalClientTokens}
            emptyIcon={Sparkles}
            emptyTitle="No client data yet"
            emptyDescription="Client-level attribution appears once requests include client tags."
          />

          <SavingsPanel
            title="Savings by model"
            eyebrow="Attribution"
            rows={activeModelRows}
            totalTokens={totalModelTokens}
            emptyIcon={Layers}
            emptyTitle="No model data yet"
            emptyDescription="Model-level attribution appears once requests flow through the proxy."
          />

          <DiagnosticsPanel prefixCache={prefixCache} />
          <RouterDiagnosticsPanel routeCounts={stats?.router?.route_counts} />
          <GraphStatusPanel knowledgeGraph={knowledgeGraph} />
          <FeatureAvailabilityPanel featureAvailability={featureAvailability} />
          <AutopilotPanel autopilot={autopilot} />
          <PoliciesPanel policies={policies} />
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
          ) : recentRequests.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No requests yet"
              description="Start using the proxy to see request activity here."
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
                  Saved = direct compression plus tracked cache, routing, and optimization savings.
                  Proxy = tokens Cutctx compressed. Cache = provider prompt-cache or semantic-cache savings.
                  Model = the routed model CutCtx observed on the request.
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
