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
    if (configFlags?.live_toggleable?.[key]?.enabled != null) {
      return Boolean(configFlags.live_toggleable[key].enabled);
    }

    if (configFlags?.restart_required?.[key]?.enabled != null) {
      return Boolean(configFlags.restart_required[key].enabled);
    }

    if (configFlags?.config?.[key] != null) {
      return Boolean(configFlags.config[key]);
    }

    if (stats?.config?.[key] != null) {
      return Boolean(stats.config[key]);
    }
  }

  return null;
}

function isRestartRequired(configFlags, key) {
  return Boolean(configFlags?.restart_required?.[key]);
}

export default function Capabilities({ searchQuery = '' }) {
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
  const eligibleCompressionTokens = Number(stats?.opportunity_funnel?.eligible_input_tokens || 0);
  const cacheProtectedTokens = Number(stats?.opportunity_funnel?.cache_protected_tokens || 0);
  const cacheProtectedPercent = eligibleCompressionTokens > 0
    ? (cacheProtectedTokens / eligibleCompressionTokens) * 100
    : 0;
  const proxyCompressionSaved = Number(stats?.tokens?.proxy_compression_saved || 0);

  const surfaceFlags = {
    rate_limit_enabled: getFlagEnabled(stats, configFlags, 'rate_limit_enabled', 'rate_limiter'),
    cache_enabled: getFlagEnabled(stats, configFlags, 'cache_enabled', 'cache'),
    ccr_context_tracking: getFlagEnabled(stats, configFlags, 'ccr_context_tracking', 'ccr'),
    episodic_memory_enabled: getFlagEnabled(
      stats,
      configFlags,
      'episodic_memory_enabled',
      'memory',
    ),
    firewall_enabled: getFlagEnabled(stats, configFlags, 'firewall_enabled', 'firewall'),
  };

  const handleToggle = async (key, currentValue) => {
    setUpdating((prev) => ({ ...prev, [key]: true }));
    setOptimisticState((prev) => ({ ...prev, [key]: !currentValue }));
    setToggleError(null);

    try {
      await patchDashboardConfig({ [key]: !currentValue });
      await refresh?.();
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error('Failed to toggle config:', err);
      }
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
      value: formatInteger(proxyCompressionSaved),
      detail: proxyCompressionSaved === 0 && cacheProtectedTokens > 0
        ? `${formatPercent(cacheProtectedPercent)} cache-protected · left unchanged intentionally`
        : `${formatPercent(stats?.tokens?.proxy_savings_percent)} active savings`,
    },
    {
      label: 'Provider cache',
      value: formatInteger(providerCacheTokens),
      detail: `${formatCurrency(providerCacheSavingsUsd)} saved`,
    },
    stats?.codex_ws != null ? {
      label: 'Codex websocket',
      value: formatInteger(stats?.codex_ws?.frames_attempted_total),
      detail: `${formatInteger(stats?.codex_ws?.frames_failed_total)} failed frames`,
    } : null,
    stats?.context_tool != null ? {
      label: 'Context tool',
      value: titleize(stats?.context_tool?.configured || 'none'),
      detail: stats?.context_tool?.available ? 'Available in workspace' : 'Unavailable',
    } : null,
    stats?.toin != null ? {
      label: 'TOIN patterns',
      value: formatInteger(stats?.toin?.patterns_tracked),
      detail: `${formatInteger(stats?.toin?.patterns_with_recommendations)} with recommendations`,
    } : null,
    {
      label: 'Rate limiter',
      value: formatInteger(stats?.rate_limiter?.active_keys || 0),
      detail:
        stats?.rate_limiter != null
          ? `${formatInteger(stats?.rate_limiter?.tokens_per_minute || 0)} tokens / min`
          : 'This proxy is not exposing live rate limiter metrics',
      status: surfaceFlags.rate_limit_enabled ?? stats?.rate_limiter != null,
      configKey: surfaceFlags.rate_limit_enabled == null ? null : 'rate_limit_enabled',
    },
    {
      label: 'Response cache',
      value: formatInteger(stats?.cache?.total_hits || 0),
      detail:
        stats?.cache != null
          ? `${formatInteger(stats?.cache?.entries || 0)} entries · ${formatInteger(stats?.cache?.total_misses || 0)} misses · ${formatInteger(stats?.cache?.tokens_avoided || 0)} tokens avoided`
          : 'This proxy is not exposing response cache metrics',
      status: surfaceFlags.cache_enabled ?? stats?.cache != null,
      configKey: surfaceFlags.cache_enabled == null ? null : 'cache_enabled',
    },
    {
      label: 'CCR store',
      value: formatInteger(stats?.compression?.ccr_entries || 0),
      detail: `${formatInteger(stats?.compression?.ccr_retrievals || 0)} retrievals · ${formatInteger(stats?.compression?.original_tokens_cached || 0)} original tokens stored`,
      status: surfaceFlags.ccr_context_tracking ?? stats?.compression != null,
      configKey: surfaceFlags.ccr_context_tracking == null ? null : 'ccr_context_tracking',
    },
    {
      label: 'Episodic memory',
      value: formatInteger(stats?.memory?.active_sessions || 0),
      detail:
        stats?.memory != null
          ? 'Cross-session context enabled'
          : 'This proxy is not exposing episodic memory metrics',
      status: surfaceFlags.episodic_memory_enabled ?? stats?.memory != null,
      configKey: surfaceFlags.episodic_memory_enabled == null
        ? null
        : 'episodic_memory_enabled',
    },
    {
      label: 'Firewall',
      value: formatInteger(stats?.firewall?.scans || 0),
      detail:
        stats?.firewall != null
          ? 'Outbound prompt scanning'
          : 'This proxy is not exposing firewall scan metrics',
      status: surfaceFlags.firewall_enabled ?? stats?.firewall != null,
      configKey: surfaceFlags.firewall_enabled == null ? null : 'firewall_enabled',
    },
  ].filter(Boolean);

  const query = searchQuery.trim().toLowerCase();
  const filteredGroups = capabilityGroups
    .map((group) => {
      if (!query) {
        return group;
      }

      const matchedItems = group.items.filter(
        (item) => item.name.toLowerCase().includes(query) || item.detail.toLowerCase().includes(query),
      );

      if (matchedItems.length === 0 && !group.title.toLowerCase().includes(query)) {
        return null;
      }

      return { ...group, items: matchedItems.length > 0 ? matchedItems : group.items };
    })
    .filter(Boolean);

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
            const restartRequired = isRestartRequired(configFlags, surface.configKey);

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
                        disabled={loading || restartRequired || updating[surface.configKey]}
                        label={restartRequired
                          ? surface.label + ' requires a proxy restart'
                          : (toggleState ? 'Disable ' : 'Enable ') + surface.label}
                      />
                    </div>
                  ) : !loading && 'status' in surface ? (
                    liveStatus(Boolean(surface.status))
                  ) : null}
                </div>
                <div className="metric-value">{loading ? '—' : surface.value}</div>
                <div className="metric-footnote">
                  {surface.detail}
                  {restartRequired ? ' · Restart required to apply changes' : ''}
                </div>
              </article>
            );
          })}
        </div>
      </div>

      {filteredGroups.length === 0 && query ? (
        <div className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Search</div>
              <h2>No capability matches</h2>
            </div>
            <p>Try a broader query or clear the search box to see all capability groups.</p>
          </div>
        </div>
      ) : null}

      {filteredGroups.map((group) => {
        const Icon = icons[group.title] || Boxes;
        const iconColors = {
          'Core Deployment Modes': { bg: 'rgba(14, 165, 233, 0.1)', color: '#0ea5e9' },
          'Compression & Optimization': { bg: 'rgba(16, 185, 129, 0.1)', color: '#10b981' },
          'State, Retrieval, and Memory': { bg: 'rgba(168, 85, 247, 0.1)', color: '#a855f7' },
          'Governance & Operations': { bg: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' },
        };
        const colorStyle = iconColors[group.title] || { bg: 'var(--accent-muted)', color: 'var(--accent)' };

        return (
          <section key={group.title} className="panel capability-panel">
            <div className="section-heading">
              <div className="heading-with-icon">
                <div className="heading-icon" style={{ backgroundColor: colorStyle.bg, color: colorStyle.color }}>
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
