import { AlertTriangle, Shield, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson } from '../lib/use-dashboard-data';

export default function Firewall() {
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [statsResponse, eventsResponse] = await Promise.all([
          fetchDashboardJson('/v1/firewall/stats?cached=1').catch(() => null),
          fetchDashboardJson('/v1/audit/events?action_prefix=firewall&limit=20').catch(() => []),
        ]);

        if (cancelled) {
          return;
        }

        setStats(statsResponse);
        setEvents(Array.isArray(eventsResponse) ? eventsResponse : []);
        setError(null);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setError(loadError.message || String(loadError));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <section className="page-stack">
      <div className="page-header-card">
        <div>
          <div className="eyebrow">Governance</div>
          <h1>Firewall and request security</h1>
          <p>
            Request interception, PII-aware scanning, audit events, and operator posture. This
            page keeps the original security surface and makes it readable enough to actually use.
          </p>
        </div>
        <div className="hero-sidecard">
          <div className="hero-sidecard-label">Current status</div>
          <div className="hero-sidecard-value">{loading ? '—' : stats?.enabled ? 'Active' : 'Disabled'}</div>
          <p>{stats?.enabled ? 'PII, jailbreak, and injection scanning enabled.' : 'Set CUTCTX_FIREWALL_ENABLED=1 to enable.'}</p>
        </div>
      </div>

      {error && <div className="alert-card">Failed to load firewall data: {error}</div>}

      <div className="metric-grid metric-grid-four">
        <MetricCard
          icon={<Shield size={18} />}
          label="Patterns"
          value={loading ? '—' : formatInteger(stats?.patterns_loaded)}
          note="Loaded signature rules"
        />
        <MetricCard
          icon={<ShieldAlert size={18} />}
          label="Blocks"
          value={loading ? '—' : formatInteger(stats?.blocks)}
          note={`${formatInteger(stats?.blocks_today)} in the last 24h`}
        />
        <MetricCard
          icon={<ShieldCheck size={18} />}
          label="Mode"
          value={loading ? '—' : stats?.enabled ? 'Active' : 'Disabled'}
          note="Live firewall posture"
        />
        <MetricCard
          icon={<AlertTriangle size={18} />}
          label="Events"
          value={loading ? '—' : formatInteger(events.length)}
          note="Recent audit trail rows"
        />
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Recent interceptions</div>
              <h2>Firewall event tape</h2>
            </div>
            <p>Recent firewall-related audit events from the proxy.</p>
          </div>

          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-row">
                      {loading ? 'Loading events…' : 'No firewall events recorded yet.'}
                    </td>
                  </tr>
                ) : (
                  events.map((event, index) => (
                    <tr key={event.event_id || index}>
                      <td>{event.timestamp ? formatRelativeTime(event.timestamp) : '—'}</td>
                      <td>{event.action || '—'}</td>
                      <td>{event.actor || '—'}</td>
                      <td className="detail-cell">
                        <code>{JSON.stringify(event.detail || {}).slice(0, 140)}</code>
                      </td>
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
              <div className="eyebrow">Operator notes</div>
              <h2>Security surface</h2>
            </div>
          </div>
          <div className="stack-list">
            <StatusBullet title="Pattern inventory" detail="Tracks loaded signatures and active scanning posture." />
            <StatusBullet title="Audit trail" detail="Surfaces recent firewall actions through the audit event tape." />
            <StatusBullet title="Policy controls" detail="Environment-driven configuration remains the source of truth." />
          </div>
        </aside>
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
