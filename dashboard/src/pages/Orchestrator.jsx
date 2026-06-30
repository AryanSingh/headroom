import { useDashboardData, patchDashboardConfig } from '../lib/use-dashboard-data';
import { useState } from 'react';
import { Network, ArrowDownCircle, CheckCircle2 } from 'lucide-react';
import { formatCurrency, formatNumber } from '../lib/format';

function ToggleSwitch({ checked, onChange, disabled }) {
  return (
    <label className="toggle-switch" style={{
      position: 'relative', display: 'inline-block', width: '36px', height: '20px', opacity: disabled ? 0.5 : 1, cursor: disabled ? 'not-allowed' : 'pointer'
    }}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} style={{ opacity: 0, width: 0, height: 0 }} />
      <span style={{
        position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: checked ? 'var(--accent)' : 'var(--surface-3)', transition: '.2s', borderRadius: '20px'
      }}>
        <span style={{
          position: 'absolute', content: '""', height: '14px', width: '14px', left: '3px', bottom: '3px',
          backgroundColor: 'white', transition: '.2s', borderRadius: '50%',
          transform: checked ? 'translateX(16px)' : 'translateX(0)'
        }} />
      </span>
    </label>
  );
}

export default function Orchestrator() {
  const { stats, loading, error, mutate } = useDashboardData();
  const [updating, setUpdating] = useState(false);
  const [optimisticState, setOptimisticState] = useState(null);

  if (loading) {
    return <div className="page-shell">Loading...</div>;
  }
  if (error) {
    return <div className="page-shell error">Error loading orchestrator stats: {error}</div>;
  }

  const usdSaved = stats?.savings_by_source?.usd?.model_routing || 0;
  const tokensSaved = stats?.savings_by_source?.tokens?.model_routing || 0;
  
  const isActive = optimisticState !== null ? optimisticState : (stats?.config?.orchestrator ?? false);

  const handleToggle = async (e) => {
    const newValue = e.target.checked;
    setOptimisticState(newValue);
    setUpdating(true);
    try {
      await patchDashboardConfig({ orchestrator: newValue });
      await mutate();
    } catch (err) {
      console.error('Failed to update orchestrator config', err);
      alert('Failed to update setting');
      setOptimisticState(null); // Revert on failure
    } finally {
      setUpdating(false);
    }
  };
  
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="header-icon-container">
          <Network size={24} />
        </div>
        <div className="header-text" style={{ flex: 1 }}>
          <h1>Orchestrator Insights</h1>
          <p>Smart model routing based on task complexity.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--surface-2)', padding: '0.5rem 1rem', borderRadius: '8px' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 500, color: isActive ? 'var(--text-1)' : 'var(--text-2)' }}>
            {isActive ? 'Routing Enabled' : 'Routing Disabled'}
          </span>
          <ToggleSwitch checked={isActive} onChange={handleToggle} disabled={updating} />
        </div>
      </header>

      <section className="metric-grid metric-grid-two">
        <article className="metric-card">
          <div className="metric-card-header">
            <h3>Routed USD Savings</h3>
            <ArrowDownCircle className="stat-icon savings" />
          </div>
          <div className="metric-card-value savings">
            {formatCurrency(usdSaved)}
          </div>
          <div className="metric-card-subtitle">
            Delta vs requested models
          </div>
        </article>

        <article className="metric-card">
          <div className="metric-card-header">
            <h3>Routed Token Savings</h3>
            <CheckCircle2 className="stat-icon" />
          </div>
          <div className="metric-card-value">
            {formatNumber(tokensSaved)}
          </div>
          <div className="metric-card-subtitle">
            Offloaded to local/cheaper models
          </div>
        </article>
      </section>
      
      <section className="panel">
        <div className="section-heading">
          <h2>How it works</h2>
        </div>
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
