import { Activity, Zap, ShieldAlert, Cpu, Download } from 'lucide-react';

export default function Overview() {
  const telemetryData = [
    { provider: "Anthropic (Claude 3.5 Sonnet)", status: "Healthy", latency: "241ms", load: "42%" },
    { provider: "OpenAI (GPT-4o)", status: "Healthy", latency: "310ms", load: "28%" },
    { provider: "AWS Bedrock (Meta Llama 3)", status: "Failing Over", latency: "--", load: "0%" }
  ];

  const handleExportCSV = () => {
    const headers = ["Upstream Provider", "Status", "Latency (p99)", "Load"];
    const rows = telemetryData.map(node => [
      node.provider, 
      node.status, 
      node.latency, 
      node.load
    ]);
    
    const csvContent = [
      headers.join(","),
      ...rows.map(r => r.map(cell => `"${cell}"`).join(","))
    ].join("\n");
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "telemetry_stats.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2>Dashboard Overview</h2>
          <p className="text-secondary">Real-time telemetry and infrastructure metrics</p>
        </div>
        <button 
          onClick={handleExportCSV}
          className="btn" 
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <Download size={16} /> Export to CSV
        </button>
      </div>

      <div className="grid grid-cols-3 mb-4">
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <Activity size={18} /> Requests / min
          </div>
          <div className="text-2xl">4,289</div>
          <div className="text-sm text-success mt-4">↑ 12% from last hour</div>
        </div>

        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <Zap size={18} /> Compression Savings
          </div>
          <div className="text-2xl">68.4%</div>
          <div className="text-sm text-success mt-4">AST + Semantic Caching active</div>
        </div>

        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <Cpu size={18} /> Budget Burn Rate
          </div>
          <div className="text-2xl">$14.20 / hr</div>
          <div className="text-sm text-secondary mt-4">Safe zone (CRITICAL threshold: $50)</div>
        </div>
      </div>

      <div className="glass-panel">
        <h3 style={{ marginBottom: '16px', color: '#fff' }}>Active Traffic Nodes</h3>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Upstream Provider</th>
                <th>Status</th>
                <th>Latency (p99)</th>
                <th>Load</th>
              </tr>
            </thead>
            <tbody>
              {telemetryData.map((node, index) => (
                <tr key={index}>
                  <td>{node.provider}</td>
                  <td>
                    <span className={`badge ${node.status === 'Healthy' ? 'badge-success' : 'badge-danger'}`}>
                      {node.status}
                    </span>
                  </td>
                  <td>{node.latency}</td>
                  <td>{node.load}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
