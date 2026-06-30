import {
  BadgeCheck,
  Building2,
  CheckCircle2,
  Copy,
  KeyRound,
  MinusCircle,
  RefreshCw,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson, useDashboardData } from '../lib/use-dashboard-data';
import { getAdminAuthHeaders } from '../lib/admin-auth';
import { getProxyUrl } from '../lib/api';

const GOVERNANCE_PATHS = {
  audit: '/audit/events',
  rbac: '/rbac/roles',
};

// TODO: The following endpoints are planned but not yet implemented in admin.py:
// - /orgs: organization management
// - /quota: quota tracking
// - /retention/stats: data retention statistics
// - /subscription-window: subscription lifecycle

// liveToggle=true means the proxy can apply the change immediately (per-request flag).
// liveToggle=false means a proxy restart is required.
const FEATURE_CONFIG = [
  {
    key: 'firewall',
    flagKey: 'firewall_enabled',
    label: 'Request firewall',
    envVar: 'CUTCTX_FIREWALL_ENABLED=1',
    description: 'Scan every request for prompt injection, jailbreaks, and PII before it reaches the model.',
    tier: 'free',
    liveToggle: false,
    statPath: (stats) => stats?.config?.firewall_enabled,
  },
  {
    key: 'rate_limit',
    flagKey: 'rate_limit_enabled',
    label: 'Rate limiting',
    envVar: 'CUTCTX_RATE_LIMIT_ENABLED=true',
    description: 'Token-bucket rate limiting per API key. Configure limits with CUTCTX_RATE_LIMIT_TPM and CUTCTX_RATE_LIMIT_RPM.',
    tier: 'free',
    liveToggle: false,
    statPath: (stats) => stats?.config?.rate_limit,
  },
  {
    key: 'task_aware',
    flagKey: 'task_aware_enabled',
    label: 'Task-aware compression',
    envVar: 'CUTCTX_TASK_AWARE_ENABLED=1',
    description: 'Modulate compression depth based on relevance to the active task — protect critical context, aggressively compress background material.',
    tier: 'free',
    liveToggle: true,
    statPath: (stats) => stats?.config?.task_aware_enabled,
  },
  {
    key: 'dedup',
    flagKey: 'dedup_enabled',
    label: 'Semantic deduplication',
    envVar: 'CUTCTX_DEDUP_ENABLED=1',
    description: 'Detect and collapse repeated content across messages using reversible CCR pointers.',
    tier: 'free',
    liveToggle: true,
    statPath: (stats) => stats?.config?.dedup_enabled,
  },
  {
    key: 'context_budget',
    flagKey: 'context_budget_enabled',
    label: 'Context budget controller',
    envVar: 'CUTCTX_CONTEXT_BUDGET_ENABLED=1',
    description: 'Progressively increase compression as the context window fills — prevents silent truncation and cost spikes.',
    tier: 'free',
    liveToggle: true,
    statPath: (stats) => stats?.config?.context_budget_enabled,
  },
  {
    key: 'profiles',
    flagKey: 'profiles_enabled',
    label: 'Compression profiles',
    envVar: 'CUTCTX_PROFILES_ENABLED=1',
    description: 'Learn per-workspace compression patterns across sessions for improving accuracy over time.',
    tier: 'free',
    liveToggle: true,
    statPath: (stats) => stats?.config?.profiles_enabled,
  },
  {
    key: 'memory',
    flagKey: null,
    label: 'Cross-agent memory',
    envVar: 'Contact sales',
    description: 'Persistent shared memory backend across Claude, Codex, Gemini, and other agents. Semantic search, learn signals, and correction writing.',
    tier: 'enterprise',
    liveToggle: false,
    statPath: () => null,
  },
  {
    key: 'rbac',
    flagKey: null,
    label: 'RBAC & audit trail',
    envVar: 'Contact sales',
    description: 'Role-based access control with admin/operator/viewer tiers. Tamper-evident audit log with hash-chain verification.',
    tier: 'enterprise',
    liveToggle: false,
    statPath: () => null,
  },
];

function emptySection() {
  return { ok: false, data: null, error: 'Loading…' };
}

function summarizeQuotaProviders(quotaData) {
  if (!quotaData || typeof quotaData !== 'object') return [];
  return Object.entries(quotaData)
    .map(([provider, stats]) => ({
      provider,
      limit: formatInteger(stats?.limit_tokens ?? stats?.tokens_per_minute ?? stats?.requests_per_minute ?? 0),
      remaining: formatInteger(stats?.remaining_tokens ?? stats?.remaining_requests ?? 0),
      reset: formatRelativeTime(stats?.reset_at ?? stats?.window_end ?? stats?.reset_time),
    }))
    .slice(0, 6);
}

function normalizeAssignments(rbacData) {
  const raw = rbacData?.assignments;
  if (Array.isArray(raw)) return raw;
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
    <button className="copy-btn" onClick={handleCopy} title="Copy to clipboard">
      {copied ? <CheckCircle2 size={13} /> : <Copy size={13} />}
    </button>
  );
}

function FeatureToggle({ flagKey, enabled, onToggle, busy }) {
  return (
    <button
      className={`feature-toggle ${enabled ? 'feature-toggle-on' : 'feature-toggle-off'}`}
      onClick={() => onToggle(flagKey, !enabled)}
      disabled={busy}
      aria-label={enabled ? 'Disable' : 'Enable'}
    >
      <span className="feature-toggle-knob" />
    </button>
  );
}

function FeatureRow({ feature, stats, liveFlags, onToggle, toggleBusy, restartNeeded }) {
  const isEnterprise = feature.tier === 'enterprise';
  const isLive = feature.liveToggle;
  const isActive = isLive
    ? (liveFlags[feature.flagKey] ?? feature.statPath(stats))
    : feature.statPath(stats);
  const pendingRestart = !isLive && restartNeeded.has(feature.flagKey);

  return (
    <div className="feature-config-row">
      <div className="feature-config-main">
        <div className="feature-config-header">
          <span className="feature-config-name">{feature.label}</span>
          {isEnterprise
            ? <span className="tier-badge tier-enterprise">Enterprise</span>
            : pendingRestart
              ? <span className="tier-badge tier-restart"><RefreshCw size={10} /> Restart required</span>
              : isActive === true
                ? <span className="status-active"><CheckCircle2 size={12} /> Active</span>
                : isActive === false
                  ? <span className="status-inactive"><MinusCircle size={12} /> Inactive</span>
                  : null}
        </div>
        <p className="feature-config-desc">{feature.description}</p>
      </div>
      {!isEnterprise && (
        <div className="feature-config-controls">
          {isLive ? (
            <FeatureToggle
              flagKey={feature.flagKey}
              enabled={!!isActive}
              onToggle={onToggle}
              busy={toggleBusy === feature.flagKey}
            />
          ) : (
            <div className="feature-config-env">
              <code>{feature.envVar}</code>
              <CopyButton text={feature.envVar} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Governance({ searchQuery = '' }) {
  const { stats, loading: statsLoading } = useDashboardData();
  const [sections, setSections] = useState({
    audit: emptySection(),
    orgs: emptySection(),
    quota: emptySection(),
    rbac: emptySection(),
    retention: emptySection(),
    subscription: emptySection(),
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

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
      if (cancelled) return;
      setSections(Object.fromEntries(entries));
      setLoading(false);
      setLastUpdated(new Date().toISOString());
    };
    load();
    const id = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const orgs = sections.orgs.data?.orgs || [];
  const audit = sections.audit.data || {};
  const assignments = useMemo(() => normalizeAssignments(sections.rbac.data), [sections.rbac.data]);
  const quotaProviders = useMemo(() => summarizeQuotaProviders(sections.quota.data), [sections.quota.data]);

  const [liveFlags, setLiveFlags] = useState({});
  const [toggleBusy, setToggleBusy] = useState(null);
  const [restartNeeded, setRestartNeeded] = useState(new Set());

  const handleToggle = useCallback(async (flagKey, value) => {
    setToggleBusy(flagKey);
    try {
      const res = await fetch(getProxyUrl('/admin/config/flags'), {
        method: 'POST',
        headers: { ...getAdminAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ [flagKey]: value }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.applied_live?.[flagKey] != null) {
          setLiveFlags((prev) => ({ ...prev, [flagKey]: value }));
        }
        if (data.restart_required?.[flagKey] != null) {
          setRestartNeeded((prev) => new Set([...prev, flagKey]));
        }
      }
    } catch (_) { /* network error — silently ignore */ }
    setToggleBusy(null);
  }, []);

  const rateLimiter = stats?.rate_limiter;
  const isRateLimitActive = stats?.config?.rate_limit;

  const failedSections = Object.entries(sections).filter(([, s]) => !s.ok && !loading);
  const isNetworkError = failedSections.some(([, s]) =>
    s.error && !s.error.includes('403') && !s.error.includes('503') && !s.error.includes('501'),
  );

  return (
    <section className="page-stack">
      {!loading && failedSections.length > 0 && (
        <div className="alert-card" role="alert">
          {isNetworkError
            ? `Some governance surfaces could not be reached: ${failedSections.map(([k]) => k).join(', ')}.`
            : `${failedSections.length} of ${Object.keys(sections).length} governance surfaces require enterprise entitlements or additional configuration.`}
        </div>
      )}

      {/* Rate limiter — only free live governance feature */}
      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Live control</div>
            <h2>Rate limiting</h2>
          </div>
          <p>
            {isRateLimitActive
              ? 'Token-bucket throttling is active. All LLM proxy paths are rate-limited per API key.'
              : 'Rate limiting is not enabled. Set CUTCTX_RATE_LIMIT_ENABLED=true to activate.'}
          </p>
        </div>
        <div className="metric-grid metric-grid-four" aria-busy={statsLoading}>
          <article className="metric-card metric-card-compact">
            <div className="metric-header">
              <span className="metric-label">Status</span>
              <Zap size={15} />
            </div>
            <div className="metric-value">
              {statsLoading ? '—' : isRateLimitActive ? 'Active' : 'Inactive'}
            </div>
            <div className="metric-footnote">
              {isRateLimitActive ? 'Enforcing per-key limits' : 'Set CUTCTX_RATE_LIMIT_ENABLED=true'}
            </div>
          </article>
          <article className="metric-card metric-card-compact">
            <div className="metric-header">
              <span className="metric-label">Active keys</span>
            </div>
            <div className="metric-value">
              {statsLoading ? '—' : formatInteger(rateLimiter?.active_keys ?? 0)}
            </div>
            <div className="metric-footnote">Keys with live rate state</div>
          </article>
          <article className="metric-card metric-card-compact">
            <div className="metric-header">
              <span className="metric-label">Token limit</span>
            </div>
            <div className="metric-value">
              {statsLoading ? '—' : rateLimiter ? formatInteger(rateLimiter.tokens_per_minute) : '—'}
            </div>
            <div className="metric-footnote">Tokens per minute per key</div>
          </article>
          <article className="metric-card metric-card-compact">
            <div className="metric-header">
              <span className="metric-label">Request limit</span>
            </div>
            <div className="metric-value">
              {statsLoading ? '—' : rateLimiter ? formatInteger(rateLimiter.requests_per_minute) : '—'}
            </div>
            <div className="metric-footnote">Requests per minute per key</div>
          </article>
        </div>
      </div>

      {/* Feature configuration */}
      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Feature configuration</div>
            <h2>Enable optional features</h2>
          </div>
          <p>Set these environment variables before starting the proxy. Restart required for changes to take effect.</p>
        </div>
        <div className="feature-config-list">
          {FEATURE_CONFIG.filter(f => f.label.toLowerCase().includes(searchQuery) || f.description.toLowerCase().includes(searchQuery)).map((feature) => (
            <FeatureRow
              key={feature.key}
              feature={feature}
              stats={stats}
              liveFlags={liveFlags}
              onToggle={handleToggle}
              toggleBusy={toggleBusy}
              restartNeeded={restartNeeded}
            />
          ))}
        </div>
      </div>

      {/* Enterprise surfaces */}
      <div className="dashboard-grid" aria-busy={loading}>
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise</div>
              <h2>Organizations</h2>
            </div>
            <p>Multi-tenant workspace model. Requires enterprise entitlements.</p>
          </div>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Organization</th>
                  <th>Slug</th>
                  <th>Admin</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {orgs.filter(o => !searchQuery || (o.name?.toLowerCase().includes(searchQuery) || o.slug?.toLowerCase().includes(searchQuery) || o.admin_email?.toLowerCase().includes(searchQuery))).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-row">
                      {loading ? 'Loading…' : sections.orgs.ok ? 'No organizations configured.' : 'Enterprise feature — contact sales to enable.'}
                    </td>
                  </tr>
                ) : (
                  orgs.filter(o => !searchQuery || (o.name?.toLowerCase().includes(searchQuery) || o.slug?.toLowerCase().includes(searchQuery) || o.admin_email?.toLowerCase().includes(searchQuery))).slice(0, 8).map((org, index) => (
                    <tr key={org.id || org.slug || index}>
                      <td>{org.name || org.id || '—'}</td>
                      <td>{org.slug || '—'}</td>
                      <td>{org.admin_email || '—'}</td>
                      <td>{formatRelativeTime(org.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Control surfaces</div>
              <h2>Governance status</h2>
            </div>
          </div>
          <div className="stack-list">
            <StatusBullet
              icon={<Zap size={14} />}
              title="Rate limiting"
              detail={isRateLimitActive ? 'Active — token-bucket per key' : 'Inactive — set CUTCTX_RATE_LIMIT_ENABLED=true'}
              active={isRateLimitActive}
            />
            <StatusBullet
              icon={<BadgeCheck size={14} />}
              title="Audit trail"
              detail={sections.audit.ok ? 'Reachable' : 'Enterprise feature'}
              active={sections.audit.ok}
            />
            <StatusBullet
              icon={<KeyRound size={14} />}
              title="RBAC"
              detail={sections.rbac.ok ? `${assignments.length} roles assigned` : 'Enterprise feature'}
              active={sections.rbac.ok}
            />
            <StatusBullet
              icon={<Building2 size={14} />}
              title="Organizations"
              detail={sections.orgs.ok ? `${orgs.length} orgs` : 'Enterprise feature'}
              active={sections.orgs.ok}
            />
            <StatusBullet
              icon={<ShieldCheck size={14} />}
              title="Quota controls"
              detail={sections.quota.ok ? 'Provider ceilings active' : 'Enterprise feature'}
              active={sections.quota.ok}
            />
          </div>
        </aside>
      </div>

      {/* Audit trail (enterprise) */}
      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise · Audit</div>
              <h2>Top admin actions</h2>
            </div>
            <p>Most frequent governance actions from the audit ledger.</p>
          </div>
          <div className="table-shell">
            <table>
              <thead>
                <tr><th>Action</th><th>Count</th></tr>
              </thead>
              <tbody>
                {Object.entries(audit.by_action || {}).filter(([a]) => !searchQuery || a.toLowerCase().includes(searchQuery)).length === 0 ? (
                  <tr>
                    <td colSpan={2} className="empty-row">
                      {loading ? 'Loading…' : sections.audit.ok ? 'No audit activity yet.' : 'Enterprise feature — contact sales to enable.'}
                    </td>
                  </tr>
                ) : (
                  Object.entries(audit.by_action || {}).filter(([a]) => !searchQuery || a.toLowerCase().includes(searchQuery)).slice(0, 8).map(([action, count]) => (
                    <tr key={action}><td>{action}</td><td>{formatInteger(count)}</td></tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise · Audit</div>
              <h2>Recent events</h2>
            </div>
          </div>
          <div className="stack-list">
            {(audit.recent_events || []).length === 0 ? (
              <p className="empty-copy">
                {loading ? 'Loading…' : sections.audit.ok ? 'No recent events.' : 'Enterprise feature.'}
              </p>
            ) : (
              (audit.recent_events || []).slice(0, 5).map((event, index) => (
                <article className="governance-event" key={event.event_id || index}>
                  <div className="governance-event-meta">
                    <strong>{event.action || 'unknown'}</strong>
                    <span>{formatRelativeTime(event.timestamp)}</span>
                  </div>
                  <p>{event.actor || 'admin'}</p>
                </article>
              ))
            )}
          </div>
        </aside>
      </div>

      {/* RBAC (enterprise) */}
      <div className="metric-grid metric-grid-two">
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise · RBAC</div>
              <h2>Role assignments</h2>
            </div>
            <p>Admin, operator, and viewer tiers per user ID.</p>
          </div>
          <div className="table-shell">
            <table>
              <thead>
                <tr><th>User</th><th>Role</th></tr>
              </thead>
              <tbody>
                {assignments.filter(a => !searchQuery || a.user_id?.toLowerCase().includes(searchQuery) || a.role?.toLowerCase().includes(searchQuery)).length === 0 ? (
                  <tr>
                    <td colSpan={2} className="empty-row">
                      {loading ? 'Loading…' : sections.rbac.ok ? 'No roles assigned yet.' : 'Enterprise feature.'}
                    </td>
                  </tr>
                ) : (
                  assignments.filter(a => !searchQuery || a.user_id?.toLowerCase().includes(searchQuery) || a.role?.toLowerCase().includes(searchQuery)).slice(0, 8).map((assignment, index) => (
                    <tr key={assignment.user_id || index}>
                      <td>{assignment.user_id || '—'}</td>
                      <td><span className="transform-chip">{assignment.role || '—'}</span></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise · Quota</div>
              <h2>Provider ceilings</h2>
            </div>
            <p>Per-provider request and token quotas.</p>
          </div>
          <div className="table-shell">
            <table>
              <thead>
                <tr><th>Provider</th><th>Limit</th><th>Remaining</th><th>Reset</th></tr>
              </thead>
              <tbody>
                {quotaProviders.filter(q => !searchQuery || q.provider?.toLowerCase().includes(searchQuery)).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-row">
                      {loading ? 'Loading…' : sections.quota.ok ? 'No quota configured.' : 'Enterprise feature.'}
                    </td>
                  </tr>
                ) : (
                  quotaProviders.filter(q => !searchQuery || q.provider?.toLowerCase().includes(searchQuery)).map((row, index) => (
                    <tr key={row.provider || index}>
                      <td>{row.provider}</td>
                      <td>{row.limit}</td>
                      <td>{row.remaining}</td>
                      <td>{row.reset}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  );
}

function MetricCard({ icon, label, value, note }) {
  return (
    <article className="metric-card">
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      <div className="metric-value">{value}</div>
      {note && <div className="metric-footnote">{note}</div>}
    </article>
  );
}

function StatusBullet({ icon, title, detail, active }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '12px 0', borderBottom: '1px solid var(--border-default)' }}>
      <div className={`status-bullet-indicator ${active ? 'status-bullet-active' : 'status-bullet-inactive'}`}>
        {icon}
      </div>
      <div>
        <div className="status-bullet-title">{title}</div>
        <div className="status-bullet-detail">{detail}</div>
      </div>
    </div>
  );
}
