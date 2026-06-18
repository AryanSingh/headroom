import { Activity, Zap, ShieldAlert, Cpu } from 'lucide-react';

export default function Overview() {
  return (
    <div>
      <div className="page-header">
        <h2>Dashboard Overview</h2>
        <p className="text-secondary">Real-time telemetry and infrastructure metrics</p>
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
            <tr>
              <td>Anthropic (Claude 3.5 Sonnet)</td>
              <td><span className="badge badge-success">Healthy</span></td>
              <td>241ms</td>
              <td>42%</td>
            </tr>
            <tr>
              <td>OpenAI (GPT-4o)</td>
              <td><span className="badge badge-success">Healthy</span></td>
              <td>310ms</td>
              <td>28%</td>
            </tr>
            <tr>
              <td>AWS Bedrock (Meta Llama 3)</td>
              <td><span className="badge badge-danger">Failing Over</span></td>
              <td>--</td>
              <td>0%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
