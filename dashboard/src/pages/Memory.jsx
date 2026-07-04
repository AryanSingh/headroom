import { BrainCircuit, History, Lock, NotebookTabs, ScanSearch } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson, useDashboardData } from '../lib/use-dashboard-data';

export default function Memory({ searchQuery = '' }) {
  const { stats } = useDashboardData();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        let data = [];
        try {
          data = await fetchDashboardJson('/v1/memory/query?limit=20');
        } catch (fetchErr) {
          if (fetchErr.message && (fetchErr.message.includes('404') || fetchErr.message.includes('501') || fetchErr.message.includes('503'))) {
            data = [];
          } else {
            throw fetchErr;
          }
        }

        if (cancelled) {
          return;
        }
        setItems(Array.isArray(data) ? data : data?.items || []);
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
    const id = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const corrections = useMemo(() => items.filter((item) => item.correction), [items]);
  const insights = useMemo(() => items.filter((item) => !item.correction), [items]);
  const contextTool = stats?.context_tool?.stats || {};
  const memoryEnabled = stats?.config?.memory;
  const memoryIsEE = !loading && items.length === 0 && !error && !memoryEnabled;

  return (
    <section className="page-stack">

      {error && <div className="alert-card" role="alert">Failed to load memory data: {error}</div>}

      {/* Context-tool stats — conditionally shown if available */}
      <div className="metric-grid metric-grid-four" aria-busy={loading}>
        {stats?.context_tool && (
          <>
            <MetricCard
              icon={<ScanSearch size={18} />}
              label="RTK commands"
              value={formatInteger(contextTool.total_commands)}
              note={`${formatInteger(contextTool.tokens_saved)} tokens avoided`}
            />
            <MetricCard
              icon={<History size={18} />}
              label="Session savings"
              value={
                contextTool.session?.tokens_saved != null
                  ? formatInteger(contextTool.session.tokens_saved)
                  : '—'
              }
              note="Context-tool session contribution"
            />
          </>
        )}
        <MetricCard
          icon={<BrainCircuit size={18} />}
          label="Insights"
          value={loading ? '—' : memoryIsEE ? '—' : formatInteger(insights.length)}
          note="Semantic facts stored across sessions"
        />
        <MetricCard
          icon={<NotebookTabs size={18} />}
          label="Corrections"
          value={loading ? '—' : memoryIsEE ? '—' : formatInteger(corrections.length)}
          note="Learn signals and corrective entries"
        />
      </div>

      {/* Enterprise gate card */}
      {memoryIsEE && (
        <div className="panel ee-gate-panel">
          <div className="ee-gate-icon"><Lock size={22} /></div>
          <div className="ee-gate-body">
            <div className="eyebrow">Enterprise feature</div>
            <h2>Cross-agent memory</h2>
            <p>
              Persistent shared memory lets Claude, Codex, Gemini, and other agents
              share knowledge across sessions — semantic search, learn signals, and
              correction writing into AGENTS.md / CLAUDE.md. Contact sales to enable.
            </p>
            <div className="ee-gate-features">
              <span>Semantic search across sessions</span>
              <span>Correction write-back to agent config</span>
              <span>Cross-agent knowledge sharing</span>
              <span>Session mining and pattern learning</span>
            </div>
          </div>
        </div>
      )}

      {/* Memory table — shown when enabled */}
      {!memoryIsEE && (
        <div className="dashboard-grid" aria-busy={loading}>
          <section className="panel panel-wide">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Memory</div>
                <h2>Persisted entries</h2>
              </div>
              <p>Live memory records from the running proxy.</p>
            </div>
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Memory</th>
                    <th>Source</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {items.filter(i => !searchQuery || (i.text || i.content)?.toLowerCase().includes(searchQuery) || i.source?.toLowerCase().includes(searchQuery)).length === 0 ? (
                    <tr>
                      <td colSpan={3} className="empty-row">
                        {loading ? 'Loading memories…' : 'No memories recorded yet.'}
                      </td>
                    </tr>
                  ) : (
                    items.filter(i => !searchQuery || (i.text || i.content)?.toLowerCase().includes(searchQuery) || i.source?.toLowerCase().includes(searchQuery)).map((item, index) => (
                      <tr key={item.id || index}>
                        <td>{item.text || item.content || '—'}</td>
                        <td>
                          <span className="transform-chip">{item.source || 'unknown'}</span>
                        </td>
                        <td>{item.created_at ? formatRelativeTime(item.created_at) : '—'}</td>
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
                <div className="eyebrow">How it works</div>
                <h2>Memory system</h2>
              </div>
            </div>
            <div className="stack-list">
              <StatusBullet title="Cross-agent memory" detail="Stored facts reused across sessions by any connected agent." />
              <StatusBullet title="Learn loop" detail="Corrections surface where the proxy can steer future agent behavior." />
              <StatusBullet title="Context tooling" detail="RTK and related tools are tracked alongside memory activity." />
            </div>
          </aside>
        </div>
      )}
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
