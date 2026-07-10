import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Activity,
  Calendar,
  Clock,
  Coins,
  Layers,
  PiggyBank,
  Sparkles,
} from 'lucide-react';
import { fetchPeriodStats } from '../lib/period-stats';
import {
  getAttributionCoverage,
  getCreatedObservedSavingsTokens,
  getCreatedObservedSavingsUsd,
  getCreatedSavingsRate,
  isVisibleSavingsRow,
} from '../lib/savings-sources';
import {
  formatCurrency,
  formatInteger,
  formatNumber,
  formatPercent,
} from '../lib/format';
import { fetchDashboardJson, useDashboardData } from '../lib/use-dashboard-data';

const SOURCE_LABELS = {
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

function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton skeleton-line skeleton-line-sm" />
      <div className="skeleton skeleton-value" />
      <div className="skeleton skeleton-line skeleton-line-lg" />
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

function MetricCard({ icon: Icon, iconColor, label, value, footnote }) {
  return (
    <div className="metric-card">
      <div className="metric-header">
        <div className="metric-icon" style={{ color: `var(--${iconColor})` }}>
          <Icon size={18} />
        </div>
        <div className="metric-label">{label}</div>
      </div>
      <div className="metric-value">{value}</div>
      {footnote ? <div className="metric-footnote">{footnote}</div> : null}
    </div>
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

function SavingsPanel({
  title,
  eyebrow,
  rows,
  totalTokens,
  totalUsd,
  metric,
  emptyIcon,
  emptyTitle,
  emptyDescription,
}) {
  const byUsd = metric === 'usd';
  const total = byUsd ? totalUsd : totalTokens;
  const visibleRows = rows.filter(isVisibleSavingsRow);
  const sortedRows = [...visibleRows].sort((a, b) => (byUsd ? b.usd - a.usd : b.tokens - a.tokens));

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
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
            return (
              <div key={row.key} className="source-row">
                <div className="source-labels">
                  <div className="source-name">{row.label}</div>
                  <div className="source-meta">
                    {byUsd
                      ? `${formatCurrency(row.usd)} · ${formatInteger(row.tokens)} tokens`
                      : `${formatInteger(row.tokens)} tokens · ${formatCurrency(row.usd)}`}
                  </div>
                </div>
                <div className="source-bar-track">
                  <div className="source-bar-fill" style={{ width: `${Math.min(100, percent)}%` }} />
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

function SavingsMixPanel({ metric, created, observed, note, coverage }) {
  const byUsd = metric === 'usd';
  const createdValue = byUsd ? created.usd : created.tokens;
  const observedValue = byUsd ? observed.usd : observed.tokens;
  const total = createdValue + observedValue;
  const rows = [
    {
      key: 'created',
      label: 'Created by Cutctx',
      tokens: created.tokens,
      usd: created.usd,
      percent: total > 0 ? (createdValue / total) * 100 : 0,
    },
    {
      key: 'observed',
      label: 'Observed at provider',
      tokens: observed.tokens,
      usd: observed.usd,
      percent: total > 0 ? (observedValue / total) * 100 : 0,
    },
  ];

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Savings mix</div>
          <h2>Cutctx share of attributed savings</h2>
          <p>{note}</p>
          {!coverage.complete ? (
            <p className="metric-footnote">
              Partial historical coverage · {formatPercent(coverage.percent)} of requests attributed
            </p>
          ) : null}
        </div>
      </div>

      <div className="source-stack">
        {rows.map((row) => (
          <div key={row.key} className="source-row">
            <div className="source-labels">
              <div className="source-name">{row.label}</div>
              <div className="source-meta">
                {byUsd
                  ? `${formatCurrency(row.usd)} · ${formatInteger(row.tokens)} tokens`
                  : `${formatInteger(row.tokens)} tokens · ${formatCurrency(row.usd)}`}
              </div>
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

function mapAttributionRows(entries) {
  return Object.entries(entries || {})
    .map(([key, data]) => ({
      key,
      label: key,
      tokens: Number(data?.tokens_saved || data?.total_tokens_saved || 0),
      usd: Math.max(
        Number(data?.total_savings_usd || 0),
        Number(data?.compression_savings_usd || 0),
      ),
    }))
    .filter((row) => row.tokens > 0 || row.usd > 0)
    .sort((a, b) => b.tokens - a.tokens || b.usd - a.usd);
}

function buildSourceRows(duration, stats, historyData) {
  if (duration !== 'session' && duration !== 'lifetime') {
    return [];
  }

  const statsCost = stats?.cost || stats?.summary?.cost || {};
  const statsSource = stats?.savings_by_source || statsCost?.savings_by_source || {};
  const record = duration === 'session'
    ? (historyData?.display_session || stats?.display_session || {})
    : (historyData?.lifetime || {});
  const sessionScoped = duration === 'session';
  const sourceUsd = sessionScoped ? (record.savings_by_source_usd || {}) : (statsSource?.usd || {});
  const sourceTokens = sessionScoped ? (record.savings_by_source_tokens || {}) : (statsSource?.tokens || {});
  const sourceFlags = sessionScoped ? {} : (statsSource?.active || statsSource?.enabled || {});

  return [
    ['compression_savings_usd', 'cutctx_compression'],
    ['cache_savings_usd', 'provider_prompt_cache'],
    ['semantic_cache_savings_usd', 'semantic_cache'],
    ['self_hosted_prefix_cache_savings_usd', 'prefix_cache_self_hosted'],
    ['model_routing_savings_usd', 'model_routing'],
    ['tool_schema_compaction_savings_usd', 'tool_schema_compaction'],
    ['api_surface_slimming_savings_usd', 'api_surface_slimming'],
    ['normalization_savings_usd', 'normalization'],
    ['memoization_savings_usd', 'memoization'],
    ['output_optimization_savings_usd', 'output_optimization'],
    ['batch_routing_savings_usd', 'batch_routing'],
  ]
    .map(([field, sourceKey]) => ({
      key: sourceKey,
      label: SOURCE_LABELS[sourceKey] || sourceKey,
      tokens: Number(sourceTokens[sourceKey] || 0),
      usd: Math.max(Number(record?.[field] || 0), Number(sourceUsd[sourceKey] || 0)),
      active: Boolean(sourceFlags[sourceKey]),
    }))
    .filter(isVisibleSavingsRow);
}

export default function Savings() {
  const {
    stats,
    historyData,
    loading: contextLoading,
    error: contextError,
  } = useDashboardData();
  const [duration, setDuration] = useState('lifetime');
  const [attributionMetric, setAttributionMetric] = useState('tokens');
  const [durationData, setDurationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);

      if (duration === 'session') {
        if (active) {
          setDurationData(
            historyData?.display_session
            || stats?.display_session
            || stats?.persistent_savings?.display_session
            || {},
          );
          setLoading(false);
        }
        return;
      }

      if (duration === 'lifetime') {
        if (active) {
          setDurationData(historyData?.lifetime || stats?.persistent_savings?.lifetime || {});
          setLoading(false);
        }
        return;
      }

      try {
        const period = await fetchPeriodStats(fetchDashboardJson, duration);
        if (active) {
          setDurationData(period);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError.message || String(loadError));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [duration, historyData, stats]);

  const sourceRows = useMemo(
    () => buildSourceRows(duration, stats, historyData),
    [duration, stats, historyData],
  );

  const activeRecord = duration === 'session'
    ? (historyData?.display_session || stats?.display_session || stats?.persistent_savings?.display_session || {})
    : duration === 'lifetime'
      ? (historyData?.lifetime || stats?.persistent_savings?.lifetime || {})
      : durationData || {};
  const sourceRowsTotalTokens = sourceRows.reduce((sum, row) => sum + row.tokens, 0);
  const sourceRowsTotalUsd = sourceRows.reduce((sum, row) => sum + row.usd, 0);
  const inputTokens = Number(activeRecord?.total_input_tokens || 0);

  const savingsFallbackRecord = duration === 'lifetime' ? historyData?.lifetime || null : null;
  const { createdUsd: createdSavingsUsd, observedUsd: observedProviderSavingsUsd } =
    getCreatedObservedSavingsUsd(activeRecord, savingsFallbackRecord);

  const { createdTokens: createdSavingsTokens, observedTokens: observedProviderSavingsTokens } =
    getCreatedObservedSavingsTokens(activeRecord, sourceRows);
  const attributionCoverage = getAttributionCoverage(activeRecord);
  const createdSavingsRate = getCreatedSavingsRate(createdSavingsTokens, inputTokens);
  const combinedSavingsUsd = createdSavingsUsd + observedProviderSavingsUsd;

  const modelRows = duration === 'lifetime'
    ? mapAttributionRows(historyData?.models)
    : mapAttributionRows(activeRecord?.models);
  const clientRows = duration === 'lifetime' ? mapAttributionRows(historyData?.clients) : [];

  const totalModelTokens = modelRows.reduce((sum, row) => sum + row.tokens, 0);
  const totalModelUsd = modelRows.reduce((sum, row) => sum + row.usd, 0);
  const totalClientTokens = clientRows.reduce((sum, row) => sum + row.tokens, 0);
  const totalClientUsd = clientRows.reduce((sum, row) => sum + row.usd, 0);

  const sourcePanelDescription = duration === 'session' || duration === 'lifetime'
    ? 'Direct compression, response cache, routing, and cache surfaces split into their own lines.'
    : 'Source-level breakdown is available for session and lifetime views. Rolling windows keep the headline split but not per-source tokens yet.';

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <h1>Savings & Attribution</h1>
          <p>Separate value Cutctx creates from value merely observed at the upstream provider.</p>
        </div>
      </div>

      <div className="tab-group" style={{ marginBottom: 'var(--space-md)' }}>
        <button className={`tab-button ${duration === 'session' ? 'active' : ''}`} onClick={() => setDuration('session')}>
          <Activity size={16} />
          Current Session
        </button>
        <button className={`tab-button ${duration === 'daily' ? 'active' : ''}`} onClick={() => setDuration('daily')}>
          <Clock size={16} />
          Last 24 Hours
        </button>
        <button className={`tab-button ${duration === 'weekly' ? 'active' : ''}`} onClick={() => setDuration('weekly')}>
          <Calendar size={16} />
          Last 7 Days
        </button>
        <button className={`tab-button ${duration === 'monthly' ? 'active' : ''}`} onClick={() => setDuration('monthly')}>
          <Calendar size={16} />
          Last 30 Days
        </button>
        <button className={`tab-button ${duration === 'lifetime' ? 'active' : ''}`} onClick={() => setDuration('lifetime')}>
          <Sparkles size={16} />
          Lifetime
        </button>
      </div>

      {error || contextError ? (
        <div className="alert-card" role="alert">
          <span>Failed to load data: {error || contextError}</span>
        </div>
      ) : null}

      {(loading || contextLoading) && !durationData ? (
        <div className="metric-grid metric-grid-four">
          {Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} />)}
        </div>
      ) : (
        <>
          <div className="metric-grid metric-grid-four">
            <MetricCard
              icon={PiggyBank}
              iconColor="green"
              label="Cutctx-created savings"
              value={formatCurrency(createdSavingsUsd)}
              footnote={`${formatPercent(createdSavingsRate)} incremental reduction · ${formatNumber(createdSavingsTokens)} attributed tokens`}
            />
            <MetricCard
              icon={Coins}
              iconColor="amber"
              label="Provider savings preserved"
              value={formatCurrency(observedProviderSavingsUsd)}
              footnote={`${formatInteger(observedProviderSavingsTokens)} provider prompt-cache tokens observed`}
            />
            <MetricCard
              icon={Sparkles}
              iconColor="blue"
              label="Combined optimized savings"
              value={formatCurrency(combinedSavingsUsd)}
              footnote="Cutctx-created plus provider-native value"
            />
            <MetricCard
              icon={Layers}
              iconColor="purple"
              label="Attribution coverage"
              value={formatPercent(attributionCoverage.percent)}
              footnote={attributionCoverage.complete ? 'Complete request-level attribution' : `${formatInteger(attributionCoverage.legacyRequests)} legacy requests excluded from mix percentages`}
            />
          </div>

          <AttributionMetricToggle metric={attributionMetric} onChange={setAttributionMetric} />

          <div className="overview-bottom-grid">
            <div className="overview-side-stack">
              <SavingsMixPanel
                metric={attributionMetric}
                created={{ tokens: createdSavingsTokens, usd: createdSavingsUsd }}
                observed={{ tokens: observedProviderSavingsTokens, usd: observedProviderSavingsUsd }}
                note="Created savings come from Cutctx features. Observed savings come from upstream provider prompt-cache hits."
                coverage={attributionCoverage}
              />

              <CompressionDeclineStrip stats={stats} />

              <SavingsPanel
                title="Savings by source"
                eyebrow="Attribution"
                rows={sourceRows}
                totalTokens={sourceRowsTotalTokens}
                totalUsd={sourceRowsTotalUsd}
                metric={attributionMetric}
                emptyIcon={Sparkles}
                emptyTitle="No source breakdown yet"
                emptyDescription={sourcePanelDescription}
              />
            </div>

            <div className="overview-side-stack">
              <SavingsPanel
                title="Savings by model"
                eyebrow="Attribution"
                rows={modelRows}
                totalTokens={totalModelTokens}
                totalUsd={totalModelUsd}
                metric={attributionMetric}
                emptyIcon={Layers}
                emptyTitle="No model data yet"
                emptyDescription="Model-level attribution appears once requests flow through the proxy."
              />

              <SavingsPanel
                title="Savings by client"
                eyebrow="Attribution"
                rows={clientRows}
                totalTokens={totalClientTokens}
                totalUsd={totalClientUsd}
                metric={attributionMetric}
                emptyIcon={Sparkles}
                emptyTitle="No client data yet"
                emptyDescription={duration === 'lifetime'
                  ? 'Client attribution is currently shown on the lifetime view.'
                  : 'Client attribution is currently exposed on the lifetime view only.'}
              />
            </div>
          </div>
        </>
      )}
    </section>
  );
}
