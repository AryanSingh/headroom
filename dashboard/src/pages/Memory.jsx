import { BrainCircuit, History, NotebookTabs, ScanSearch } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { formatInteger, formatRelativeTime } from '../lib/format';
import { fetchDashboardJson, useDashboardData } from '../lib/use-dashboard-data';

export default function Memory() {
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
          if (fetchErr.message && fetchErr.message.includes('404')) {
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

  return (
    <section className="page-stack">

      {error && <div className="alert-card" role="alert">Failed to load memory data: {error}</div>}

      <div className="metric-grid metric-grid-four" aria-busy={loading}>
        <MetricCard
          icon={<BrainCircuit size={18} />}
          label="Insights"
          value={loading ? '—' : formatInteger(insights.length)}
          note="Semantic facts stored in memory"
        />
        <MetricCard
          icon={<NotebookTabs size={18} />}
          label="Corrections"
          value={loading ? '—' : formatInteger(corrections.length)}
          note="Corrective memory entries and learn signals"
        />
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
      </div>

      <div className="dashboard-grid" aria-busy={loading}>
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Recent memory rows</div>
              <h2>Persisted memory entries</h2>
            </div>
            <p>Live memory records as exposed by the running proxy.</p>
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
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="empty-row">
                      {loading ? 'Loading memories…' : 'No memories recorded yet.'}
                    </td>
                  </tr>
                ) : (
                  items.map((item, index) => (
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
              <div className="eyebrow">Operational notes</div>
              <h2>What users can do here</h2>
            </div>
          </div>
          <div className="stack-list">
            <StatusBullet title="Cross-agent memory" detail="Stored facts can be reused across future sessions." />
            <StatusBullet title="Learn loop" detail="Corrections surface where Cutctx can steer future agent behavior." />
            <StatusBullet title="Context tooling" detail="RTK and related tools are surfaced alongside memory activity." />
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
