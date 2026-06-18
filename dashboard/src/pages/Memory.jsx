import { BrainCircuit, FileText } from 'lucide-react';

export default function Memory() {
  return (
    <div>
      <div className="page-header">
        <h2>Memory & Learn</h2>
        <p className="text-secondary">Cross-session agent institutional memory and semantic corrections</p>
      </div>

      <div className="grid grid-cols-3 mb-4">
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <BrainCircuit size={18} /> Extracted Insights
          </div>
          <div className="text-2xl">4,192</div>
          <div className="text-sm mt-4 text-secondary">Total semantic facts</div>
        </div>
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <FileText size={18} /> Active Corrections
          </div>
          <div className="text-2xl">12</div>
          <div className="text-sm text-success mt-4">Injected via CLAUDE.md</div>
        </div>
      </div>

      <div className="glass-panel">
        <div className="flex justify-between items-center mb-4">
          <h3 style={{ color: '#fff' }}>Recent Learned Corrections</h3>
          <button className="btn">Run Manual Extraction</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Pattern Identified</th>
              <th>Target File</th>
              <th>Confidence</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Use `uv run python` instead of `python`</td>
              <td>CLAUDE.md</td>
              <td>98%</td>
              <td><span className="badge badge-success">Active</span></td>
            </tr>
            <tr>
              <td>Wait for db container before running migrations</td>
              <td>AGENTS.md</td>
              <td>91%</td>
              <td><span className="badge badge-success">Active</span></td>
            </tr>
            <tr>
              <td>Avoid importing `app.models` directly</td>
              <td>CLAUDE.md</td>
              <td>85%</td>
              <td><span className="badge badge-success">Active</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
