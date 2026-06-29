import { Boxes, BrainCircuit, Cable, CheckCircle2, Lock, MinusCircle, ServerCog, Sparkles } from 'lucide-react';
import { capabilityGroups } from '../data/capabilities';
import { formatCurrency, formatInteger, formatPercent, titleize } from '../lib/format';
import { useDashboardData } from '../lib/use-dashboard-data';

const icons = {
  'Core Deployment Modes': ServerCog,
  'Compression & Optimization': Sparkles,
  'State, Retrieval, and Memory': BrainCircuit,
  'Governance & Operations': Lock,
};

function liveStatus(value) {
  const nonzero = value != null && value !== 0 && value !== '0' && value !== 'none' && value !== 'None';
  return nonzero
    ? <span className="status-active"><CheckCircle2 size={13} /> Active</span>
    : <span className="status-inactive"><MinusCircle size={13} /> Idle</span>;
}

export default function Capabilities() {
  const { stats, loading, error } = useDashboardData();
  const providerCacheSavingsUsd =
    Number(stats?.savings_by_source?.usd?.provider_prompt_cache || 0)
    || Number(stats?.summary?.cost?.breakdown?.cache_savings_usd || 0);

  const liveSurfaces = [
    {
      label: 'Proxy compression',
      value: formatInteger(stats?.tokens?.proxy_compression_saved),
      detail: `${formatPercent(stats?.tokens?.proxy_savings_percent)} active savings`,
    },
    {
      label: 'Provider cache',
      value: formatInteger(stats?.savings_by_source?.tokens?.provider_prompt_cache),
      detail: `${formatCurrency(providerCacheSavingsUsd)} saved`,
    },
    {
      label: 'Codex websocket',
      value: formatInteger(stats?.codex_ws?.frames_attempted_total),
      detail: `${formatInteger(stats?.codex_ws?.frames_failed_total)} failed frames`,
    },
    {
      label: 'Context tool',
      value: titleize(stats?.context_tool?.configured || 'none'),
      detail: stats?.context_tool?.available ? 'Available in workspace' : 'Unavailable',
    },
    {
      label: 'TOIN patterns',
      value: formatInteger(stats?.toin?.patterns_tracked),
      detail: `${formatInteger(stats?.toin?.patterns_with_recommendations)} with recommendations`,
    },
    {
      label: 'Rate limiter',
      value: formatInteger(stats?.rate_limiter?.active_keys),
      detail: `${formatInteger(stats?.rate_limiter?.tokens_per_minute)} tokens / min`,
      status: stats?.rate_limiter?.active_keys,
    },
    {
      label: 'Memory backend',
      value: titleize(stats?.memory?.backend || 'none'),
      detail: `${formatInteger(stats?.memory?.total_entries)} entries stored`,
      status: stats?.memory?.backend && stats.memory.backend !== 'none' ? 1 : 0,
    },
    {
      label: 'Semantic cache',
      value: formatInteger(stats?.semantic_cache?.hits),
      detail: `${formatInteger(stats?.semantic_cache?.misses)} misses`,
      status: stats?.semantic_cache?.hits,
    },
  ];

  return (
    <section className="page-stack">


      {error && <div className="alert-card" role="alert">Failed to load live capability signals: {error}</div>}

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Live evidence</div>
            <h2>Runtime surfaces currently active</h2>
          </div>
          <p>{loading ? 'Connecting to proxy…' : 'Signals pulled from the running proxy and stats API.'}</p>
        </div>

        <div className="metric-grid metric-grid-three" aria-busy={loading}>
          {liveSurfaces.map((surface) => (
            <article key={surface.label} className="metric-card metric-card-compact">
              <div className="metric-header">
                <span className="metric-label">{surface.label}</span>
                {!loading && 'status' in surface && liveStatus(surface.status)}
              </div>
              <div className="metric-value">{loading ? '—' : surface.value}</div>
              <div className="metric-footnote">{surface.detail}</div>
            </article>
          ))}
        </div>
      </div>

      {capabilityGroups.map((group) => {
        const Icon = icons[group.title] || Boxes;

        return (
          <section key={group.title} className="panel capability-panel">
            <div className="section-heading">
              <div className="heading-with-icon">
                <div className="heading-icon">
                  <Icon size={18} />
                </div>
                <div>
                  <div className="eyebrow">Capability group</div>
                  <h2>{group.title}</h2>
                </div>
              </div>
              <p>{group.description}</p>
            </div>

            <div className="capability-grid">
              {group.items.map((item) => (
                <article key={item.name} className="capability-card">
                  <div className="capability-name">
                    <Cable size={16} />
                    {item.name}
                  </div>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </section>
  );
}
