import { Shield, ShieldAlert, CheckCircle } from 'lucide-react';

export default function Firewall() {
  return (
    <div>
      <div className="page-header">
        <h2>Firewall & Security</h2>
        <p className="text-secondary">Manage LLM injection rules and PII redaction</p>
      </div>

      <div className="grid grid-cols-3 mb-4">
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <Shield size={18} /> Active Patterns
          </div>
          <div className="text-2xl">27</div>
          <div className="text-sm mt-4 text-secondary">Signatures loaded</div>
        </div>
        <div className="glass-panel">
          <div className="flex items-center gap-2 text-secondary">
            <ShieldAlert size={18} /> Blocks Today
          </div>
          <div className="text-2xl">143</div>
          <div className="text-sm text-danger mt-4">↑ 41 from yesterday</div>
        </div>
      </div>

      <div className="glass-panel">
        <div className="flex justify-between items-center mb-4">
          <h3 style={{ color: '#fff' }}>Recent Interceptions</h3>
          <button className="btn btn-primary">Add Custom Rule</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Rule Triggered</th>
              <th>Action</th>
              <th>Project</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>10:41 AM</td>
              <td>JAILBREAK_IGNORE_PREVIOUS</td>
              <td><span className="badge badge-danger">Blocked</span></td>
              <td>prod-api-svc</td>
            </tr>
            <tr>
              <td>10:12 AM</td>
              <td>PII_CREDIT_CARD</td>
              <td><span className="badge badge-success">Redacted</span></td>
              <td>customer-portal</td>
            </tr>
            <tr>
              <td>09:05 AM</td>
              <td>EXFILTRATION_BASE64</td>
              <td><span className="badge badge-danger">Blocked</span></td>
              <td>internal-tools</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
