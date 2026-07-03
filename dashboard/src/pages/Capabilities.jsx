import { useState } from 'react';
import {
  Boxes,
  BrainCircuit,
  Cable,
  CheckCircle2,
  Lock,
  MinusCircle,
  ServerCog,
  Sparkles,
  X,
} from 'lucide-react';
import { capabilityGroups } from '../data/capabilities';
import { formatCurrency, formatInteger, formatPercent, titleize } from '../lib/format';
import { patchDashboardConfig, useDashboardData } from '../lib/use-dashboard-data';

const icons = {
  'Core Deployment Modes': ServerCog,
  'Compression & Optimization': Sparkles,
  'State, Retrieval, and Memory': BrainCircuit,
  'Governance & Operations': Lock,
};

function liveStatus(active) {
  return active ? (
    <span className="status-active">
      <CheckCircle2 size={13} /> Active
    </span>
  ) : (
    <span className="status-inactive">
      <MinusCircle size={13} /> Idle
    </span>
  );
}

function ToggleSwitch({ checked, onChange, disabled, label }) {
  return (
    <label
      className="toggle-switch"
      style={{
        position: 'relative',
        display: 'inline-block',
        width: '36px',
        height: '20px',
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
disabled={disabled}
aria-label={label}
style={{ opacity: 0, width: 0, height: 0 }}
      />
      <span
        style={{
          position: 'absolute',
          cursor: 'pointer',
          inset: 0,
          backgroundColor: checked ? 'var(--accent)' : 'var(--surface-3)',
          transition: '.2s',
          borderRadius: '20px',
        }}
      >
        <span
          style={{
            position: 'absolute',
            height: '14px',
            width: '14px',
            left: '3px',
            bottom: '3px',
            backgroundColor: 'white',
            transition: '.2s',
            borderRadius: '50%',
            transform: checked ? 'translateX(16px)' : 'translateX(0)',
          }}
        />
      </span>
    </label>
  );
}

function getFlagEnabled(stats, configFlags, ...keys) {
  for (const key of keys) {
    if (stats?.config?.[key] != null) {
      return Boolean(stats.config[key]);
    }

    if (configFlags?.config?.[key] != null) {
      return Boolean(configFlags.config[key]);
    }

    if (configFlags?.live_toggleable?.[key]?.enabled != null) {
      return Boolean(configFlags.live_toggleable[key].enabled);
    }

    if (configFlags?.restart_required?.[key]?.enabled != null) {
      return Boolean(configFlags.restart_required[key].enabled);
    }
  }

  return null;
}

export default function Capabilities() {
  const { stats, loading, error, configFlags, configFlagsError, refresh } = useDashboardData();
  const [updating, setUpdating] = useState({});
  const [optimisticState, setOptimisticState] = useState({});
  const [toggleError, setToggleError] = useState(null);

  const providerCacheTokens =
    Number(stats?.cost?.savings_by_source?.tokens?.provider_prompt_cache || 0)
    || Number(stats?.savings_by_source?.tokens?.provider_prompt_cache || 0)
    || Number(stats?.prefix_cache?.totals?.cache_read_tokens || 0);

  const providerCacheSavingsUsd = Math.max(
    Number(stats?.cost?.cache_savings_usd || 0),
    Number(stats?.summary?.cost?.breakdown?.cache_savings_usd || 0),
    Number(stats?.prefix_cache?.totals?.net_savings_usd || 0),
    Number(stats?.prefix_cache?.totals?.savings_usd || 0),
    Number(stats?.savings_by_source?.usd?.provider_prompt_cache || 0),
  );

  const surfaceFlags = {
    rate_limiter: getFlagEnabled(stats, configFlags, 'rate_limiter', 'rate_limit_enabled'),
    cache: getFlagEnabled(stats, configFlags, 'cache', 'cache_enabled'),
    ccr: getFlagEnabled(stats, configFlags, 'ccr', 'ccr_context_tracking'),
    memory: getFlagEnabled(stats, configFlags, 'memory', 'episodic_memory_enabled'),
    firewall: getFlagEnabled(stats, configFlags, 'firewall', 'firewall_enabled'),
  };

  const handleToggle = async (key, currentValue) => {
    setUpdating((prev) => ({ ...prev, [key]: true }));
    setOptimisticState((prev) => ({ ...prev, [key]: !currentValue }));
    setToggleError(null);

    try {
      await patchDashboardConfig({ [key]: !currentValue });
      await refresh?.();
    } catch (err) {
      console.error('Failed to toggle config:', err);
      setToggleError(err?.message || 'Failed to update setting');
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
      value: formatInteger(providerCacheTokens),
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
      value: formatInteger(stats?.rate_limiter?.active_keys || 0),
      detail:
        stats?.rate_limiter != null
          ? `${formatInteger(stats?.rate_limiter?.tokens_per_minute || 0)} tokens / min`
          : 'This proxy is not exposing live rate limiter metrics',
      status: surfaceFlags.rate_limiter ?? stats?.rate_limiter != null,
      configKey: surfaceFlags.rate_limiter == null ? null : 'rate_limiter',
    },
    {
      label: 'Semantic cache',
      value: formatInteger(stats?.cache?.total_hits || 0),
      detail:
        stats?.cache != null
          ? `${formatInteger(stats?.cache?.entries || 0)} entries · ${formatInteger(stats?.cache?.max_entries || 0)} max`
          : 'This proxy is not exposing semantic cache metrics',
      status: surfaceFlags.cache ?? stats?.cache != null,
      configKey: surfaceFlags.cache == null ? null : 'cache',
    },
    {
      label: 'CCR store',
      value: formatInteger(stats?.compression?.ccr_entries || 0),
      detail: `${formatInteger(stats?.compression?.ccr_retrievals || 0)} retrievals`,
      status: surfaceFlags.ccr ?? stats?.compression != null,
      configKey: surfaceFlags.ccr == null ? null : 'ccr',
    },
    {
      label: 'Episodic memory',
      value: formatInteger(stats?.memory?.active_sessions || 0),
      detail:
        stats?.memory != null
          ? 'Cross-session context enabled'
          : 'This proxy is not exposing episodic memory metrics',
      status: surfaceFlags.memory ?? stats?.memory != null,
      configKey: surfaceFlags.memory == null ? null : 'memory',
    },
    {
      label: 'Firewall',
      value: formatInteger(stats?.firewall?.scans || 0),
      detail:
        stats?.firewall != null
          ? 'Outbound prompt scanning'
          : 'This proxy is not exposing firewall scan metrics',
      status: surfaceFlags.firewall ?? stats?.firewall != null,
      configKey: surfaceFlags.firewall == null ? null : 'firewall',
    },
  ];

  return (
    <section className="page-stack">
      {error ? (
        <div className="alert-card" role="alert">
          Failed to load live capability signals: {error}
        </div>
      ) : null}

      {configFlagsError ? (
        <div className="alert-card" role="status">
          Runtime config API unavailable: {configFlagsError}. Idle states below may reflect missing backend
          telemetry rather than disabled features.
        </div>
      ) : null}

      {toggleError ? (
        <div className="alert-card" role="alert">
          <span>Failed to update setting: {toggleError}</span>
          <button
            className="ghost-button"
            style={{ marginLeft: 'auto' }}
            onClick={() => setToggleError(null)}
            type="button"
          >
            <X size={14} /> Dismiss
          </button>
        </div>
      ) : null}

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
            const isToggleable = Boolean(surface.configKey);
            const backendState = isToggleable ? surfaceFlags[surface.configKey] : false;
            const toggleState =
              isToggleable && surface.configKey in optimisticState
                ? optimisticState[surface.configKey]
                : backendState;

            return (
              <article key={surface.label} className="metric-card metric-card-compact">
                <div
                  className="metric-header"
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span className="metric-label">{surface.label}</span>
                  {isToggleable ? (
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      {!loading && liveStatus(Boolean(toggleState))}
                      <ToggleSwitch
                        checked={Boolean(toggleState)}
                        onChange={() => handleToggle(surface.configKey, Boolean(toggleState))}
disabled={loading || updating[surface.configKey]}
label={`${toggleState ? "Disable" : "Enable"} ${surface.label}`}
/>
                    </div>
                  ) : !loading && 'status' in surface ? (
                    liveStatus(Boolean(surface.status))
                  ) : null}
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
