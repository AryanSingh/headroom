import { AlertTriangle, Play, Shield, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson } from '../lib/use-dashboard-data';
import { getAdminAuthHeaders } from '../lib/admin-auth';
import { getProxyUrl } from '../lib/api';

export default function Firewall({ searchQuery = '' }) {
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scanText, setScanText] = useState('');
  const [scanResult, setScanResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState(null);

  const handleScan = async () => {
    if (!scanText.trim()) return;
    setScanning(true);
    setScanResult(null);
    setScanError(null);
    try {
      const response = await fetch(getProxyUrl('/firewall/scan'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAdminAuthHeaders() },
        body: JSON.stringify({ text: scanText }),
      });
      if (!response.ok) throw new Error(`Scan returned ${response.status}`);
      setScanResult(await response.json());
    } catch (e) {
      setScanError(e.message || String(e));
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [statsResponse, eventsResponse] = await Promise.all([
          fetchDashboardJson('/firewall/status?cached=1').catch(() => null),
          fetchDashboardJson('/audit/events?action_prefix=firewall&limit=20').catch(() => []),
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

      {error && <div className="alert-card" role="alert">Failed to load firewall data: {error}</div>}

      <div className="metric-grid metric-grid-four" aria-busy={loading}>
        <MetricCard
          icon={<Shield size={18} />}
          label="Patterns"
          value={loading ? '—' : formatInteger(stats?.patterns_loaded)}
          note="Loaded signature rules"
        />
        <MetricCard
          icon={<ShieldAlert size={18} />}
          label="Blocks"
          value={loading ? '—' : stats?.blocks == null ? '—' : formatInteger(stats?.blocks)}
          note={
            stats?.telemetry_available
              ? `${formatInteger(stats?.blocks_today)} in the last 24h`
              : 'Block counters not yet tracked by the runtime'
          }
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

      <div className="dashboard-grid" aria-busy={loading}>
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
                {events.filter(e => !searchQuery || e.action?.toLowerCase().includes(searchQuery) || e.actor?.toLowerCase().includes(searchQuery) || JSON.stringify(e.detail || {}).toLowerCase().includes(searchQuery)).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-row">
                      {loading ? 'Loading events…' : 'No firewall events recorded yet.'}
                    </td>
                  </tr>
                ) : (
                  events.filter(e => !searchQuery || e.action?.toLowerCase().includes(searchQuery) || e.actor?.toLowerCase().includes(searchQuery) || JSON.stringify(e.detail || {}).toLowerCase().includes(searchQuery)).map((event, index) => (
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
            <StatusBullet
              title="Prompt injection"
              detail={`Detection: ${stats?.config?.block_injection ? 'enabled' : 'disabled'}. Intercepts attempts to override system instructions.`}
            />
            <StatusBullet
              title="Jailbreak detection"
              detail={`Detection: ${stats?.config?.block_jailbreak ? 'enabled' : 'disabled'}. Catches common restriction-bypass patterns.`}
            />
            <StatusBullet
              title="PII redaction"
              detail={`Redaction: ${stats?.config?.block_pii ? 'enabled' : 'disabled'}. Strips emails, SSNs, and credit card numbers in-flight.`}
            />
            <StatusBullet
              title="Policy controls"
              detail={`Custom patterns: ${formatInteger(stats?.config?.custom_patterns || 0)} · Allowed domains: ${formatInteger(stats?.config?.allowed_domains || 0)}`}
            />
          </div>
        </aside>
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Live scanner</div>
              <h2>Test text against firewall rules</h2>
            </div>
            <p>Paste any prompt or message to check for violations before it reaches the model.</p>
          </div>

          {stats && !stats.enabled && (
            <div className="alert-card" role="status">
              Firewall is not initialized on this proxy. Enable it by setting <code>CUTCTX_FIREWALL=1</code> and restarting.
            </div>
          )}

          {scanError && <div className="alert-card" role="alert">{scanError}</div>}

          <label className="field">
            <span>Text to scan</span>
            <textarea
              value={scanText}
              onChange={(e) => setScanText(e.target.value)}
              rows={5}
              placeholder="Paste a prompt, tool output, or user message to check for injections, jailbreaks, or PII."
            />
          </label>

          <div className="playground-actions">
            <button
              className="primary-button"
              onClick={handleScan}
              disabled={scanning || !scanText.trim()}
              type="button"
            >
              <Play size={16} />
              {scanning ? 'Scanning…' : 'Scan text'}
            </button>
          </div>

          {scanResult && (
            <div className="table-shell" style={{ marginTop: '1rem' }}>
              <table>
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Confidence</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {scanResult.violations.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="empty-row">No violations detected.</td>
                    </tr>
                  ) : (
                    scanResult.violations.map((v, i) => (
                      <tr key={i}>
                        <td><span className="transform-chip">{v.kind}</span></td>
                        <td>{Math.round(v.confidence * 100)}%</td>
                        <td>{v.description}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: scanResult.block ? '#f87171' : '#6ee7b7' }}>
                {scanResult.block ? 'This request would be blocked.' : 'This request would be allowed.'}
              </div>
            </div>
          )}
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Configuration</div>
              <h2>Active rule sets</h2>
            </div>
          </div>
          <div className="stack-list">
            <StatusBullet
              title={`Patterns loaded: ${stats ? formatInteger(stats.patterns_loaded) : '—'}`}
              detail="Total injection, jailbreak, PII, and custom signatures active."
            />
            <StatusBullet
              title="Streaming redaction"
              detail={stats?.config?.redact_streaming ? 'Enabled — PII stripped from streaming responses.' : 'Disabled.'}
            />
            <StatusBullet
              title="Exfil patterns"
              detail="Always-on data-exfiltration detection regardless of tier."
            />
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
