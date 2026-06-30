import { useDashboardData } from '../lib/use-dashboard-data';
import { Network, ArrowDownCircle, CheckCircle2 } from 'lucide-react';
import { formatCurrency, formatNumber } from '../lib/format';

export default function Orchestrator() {
  const { stats, loading, error } = useDashboardData();

  if (loading) {
    return <div className="page-shell">Loading...</div>;
  }
  if (error) {
    return <div className="page-shell error">Error loading orchestrator stats: {error}</div>;
  }

  const usdSaved = stats?.savings_by_source?.usd?.model_routing || 0;
  const tokensSaved = stats?.savings_by_source?.tokens?.model_routing || 0;
  
  return (
    <div className="page-shell">
      <header className="page-header">
        <div className="header-icon-container">
          <Network size={24} />
        </div>
        <div className="header-text">
          <h1>Orchestrator Insights</h1>
          <p>Smart model routing based on task complexity.</p>
        </div>
      </header>

      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <h3>Routed USD Savings</h3>
            <ArrowDownCircle className="stat-icon savings" />
          </div>
          <div className="stat-card-value savings">
            {formatCurrency(usdSaved)}
          </div>
          <div className="stat-card-subtitle">
            Delta vs requested models
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <h3>Routed Token Savings</h3>
            <CheckCircle2 className="stat-icon" />
          </div>
          <div className="stat-card-value">
            {formatNumber(tokensSaved)}
          </div>
          <div className="stat-card-subtitle">
            Offloaded to local/cheaper models
          </div>
        </div>
      </section>
      
      <section className="card">
        <h3>How it works</h3>
        <p style={{ marginTop: '1rem', lineHeight: '1.5' }}>
          The Smart Coding Model Orchestrator intercepts requests from your AI coding agents. 
          If it detects a simple task (e.g. fixing typos, adding docstrings) using heuristic classification, 
          it seamlessly down-routes the request to a cheaper, faster model (like Llama 3 8B or Haiku), 
          preserving your expensive cloud model tokens for heavy architectural work.
        </p>
      </section>
    </div>
  );
}
