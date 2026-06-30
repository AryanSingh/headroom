import { Boxes, BrainCircuit, Cable, CheckCircle2, Lock, MinusCircle, ServerCog, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { capabilityGroups } from '../data/capabilities';
import { formatCurrency, formatInteger, formatPercent, titleize } from '../lib/format';
import { useDashboardData, patchDashboardConfig } from '../lib/use-dashboard-data';

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

function ToggleSwitch({ checked, onChange, disabled }) {
  return (
    <label className="toggle-switch" style={{
      position: 'relative', display: 'inline-block', width: '36px', height: '20px', opacity: disabled ? 0.5 : 1, cursor: disabled ? 'not-allowed' : 'pointer'
    }}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} style={{ opacity: 0, width: 0, height: 0 }} />
      <span style={{
        position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: checked ? 'var(--accent)' : 'var(--surface-3)', transition: '.2s', borderRadius: '20px'
      }}>
        <span style={{
          position: 'absolute', content: '""', height: '14px', width: '14px', left: '3px', bottom: '3px',
          backgroundColor: 'white', transition: '.2s', borderRadius: '50%',
          transform: checked ? 'translateX(16px)' : 'translateX(0)'
        }} />
      </span>
    </label>
  );
}

export default function Capabilities() {
  const { stats, loading, error } = useDashboardData();
  const [updating, setUpdating] = useState({});

  const [optimisticState, setOptimisticState] = useState({});

  const providerCacheSavingsUsd =
    Number(stats?.savings_by_source?.usd?.provider_prompt_cache || 0)
    || Number(stats?.summary?.cost?.breakdown?.cache_savings_usd || 0);

  const handleToggle = async (key, currentValue) => {
    setUpdating((prev) => ({ ...prev, [key]: true }));
    setOptimisticState((prev) => ({ ...prev, [key]: !currentValue }));
    try {
      await patchDashboardConfig({ [key]: !currentValue });
    } catch (err) {
      console.error('Failed to toggle config:', err);
      // Revert optimistic state on error
      setOptimisticState((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } finally {
      setUpdating((prev) => ({ ...prev, [key]: false }));
    }
  };

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
      configKey: 'rate_limiter',
    },
    {
      label: 'Semantic cache',
      value: formatInteger(stats?.cache?.total_hits),
      detail: `${formatInteger(stats?.cache?.entries || 0)} entries · ${formatInteger(stats?.cache?.max_entries || 0)} max`,
      status: stats?.config?.cache !== false ? (stats?.cache?.entries ?? 1) : 0,
      configKey: 'cache',
    },
    {
      label: 'CCR store',
      value: formatInteger(stats?.compression?.ccr_entries),
      detail: `${formatInteger(stats?.compression?.ccr_retrievals || 0)} retrievals`,
      status: stats?.compression != null ? 1 : 0,
      configKey: 'ccr',
    },
    {
      label: 'Episodic memory',
      value: formatInteger(stats?.memory?.active_sessions || 0),
      detail: `Cross-session context enabled`,
      status: stats?.config?.memory ? 1 : 0,
      configKey: 'memory',
    },
    {
      label: 'Firewall',
      value: formatInteger(stats?.firewall?.scans || 0),
      detail: `Outbound prompt scanning`,
      status: stats?.config?.firewall ? 1 : 0,
      configKey: 'firewall',
    }
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
          {liveSurfaces.map((surface) => {
            const isToggleable = surface.configKey && stats?.config != null;
            const backendState = isToggleable ? stats.config[surface.configKey] : false;
            // Use optimistic state if it exists, otherwise backend state
            const toggleState = surface.configKey in optimisticState ? optimisticState[surface.configKey] : backendState;

            return (
              <article key={surface.label} className="metric-card metric-card-compact">
                <div className="metric-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="metric-label">{surface.label}</span>
                  {isToggleable ? (
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      {!loading && 'status' in surface && liveStatus(toggleState ? surface.status : 0)}
                      <ToggleSwitch 
                        checked={toggleState} 
                        onChange={() => handleToggle(surface.configKey, toggleState)} 
                        disabled={loading || updating[surface.configKey]} 
                      />
                    </div>
                  ) : (
                    !loading && 'status' in surface && liveStatus(surface.status)
                  )}
                </div>
                <div className="metric-value">{loading ? '—' : surface.value}</div>
                <div className="metric-footnote">{surface.detail}</div>
              </article>
            );
          })}
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
