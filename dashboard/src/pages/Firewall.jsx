import { Shield, ShieldAlert, CheckCircle } from 'lucide-react';
import { useEffect, useState } from 'react';

// Audit-Deep-2026-06-21 Blocker 4: Firewall.jsx was a static
// mockup. It now reads from /v1/firewall/stats (the proxy's
// real LLM firewall stats endpoint) and /v1/audit/events
// (filtered to firewall.* actions) for the recent
// interceptions table. The hardcoded values (27 patterns,
// 143 blocks) are gone.

export default function Firewall() {
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [statsRes, auditRes] = await Promise.all([
          fetch('/v1/firewall/stats?cached=1').then((r) => r.json()).catch(() => null),
          fetch('/v1/audit/events?action_prefix=firewall&limit=20').then((r) => r.json()).catch(() => []),
        ]);
        if (cancelled) return;
        setStats(statsRes);
        setEvents(Array.isArray(auditRes) ? auditRes : []);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || String(e));
      } finally {
        if (!cancelled) setLoading(false);
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
    <div>
      <div className="page-header">
        <h2>Firewall & Security</h2>
        <p className="text-secondary">Manage LLM injection rules and PII redaction</p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded border border-red-600 bg-red-900/30 text-red-200 px-4 py-2 text-sm mb-4"
        >
          Failed to load firewall stats: {error}
        </div>
      )}

      <div className="grid grid-cols-3 mb-4">
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <Shield size={18} /> Active Patterns
          </div>
          <div className="text-2xl">
            {loading ? '—' : (stats?.patterns_loaded ?? '—')}
          </div>
          <div className="text-sm mt-4 text-secondary">Signatures loaded</div>
        </div>
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <ShieldAlert size={18} /> Blocks (session)
          </div>
          <div className="text-2xl">
            {loading ? '—' : (stats?.blocks ?? 0)}
          </div>
          <div className="text-sm text-secondary mt-4">
            {loading ? '' : `${stats?.blocks_today ?? 0} in the last 24h`}
          </div>
        </div>
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <CheckCircle size={18} /> Status
          </div>
          <div className="text-2xl">
            {loading
              ? '—'
              : stats?.enabled
                ? 'Active'
                : 'Disabled'}
          </div>
          <div className="text-sm text-secondary mt-4">
            {stats?.enabled
              ? 'PII + injection + jailbreak scanning'
              : 'Set CUTCTX_FIREWALL_ENABLED=1 to enable'}
          </div>
        </div>
      </div>

      <div className="glass-panel">
        <div className="flex justify-between items-center mb-4">
          <h3 style={{ color: '#fff' }}>Recent Interceptions</h3>
          <button
            className="btn btn-primary"
            onClick={() => alert(
              'Custom firewall rules are configured via env vars. See docs/security.md.'
            )}
            aria-label="Add custom firewall rule"
          >
            Add Custom Rule
          </button>
        </div>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-secondary text-center py-4">
                    {loading ? 'Loading…' : 'No firewall events recorded yet.'}
                  </td>
                </tr>
              ) : (
                events.map((e, i) => (
                  <tr key={e.event_id || i}>
                    <td>{e.timestamp || '—'}</td>
                    <td>
                      <code>{e.action || '—'}</code>
                    </td>
                    <td>{e.actor || '—'}</td>
                    <td>
                      <code className="text-xs">
                        {JSON.stringify(e.detail || {}).slice(0, 80)}
                      </code>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
