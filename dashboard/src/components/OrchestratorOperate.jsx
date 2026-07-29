import { ArrowRight, CircleAlert, Gauge, ShieldCheck } from "lucide-react";

export function getOrchestratorRecommendation({
  configAvailable,
  roleCount,
  mode,
  evidenceStatus,
  providers,
}) {
  if (!configAvailable) {
    return { icon: CircleAlert, label: "Update the proxy", detail: "Runtime controls need a compatible proxy build.", target: null };
  }
  if (providers.some((provider) => provider.healthy === false)) {
    return { icon: CircleAlert, label: "Check provider health", detail: "A configured compatibility provider is disabled.", target: "configuration" };
  }
  if (mode === "off" && roleCount === 0) {
    return { icon: Gauge, label: "Set up role assignments", detail: "Lock important workloads to approved models before enabling routing.", target: "configuration" };
  }
  if (evidenceStatus === "ready") {
    return { icon: ShieldCheck, label: "Review rollout gates", detail: "Measured evidence is ready for a contract rollout decision.", target: "contracts" };
  }
  if (evidenceStatus === "collecting") {
    return { icon: Gauge, label: "Continue collecting evidence", detail: "Shadow samples are still building the quality-safe routing frontier.", target: null };
  }
  if (mode === "off") {
    return { icon: Gauge, label: "Start with Auto routing", detail: "Auto keeps uncertain work on the requested model.", target: null };
  }
  return { icon: ShieldCheck, label: "Routing is operational", detail: "Current routing and safety signals do not require action.", target: null };
}

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
