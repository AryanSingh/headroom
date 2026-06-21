import { BrainCircuit, FileText } from 'lucide-react';
import { useEffect, useState } from 'react';

// Audit-Deep-2026-06-21 Blocker 4: Memory.jsx was a static
// mockup. It now reads from /v1/memory/query and surfaces
// real insights and corrections. The hardcoded 4,192 / 12
// numbers are gone.

export default function Memory() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch('/v1/memory/query?limit=20');
        const data = await res.json();
        if (cancelled) return;
        setItems(Array.isArray(data) ? data : data?.items || []);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const insights = items.filter((i) => !i.correction);
  const corrections = items.filter((i) => i.correction);

  return (
    <div>
      <div className="page-header">
        <h2>Memory & Learn</h2>
        <p className="text-secondary">
          Cross-session agent institutional memory and semantic corrections
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded border border-red-600 bg-red-900/30 text-red-200 px-4 py-2 text-sm mb-4"
        >
          Failed to load memory: {error}
        </div>
      )}

      <div className="grid grid-cols-3 mb-4">
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <BrainCircuit size={18} /> Extracted Insights
          </div>
          <div className="text-2xl">
            {loading ? '—' : insights.length.toLocaleString()}
          </div>
          <div className="text-sm mt-4 text-secondary">Total semantic facts</div>
        </div>
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <FileText size={18} /> Active Corrections
          </div>
          <div className="text-2xl">
            {loading ? '—' : corrections.length.toLocaleString()}
          </div>
          <div className="text-sm text-success mt-4">Injected via CLAUDE.md</div>
        </div>
      </div>

      <div className="glass-panel">
        <div className="flex justify-between items-center mb-4">
          <h3 style={{ color: '#fff' }}>Recent Memories</h3>
          <button
            className="btn"
            onClick={() => alert(
              'Manual extraction is run via: cutctx memory extract. See docs/memory.md.'
            )}
            aria-label="Run manual memory extraction"
          >
            Run Manual Extraction
          </button>
        </div>
        <div className="table-responsive">
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
                  <td colSpan={3} className="text-secondary text-center py-4">
                    {loading ? 'Loading…' : 'No memories recorded yet.'}
                  </td>
                </tr>
              ) : (
                items.map((it, i) => (
                  <tr key={it.id || i}>
                    <td>{it.text || it.content || '—'}</td>
                    <td>
                      <code className="text-xs">{it.source || '—'}</code>
                    </td>
                    <td>{it.created_at || '—'}</td>
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
