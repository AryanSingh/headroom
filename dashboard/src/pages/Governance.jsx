import {
  BadgeCheck,
  Building2,
  Clock3,
  KeyRound,
  Layers3,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson } from '../lib/use-dashboard-data';

const GOVERNANCE_PATHS = {
  audit: '/audit/stats',
  orgs: '/orgs',
  quota: '/quota',
  rbac: '/rbac/roles',
  retention: '/retention/stats',
  subscription: '/subscription-window',
};

function emptySection() {
  return { ok: false, data: null, error: 'Loading…' };
}

function summarizeQuotaProviders(quotaData) {
  if (!quotaData || typeof quotaData !== 'object') {
    return [];
  }

  return Object.entries(quotaData)
    .map(([provider, stats]) => {
      if (!stats || typeof stats !== 'object') {
        return {
          provider,
          limit: '—',
          remaining: '—',
          reset: '—',
        };
      }

      return {
        provider,
        limit: formatInteger(
          stats.limit_tokens ??
            stats.tokens_per_minute ??
            stats.requests_per_minute ??
            0,
        ),
        remaining: formatInteger(
          stats.remaining_tokens ?? stats.remaining_requests ?? 0,
        ),
        reset: formatRelativeTime(
          stats.reset_at ?? stats.window_end ?? stats.reset_time,
        ),
      };
    })
    .slice(0, 6);
}

function summarizeRetention(retentionData) {
  const stats = retentionData?.retention;
  if (!stats || typeof stats !== "object") {
    return [];
  }

  return Object.entries(stats)
    .filter(([, value]) => value != null && value !== '')
    .slice(0, 6)
    .map(([key, value]) => ({
      key,
      value:
        typeof value === 'number'
          ? formatInteger(value)
          : typeof value === 'boolean'
            ? value
              ? 'Enabled'
              : 'Disabled'
            : String(value),
    }));
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

function countAvailableSurfaces(sections) {
  return Object.values(sections).filter((section) => section.ok).length;
}

export default function Governance() {
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

      if (cancelled) {
        return;
      }

      setSections(Object.fromEntries(entries));
      setLoading(false);
      setLastUpdated(new Date().toISOString());
    };

    load();
    const id = setInterval(load, 15000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const orgs = sections.orgs.data?.orgs || [];
  const audit = sections.audit.data || {};
  const assignments = useMemo(
    () => normalizeAssignments(sections.rbac.data),
    [sections.rbac.data],
  );
  const quotaProviders = useMemo(
    () => summarizeQuotaProviders(sections.quota.data),
    [sections.quota.data],
  );
  const retentionSummary = useMemo(
    () => summarizeRetention(sections.retention.data),
    [sections.retention.data],
  );
  const availableSurfaces = countAvailableSurfaces(sections);
  const sectionErrors = Object.entries(sections)
    .filter(([, section]) => !section.ok && !loading)
    .map(([key, section]) => `${key}: ${section.error}`);

  return (
    <section className="page-stack">
      {sectionErrors.length > 0 ? (
        <div className="alert-card" role="alert">
          Some enterprise surfaces are unavailable in this environment: {sectionErrors.join(' • ')}
        </div>
      ) : null}

      <div className="metric-grid metric-grid-four" aria-busy={loading}>
        <MetricCard
          icon={<Building2 size={18} />}
          label="Organizations"
          value={loading ? '—' : formatInteger(orgs.length)}
          note="Workspace model entities exposed"
        />
        <MetricCard
          icon={<BadgeCheck size={18} />}
          label="Audit events"
          value={loading ? '—' : formatInteger(audit.total_events)}
          note="Tamper-evident operator trail"
        />
        <MetricCard
          icon={<KeyRound size={18} />}
          label="Role assignments"
          value={loading ? '—' : formatInteger(assignments.length)}
          note="RBAC entries visible to operators"
        />
        <MetricCard
          icon={<ShieldCheck size={18} />}
          label="Control planes"
          value={loading ? '—' : `${availableSurfaces}/${Object.keys(GOVERNANCE_PATHS).length}`}
          note={lastUpdated ? `Refreshed ${formatRelativeTime(lastUpdated)}` : 'Polling every 15 seconds'}
        />
      </div>

      <div className="dashboard-grid" aria-busy={loading}>
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise model</div>
              <h2>Organizations and workspaces</h2>
            </div>
            <p>Expose the multi-tenant control plane instead of leaving it hidden behind raw admin APIs.</p>
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
                {orgs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-row">
                      {loading
                        ? 'Loading organizations…'
                        : sections.orgs.ok
                          ? 'No organizations configured yet.'
                          : sections.orgs.error}
                    </td>
                  </tr>
                ) : (
                  orgs.slice(0, 8).map((org, index) => (
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
              <div className="eyebrow">Control status</div>
              <h2>Governance surfaces</h2>
            </div>
          </div>

          <div className="stack-list">
            <StatusBullet
              title="Audit trail"
              detail={
                sections.audit.ok
                  ? 'Audit statistics are reachable from the dashboard.'
                  : sections.audit.error
              }
            />
            <StatusBullet
              title="RBAC"
              detail={
                sections.rbac.ok
                  ? 'Role assignments are exposed to the operator surface.'
                  : sections.rbac.error
              }
            />
            <StatusBullet
              title="Retention"
              detail={
                sections.retention.ok
                  ? 'Retention controls are configured and queryable.'
                  : sections.retention.error
              }
            />
            <StatusBullet
              title="Quota and subscription"
              detail={
                sections.quota.ok || sections.subscription.ok
                  ? 'Runtime provider ceilings are visible here.'
                  : [sections.quota.error, sections.subscription.error]
                      .filter(Boolean)
                      .join(' • ')
              }
            />
          </div>
        </aside>
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Audit analysis</div>
              <h2>Top admin actions</h2>
            </div>
            <p>Most frequent governance actions from the audit ledger sample.</p>
          </div>

          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(audit.by_action || {}).length === 0 ? (
                  <tr>
                    <td colSpan={2} className="empty-row">
                      {loading
                        ? 'Loading audit statistics…'
                        : sections.audit.ok
                          ? 'No audit activity recorded yet.'
                          : sections.audit.error}
                    </td>
                  </tr>
                ) : (
                  Object.entries(audit.by_action || {})
                    .slice(0, 8)
                    .map(([action, count]) => (
                      <tr key={action}>
                        <td>{action}</td>
                        <td>{formatInteger(count)}</td>
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
              <div className="eyebrow">Recent activity</div>
              <h2>Last operator events</h2>
            </div>
          </div>

          <div className="stack-list">
            {(audit.recent_events || []).length === 0 ? (
              <p className="empty-copy">
                {loading
                  ? 'Loading recent audit rows…'
                  : sections.audit.ok
                    ? 'No recent events available.'
                    : sections.audit.error}
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

      <div className="metric-grid metric-grid-two">
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">RBAC</div>
              <h2>Role assignments</h2>
            </div>
            <p>Current admin access assignments, normalized for both list and map responses.</p>
          </div>

          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="empty-row">
                      {loading
                        ? 'Loading RBAC assignments…'
                        : sections.rbac.ok
                          ? 'No roles assigned yet.'
                          : sections.rbac.error}
                    </td>
                  </tr>
                ) : (
                  assignments.slice(0, 8).map((assignment, index) => (
                    <tr key={assignment.user_id || assignment.userId || index}>
                      <td>{assignment.user_id || assignment.userId || '—'}</td>
                      <td>
                        <span className="transform-chip">
                          {assignment.role || assignment.value || 'viewer'}
                        </span>
                      </td>
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
              <div className="eyebrow">Retention and runtime ceilings</div>
              <h2>Operator controls</h2>
            </div>
            <p>Best-effort visibility into data lifecycle and provider limits.</p>
          </div>

          <div className="governance-snapshot-grid">
            <div className="code-panel">
              <div className="governance-panel-title">
                <Clock3 size={16} />
                Retention
              </div>
              {retentionSummary.length === 0 ? (
                <p className="empty-copy">
                  {loading
                    ? 'Loading retention settings…'
                    : sections.retention.ok
                      ? 'No retention configuration returned.'
                      : sections.retention.error}
                </p>
              ) : (
                retentionSummary.map((item) => (
                  <div key={item.key} className="governance-kv">
                    <span>{item.key}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))
              )}
            </div>

            <div className="code-panel">
              <div className="governance-panel-title">
                <Layers3 size={16} />
                Quota
              </div>
              {quotaProviders.length === 0 ? (
                <p className="empty-copy">
                  {loading
                    ? 'Loading quota providers…'
                    : sections.quota.ok
                      ? 'No quota data returned.'
                      : sections.quota.error}
                </p>
              ) : (
                quotaProviders.map((provider) => (
                  <div key={provider.provider} className="governance-kv">
                    <span>{provider.provider}</span>
                    <strong>{provider.remaining} / {provider.limit}</strong>
                  </div>
                ))
              )}
            </div>
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
      <div className="metric-footnote">{note}</div>
    </article>
  );
}

function StatusBullet({ title, detail }) {
  return (
    <article className="status-bullet">
      <strong>{title}</strong>
      <p>{detail}</p>
    </article>
  );
}
