import { ArrowRight, Gauge } from "lucide-react";

export default function OrchestratorOperate({ recommendation, onNavigate }) {
  const Icon = recommendation.icon;
  return (
    <section className="panel orchestrator-command-panel">
      <div className="orchestrator-command-copy">
        <div className="heading-icon"><Gauge aria-hidden="true" size={18} /></div>
        <div>
          <div className="eyebrow">Operate</div>
          <h2>Route requests</h2>
          <p>Choose the live routing posture, then follow the next action supported by current evidence.</p>
        </div>
      </div>
      <div className="orchestrator-recommendation" role="status">
        <Icon aria-hidden="true" size={18} />
        <div>
          <strong>{recommendation.label}</strong>
          <span>{recommendation.detail}</span>
        </div>
        {recommendation.target ? (
          <button className="ghost-button" onClick={() => onNavigate(recommendation.target)} type="button">
            Open <ArrowRight aria-hidden="true" size={14} />
          </button>
        ) : null}
      </div>
    </section>
  );
}
