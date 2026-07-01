import { CheckCircle2, Copy, MinusCircle, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson, patchDashboardConfig, useDashboardData } from '../lib/use-dashboard-data';

const GOVERNANCE_PATHS = {
  audit: '/audit/events',
  rbac: '/rbac/roles',
};

const FEATURE_CONFIG = [
  {
    key: 'firewall',
    flagKey: 'firewall_enabled',
    label: 'Request firewall',
    envVar: 'CUTCTX_FIREWALL_ENABLED=1',
    description: 'Scan every request for prompt injection, jailbreaks, and PII before it reaches the model.',
    tier: 'free',
    liveToggle: false,
    statPath: (stats) => stats?.config?.firewall,
  },
  {
    key: 'rate_limit',
    flagKey: 'rate_limit_enabled',
    label: 'Rate limiting',
    envVar: 'CUTCTX_RATE_LIMIT_ENABLED=true',
    description: 'Token-bucket rate limiting per API key. Configure limits with CUTCTX_RATE_LIMIT_TPM and CUTCTX_RATE_LIMIT_RPM.',
    tier: 'free',
    liveToggle: false,
    statPath: (stats) => stats?.config?.rate_limiter,
  },
  {
    key: 'task_aware',
    flagKey: 'task_aware_enabled',
    label: 'Task-aware compression',
    envVar: 'CUTCTX_TASK_AWARE_ENABLED=1',
    description: 'Modulate compression depth based on relevance to the active task.',
    tier: 'free',
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: 'dedup',
    flagKey: 'dedup_enabled',
    label: 'Semantic deduplication',
    envVar: 'CUTCTX_DEDUP_ENABLED=1',
    description: 'Detect and collapse repeated content across messages using reversible CCR pointers.',
    tier: 'free',
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: 'context_budget',
    flagKey: 'context_budget_enabled',
    label: 'Context budget controller',
    envVar: 'CUTCTX_CONTEXT_BUDGET_ENABLED=1',
    description: 'Progressively increase compression as the context window fills.',
    tier: 'free',
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: 'profiles',
    flagKey: 'profiles_enabled',
    label: 'Compression profiles',
    envVar: 'CUTCTX_PROFILES_ENABLED=1',
    description: 'Learn per-workspace compression patterns across sessions and reuse them later.',
    tier: 'free',
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: 'shared_context',
    flagKey: 'shared_context_enabled',
    label: 'Cross-agent memory',
    envVar: 'CUTCTX_SHARED_CONTEXT_ENABLED=1',
    description: 'Share compressed context and cache hits across agents working in the same workspace.',
    tier: 'enterprise',
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: 'episodic_memory',
    flagKey: 'episodic_memory_enabled',
    label: 'Episodic memory',
    envVar: 'CUTCTX_EPISODIC_MEMORY_ENABLED=1',
    description: 'Store and reinject project memories across sessions.',
    tier: 'enterprise',
    liveToggle: true,
    statPath: (stats) => stats?.config?.memory,
  },
  {
    key: 'cost_forecast',
    flagKey: 'cost_forecast_enabled',
    label: 'Cost forecasting',
    envVar: 'CUTCTX_COST_FORECAST_ENABLED=1',
    description: 'Estimate request cost up front and feed policy decisions before compression runs.',
    tier: 'free',
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: 'audit',
    flagKey: 'audit_enabled',
    label: 'Audit trail',
    envVar: 'CUTCTX_AUDIT_DISABLED=0',
    description: 'Persist admin and governance activity to the audit log. Restart required to fully apply changes.',
    tier: 'enterprise',
    liveToggle: false,
    statPath: () => null,
  },
  {
    key: 'rbac',
    flagKey: null,
    label: 'RBAC admin controls',
    envVar: 'Enterprise entitlement required',
    description: 'Role assignment and permission enforcement surfaces. This is a control plane, not a simple boolean flag.',
    tier: 'enterprise',
    liveToggle: false,
    statPath: (_, sections) => sections?.rbac?.ok ?? null,
  },
];

function emptySection() {
  return { ok: false, data: null, error: 'Loading…' };
}

function normalizeAssignments(rbacData) {
  const raw = rbacData?.assignments;
  if (Array.isArray(raw)) {
    return raw;
  }
  if (raw && typeof raw === 'object') {
    return Object.entries(raw).map(([userId, role]) => ({ user_id: userId, role }));
  }
  return [];
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <button className="copy-btn" onClick={handleCopy} title="Copy to clipboard" type="button">
      {copied ? <CheckCircle2 size={13} /> : <Copy size={13} />}
    </button>
  );
}

function FeatureToggle({ enabled, onToggle, busy }) {
  return (
    <button
      className={`feature-toggle ${enabled ? 'feature-toggle-on' : 'feature-toggle-off'}`}
      onClick={onToggle}
      disabled={busy}
      aria-label={enabled ? 'Disable feature' : 'Enable feature'}
      type="button"
    >
      <span className="feature-toggle-knob" />
    </button>
  );
}

function resolveFeatureState(feature, stats, configFlags, liveFlags, sections) {
  if (!feature.flagKey) {
    return feature.statPath(stats, sections);
  }

  if (feature.flagKey in liveFlags) {
    return liveFlags[feature.flagKey];
  }

  if (configFlags?.live_toggleable?.[feature.flagKey]?.enabled != null) {
    return Boolean(configFlags.live_toggleable[feature.flagKey].enabled);
  }

  if (configFlags?.restart_required?.[feature.flagKey]?.enabled != null) {
    return Boolean(configFlags.restart_required[feature.flagKey].enabled);
  }

  return feature.statPath(stats, sections);
}

function FeatureRow({
  feature,
  stats,
  configFlags,
  liveFlags,
  sections,
  onToggle,
  toggleBusy,
}) {
  const isActive = resolveFeatureState(feature, stats, configFlags, liveFlags, sections);
  const toggleable = Boolean(feature.flagKey);

  return (
    <div className="feature-config-row">
      <div className="feature-config-main">
        <div className="feature-config-header">
          <span className="feature-config-name">{feature.label}</span>
          {feature.tier === 'enterprise' ? (
            <span className="tier-badge tier-enterprise">Enterprise</span>
          ) : null}
          {toggleable && !feature.liveToggle ? (
            <span className="tier-badge tier-restart">
              <RefreshCw size={10} /> Restart required
            </span>
          ) : null}
          {isActive === true ? (
            <span className="status-active">
              <CheckCircle2 size={12} /> Active
            </span>
          ) : isActive === false ? (
            <span className="status-inactive">
              <MinusCircle size={12} /> Inactive
            </span>
          ) : null}
        </div>
        <p className="feature-config-desc">{feature.description}</p>
      </div>

      <div className="feature-config-controls">
        {toggleable ? (
          <>
            <FeatureToggle
              enabled={Boolean(isActive)}
              onToggle={() => onToggle(feature.flagKey, !Boolean(isActive))}
              busy={toggleBusy === feature.flagKey}
            />
            <div className="feature-config-env">
              <code>{feature.envVar}</code>
              <CopyButton text={feature.envVar} />
            </div>
          </>
        ) : (
          <div className="feature-config-env">
            <code>{feature.envVar}</code>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Governance({ searchQuery = '' }) {
  const { stats, loading: statsLoading, configFlags, configFlagsError, refresh } = useDashboardData();
  const [sections, setSections] = useState({
    audit: emptySection(),
    rbac: emptySection(),
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [liveFlags, setLiveFlags] = useState({});
  const [toggleBusy, setToggleBusy] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      const entries = await Promise.all(
        Object.entries(GOVERNANCE_PATHS).map(async ([key, path]) => {
          try {
            const data = await fetchDashboardJson(path);
            return [key, { ok: true, data, error: null }];
          } catch (error) {
            return [key, { ok: false, data: null, error: error.message || String(error) }];
          }
        }),
      );

      if (cancelled) {
        return;
      }

      setSections(Object.fromEntries(entries));
      setLoading(false);
      setLastUpdated(new Date().toISOString());
    };

    load();
    const id = setInterval(load, 15_000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!configFlags) {
      return;
    }

    setLiveFlags((prev) => {
      const next = { ...prev };

      for (const [key, value] of Object.entries(configFlags.live_toggleable || {})) {
        if (!(key in next) && value?.enabled != null) {
          next[key] = Boolean(value.enabled);
        }
      }

      for (const [key, value] of Object.entries(configFlags.restart_required || {})) {
        if (!(key in next) && value?.enabled != null) {
          next[key] = Boolean(value.enabled);
        }
      }

      return next;
    });
  }, [configFlags]);

  const handleToggle = useCallback(
    async (flagKey, value) => {
      setToggleBusy(flagKey);
      try {
        const response = await patchDashboardConfig({ [flagKey]: value });
        setLiveFlags((prev) => ({
          ...prev,
          [flagKey]: value,
          ...(response?.applied_live || {}),
        }));
        await refresh?.();
      } finally {
        setToggleBusy(null);
      }
    },
    [refresh],
  );

  const assignments = useMemo(() => normalizeAssignments(sections.rbac.data), [sections.rbac.data]);
  const failedSections = Object.entries(sections).filter(([, section]) => !section.ok && !loading);
  const rateLimiter = stats?.rate_limiter || null;
  const rateLimitEnabled =
    stats?.config?.rate_limiter ??
    configFlags?.restart_required?.rate_limit_enabled?.enabled ??
    false;

  const filteredFeatures = FEATURE_CONFIG.filter((feature) => {
    const query = searchQuery.toLowerCase();
    return (
      feature.label.toLowerCase().includes(query) ||
      feature.description.toLowerCase().includes(query)
    );
  });

  return (
    <section className="page-stack">
      {failedSections.length > 0 ? (
        <div className="alert-card" role="alert">
          Some governance surfaces could not be reached: {failedSections.map(([key]) => key).join(', ')}.
        </div>
      ) : null}

      {configFlagsError ? (
        <div className="alert-card" role="status">
          Runtime config API unavailable: {configFlagsError}. Dashboard toggles only work once the
          backend exposes the config flag routes.
        </div>
      ) : null}

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Live control</div>
            <h2>Rate limiting</h2>
          </div>
          <p>
            {rateLimitEnabled
              ? 'Token-bucket throttling is configured.'
              : 'Rate limiting is not enabled yet.'}
          </p>
        </div>

        <div className="metric-grid metric-grid-four" aria-busy={statsLoading}>
          <article className="metric-card metric-card-compact">
            <div className="metric-label">Status</div>
            <div className="metric-value">{rateLimitEnabled ? 'Active' : 'Inactive'}</div>
            <div className="metric-footnote">Dashboard toggle updates config. Restart may still be required.</div>
          </article>
          <article className="metric-card metric-card-compact">
            <div className="metric-label">Active keys</div>
            <div className="metric-value">{formatInteger(rateLimiter?.active_keys || 0)}</div>
            <div className="metric-footnote">Keys with live rate state</div>
          </article>
          <article className="metric-card metric-card-compact">
            <div className="metric-label">Token limit</div>
            <div className="metric-value">
              {rateLimiter ? formatInteger(rateLimiter.tokens_per_minute || 0) : '—'}
            </div>
            <div className="metric-footnote">Tokens per minute per key</div>
          </article>
          <article className="metric-card metric-card-compact">
            <div className="metric-label">Request limit</div>
            <div className="metric-value">
              {rateLimiter ? formatInteger(rateLimiter.requests_per_minute || 0) : '—'}
            </div>
            <div className="metric-footnote">Requests per minute per key</div>
          </article>
        </div>
      </div>

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Feature configuration</div>
            <h2>Enable optional features</h2>
          </div>
          <p>
            Dashboard toggles write to the proxy config when supported. Some features apply on the
            next request, while others need a restart to take effect fully.
          </p>
        </div>

        <div className="feature-config-list">
          {filteredFeatures.map((feature) => (
            <FeatureRow
              key={feature.key}
              feature={feature}
              stats={stats}
              configFlags={configFlags}
              liveFlags={liveFlags}
              sections={sections}
              onToggle={handleToggle}
              toggleBusy={toggleBusy}
            />
          ))}
        </div>
      </div>

      <div className="metric-grid metric-grid-two">
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise</div>
              <h2>Audit surface</h2>
            </div>
            <p>{lastUpdated ? `Refreshed ${formatRelativeTime(lastUpdated)}` : 'Polling every 15 seconds'}</p>
          </div>
          <div className="graphify-kv-grid">
            <div className="graphify-kv">
              <span>Status</span>
              <strong>{sections.audit.ok ? 'Reachable' : sections.audit.error || 'Unavailable'}</strong>
            </div>
            <div className="graphify-kv">
              <span>Recent events</span>
              <strong>{formatInteger(sections.audit.data?.events?.length || 0)}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise</div>
              <h2>RBAC surface</h2>
            </div>
            <p>{lastUpdated ? `Refreshed ${formatRelativeTime(lastUpdated)}` : 'Polling every 15 seconds'}</p>
          </div>
          <div className="graphify-kv-grid">
            <div className="graphify-kv">
              <span>Status</span>
              <strong>{sections.rbac.ok ? 'Reachable' : sections.rbac.error || 'Unavailable'}</strong>
            </div>
            <div className="graphify-kv">
              <span>Assignments</span>
              <strong>{formatInteger(assignments.length)}</strong>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
