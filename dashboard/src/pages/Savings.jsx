import { useState, useEffect } from 'react';
import { PiggyBank, Calendar, Clock, Sparkles, Layers, Activity, Coins } from 'lucide-react';
import { useDashboardData, fetchDashboardJson } from '../lib/use-dashboard-data';
import { fetchPeriodStats } from '../lib/period-stats';
import { getDurationSavingsUsd } from '../lib/savings-sources';
import {
  formatCurrency,
  formatInteger,
  formatNumber,
  formatPercent,
} from '../lib/format';

function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton skeleton-line skeleton-line-sm" />
      <div className="skeleton skeleton-value" />
      <div className="skeleton skeleton-line skeleton-line-lg" />
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
      {footnote && <div className="metric-footnote">{footnote}</div>}
    </div>
  );
}

function SavingsPanel({ title, eyebrow, rows, totalTokens, totalUsd, metric, emptyIcon: EmptyIcon, emptyTitle, emptyDescription }) {
  const byUsd = metric === 'usd';
  const total = byUsd ? totalUsd : totalTokens;
  const sortedRows = [...rows].sort((a, b) => (byUsd ? b.usd - a.usd : b.tokens - a.tokens));

  return (
    <section className="panel panel-compact">
      <div className="section-heading">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2>{title}</h2>
        </div>
      </div>

      {sortedRows.length === 0 ? (
        <div className="overview-empty">
          <div className="overview-empty-illustration">
            <EmptyIcon size={28} />
          </div>
          <h3>{emptyTitle}</h3>
          <p>{emptyDescription}</p>
        </div>
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

export default function Savings() {
  const { historyData, loading: contextLoading, error: contextError } = useDashboardData();
  const [duration, setDuration] = useState('lifetime'); // 'session', 'lifetime', 'daily', 'weekly', 'monthly'
  const [attributionMetric, setAttributionMetric] = useState('tokens'); // 'tokens' | 'usd'
  const [durationData, setDurationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    
    async function fetchData() {
      setLoading(true);
      setError(null);
      
      if (duration === 'session') {
        if (historyData?.display_session) {
          setDurationData(historyData.display_session);
        }
        setLoading(false);
        return;
      }
      
      if (duration === 'lifetime') {
        if (historyData?.lifetime) {
          setDurationData(historyData.lifetime);
        }
        setLoading(false);
        return;
      }
      
      try {
        const period = await fetchPeriodStats(fetchDashboardJson, duration);
        if (active) {
          setDurationData(period);
        }
      } catch (err) {
        if (active) {
          setError(err.message || String(err));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    
    fetchData();
    
    return () => {
      active = false;
    };
  }, [duration, historyData]);

  // Aggregate stats from durationData
  const tokensSaved = durationData?.tokens_saved || 0;
  const savingsUsd = getDurationSavingsUsd(durationData);
  const savingsObservedUsd = durationData?.compression_savings_observed_usd || 0;
  const totalInputTokens = durationData?.total_input_tokens || 1;
  const savingsPercent = durationData?.savings_percent != null 
    ? durationData.savings_percent 
    : ((tokensSaved / Math.max(totalInputTokens, tokensSaved)) * 100);

  // Extract source rows
  const parseRows = (prefix) => {
    if (!durationData) {
      return [];
    }
    return Object.keys(durationData)
      .filter((k) => k.startsWith(`${prefix}.`))
      .map((k) => {
        const key = k.replace(`${prefix}.`, '');
        const tokens = durationData[k] || 0;
        const usdKey = `${prefix}_usd.${key}`;
        const usd = durationData[usdKey] || 0;
        return { key, label: key, tokens, usd };
      })
      .filter((r) => r.tokens > 0)
      .sort((a, b) => b.tokens - a.tokens);
  };

  // Real per-model/per-client attribution — see SavingsTracker.models/.clients.
  // `savings_by_source_tokens.model.*`/`.client.*` (parseRows above) is dead:
  // the backend only ever writes compression-technique keys under that
  // prefix (cutctx_compression, semantic_cache, ...), never per-model or
  // per-client breakdowns, so parseRows always returned []. historyData.models
  // and historyData.clients are the real, restart-safe lifetime totals.
  // Per-period model attribution comes from durationData.models, built by
  // aggregatePeriodBuckets from the series' by_model breakdown — but the
  // history series has no by_client breakdown, so client attribution stays
  // lifetime-only.
  const mapAttributionRows = (entries) => Object.entries(entries || {})
    .map(([key, data]) => ({
      key,
      label: key,
      tokens: Number(data?.tokens_saved || 0),
      usd: Number(data?.compression_savings_usd || 0),
    }))
    .filter((r) => r.tokens > 0)
    .sort((a, b) => b.tokens - a.tokens);

  const modelRows = duration === 'lifetime' && historyData?.models
    ? mapAttributionRows(historyData.models)
    : duration !== 'session' && durationData?.models
      ? mapAttributionRows(durationData.models)
      : parseRows('savings_by_source_tokens.model');
  const clientRows = duration === 'lifetime' && historyData?.clients
    ? mapAttributionRows(historyData.clients)
    : parseRows('savings_by_source_tokens.client');
  const totalModelTokens = modelRows.reduce((sum, r) => sum + r.tokens, 0);
  const totalModelUsd = modelRows.reduce((sum, r) => sum + r.usd, 0);
  const totalClientTokens = clientRows.reduce((sum, r) => sum + r.tokens, 0);
  const totalClientUsd = clientRows.reduce((sum, r) => sum + r.usd, 0);

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <h1>Savings & Attribution</h1>
          <p>Track token reduction and cost savings across different time periods.</p>
        </div>
      </div>

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

      {(error || contextError) ? (
        <div className="alert-card" role="alert">
          <span>Failed to load data: {error || contextError}</span>
        </div>
      ) : null}

      {(loading || contextLoading) && !durationData ? (
        <div className="metric-grid metric-grid-three">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (
        <>
          <div className="metric-grid metric-grid-three">
            <MetricCard
              icon={PiggyBank}
              iconColor="green"
              label="Tokens saved"
              value={formatNumber(tokensSaved)}
              footnote={`${formatPercent(savingsPercent)} total reduction`}
            />
            <MetricCard
              icon={Coins}
              iconColor="yellow"
              label="Estimated savings"
              value={
                savingsUsd > savingsObservedUsd && savingsObservedUsd > 0
                  ? `${formatCurrency(savingsUsd)} (list) / ${formatCurrency(savingsObservedUsd)} (observed)`
                  : formatCurrency(savingsUsd)
              }
              footnote={`from ${formatNumber(durationData?.requests || 0)} proxy requests`}
            />
            <MetricCard
              icon={Layers}
              iconColor="blue"
              label="Total input tokens"
              value={formatNumber(durationData?.total_input_tokens || 0)}
              footnote={`Costing ${formatCurrency(durationData?.total_input_cost_usd || 0)}`}
            />
          </div>

          <AttributionMetricToggle metric={attributionMetric} onChange={setAttributionMetric} />
          <div className="overview-bottom-grid">
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
                emptyDescription="No model attribution data yet — send some traffic through the proxy."
              />
            </div>
            <div className="overview-side-stack">
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
                  ? 'No client attribution data yet — send some traffic through the proxy.'
                  : 'Per-client attribution is only tracked lifetime; switch to the Lifetime tab to see it.'}
              />
            </div>
          </div>
        </>
      )}
    </section>
  );
}
