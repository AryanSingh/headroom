import { Activity, Zap, ShieldAlert, Cpu, Download } from 'lucide-react';
import { useEffect, useState } from 'react';

// Audit-Deep-2026-06-21 Blocker 4: Overview.jsx was a static
// mockup. The page now fetches real data from the proxy's
// /stats endpoint and renders per-source savings, recent
// request counts, and provider health. The hardcoded mock
// values (4,289 Requests/min, 68.4% Compression Savings, etc.)
// are gone.

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [statsRes, healthRes] = await Promise.all([
          fetch('/stats?cached=1').then((r) => r.json()),
          fetch('/health').then((r) => r.json()),
        ]);
        if (cancelled) return;
        setStats({ ...statsRes, health: healthRes });
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Derive the per-source USD totals from the funnel-shaped
  // response. Falls back to 0 when the proxy is offline.
  const tokens = stats?.tokens || {};
  const requests = stats?.requests || {};
  const savingsBySource = stats?.savings_by_source || {};
  const providers = Object.entries(requests?.by_provider || {});

  const handleExportCSV = () => {
    const headers = [
      "Source",
      "Tokens Saved",
      "USD Saved",
    ];
    const rows = Object.entries(savingsBySource).map(
      ([source, vals]) => [
        source,
        vals?.tokens || 0,
        vals?.usd || 0,
      ]
    );
    const csvContent = [
      headers.join(","),
      ...rows.map((r) => r.map((cell) => `"${cell}"`).join(",")),
    ].join("\n");
    const blob = new Blob([csvContent], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "savings_by_source.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {error && (
        <div
          role="alert"
          className="rounded border border-red-600 bg-red-900/30 text-red-200 px-4 py-2 text-sm"
        >
          Failed to load stats: {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat
          icon={<Activity className="text-blue-400" />}
          label="Requests (today)"
          value={
            loading
              ? "—"
              : (requests?.total || 0).toLocaleString()
          }
        />
        <Stat
          icon={<Zap className="text-green-400" />}
          label="Tokens saved (today)"
          value={
            loading
              ? "—"
              : (tokens?.saved || 0).toLocaleString()
          }
        />
        <Stat
          icon={<Cpu className="text-yellow-400" />}
          label="USD saved (today)"
          value={
            loading
              ? "—"
              : `$${(tokens?.usd_saved || 0).toFixed(2)}`
          }
        />
        <Stat
          icon={<ShieldAlert className="text-purple-400" />}
          label="Health"
          value={
            loading
              ? "—"
              : stats?.health?.status || "unknown"
          }
        />
      </div>

      <div className="bg-surface rounded-lg border border-border p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-medium text-gray-200">
            Per-source savings (today)
          </h2>
          <button
            onClick={handleExportCSV}
            disabled={!savingsBySource || Object.keys(savingsBySource).length === 0}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded transition-colors"
            aria-label="Export per-source savings as CSV"
          >
            <Download size={16} />
            Export CSV
          </button>
        </div>
        {Object.keys(savingsBySource).length === 0 ? (
          <p className="text-sm text-gray-500">No savings recorded yet today.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase tracking-wide">
                <th className="px-2 py-2 font-medium">Source</th>
                <th className="px-2 py-2 font-medium text-right">Tokens saved</th>
                <th className="px-2 py-2 font-medium text-right">USD saved</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {Object.entries(savingsBySource).map(([source, vals]) => (
                <tr key={source}>
                  <td className="px-2 py-2 text-gray-300">{source}</td>
                  <td className="px-2 py-2 text-right text-gray-200 font-mono">
                    {(vals?.tokens || 0).toLocaleString()}
                  </td>
                  <td className="px-2 py-2 text-right text-gray-200 font-mono">
                    ${(vals?.usd || 0).toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-surface rounded-lg border border-border p-4">
        <h2 className="text-lg font-medium text-gray-200 mb-3">
          Upstream providers (today)
        </h2>
        {providers.length === 0 ? (
          <p className="text-sm text-gray-500">
            No upstream calls recorded today.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase tracking-wide">
                <th className="px-2 py-2 font-medium">Provider</th>
                <th className="px-2 py-2 font-medium text-right">Requests</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {providers.map(([name, count]) => (
                <tr key={name}>
                  <td className="px-2 py-2 text-gray-300">{name}</td>
                  <td className="px-2 py-2 text-right text-gray-200 font-mono">
                    {count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ icon, label, value }) {
  return (
    <div className="bg-surface rounded-lg border border-border p-4 flex items-center gap-3">
      <div className="p-2 rounded bg-bg">{icon}</div>
      <div className="min-w-0">
        <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
        <div className="text-xl font-semibold text-gray-100 truncate" title={String(value)}>
          {value}
        </div>
      </div>
    </div>
  );
}
