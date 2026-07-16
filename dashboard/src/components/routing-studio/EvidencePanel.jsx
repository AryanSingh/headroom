import { BarChart3 } from "lucide-react";

function percent(value) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export default function EvidencePanel({ contract, evidence }) {
  if (!contract || !evidence) {
    return (
      <div className="routing-empty-state">
        <BarChart3 size={22} />
        <strong>Evidence is collecting</strong>
        <span>Select a persisted contract version to inspect its rollout signals.</span>
      </div>
    );
  }
  const metrics = [
    ["Quality-safe savings", `$${evidence.quality_safe_savings_usd.toFixed(2)}`],
    ["Raw routed savings", `$${evidence.raw_routed_savings_usd.toFixed(2)}`],
    ["Evidence coverage", percent(evidence.coverage)],
    ["Mean quality", percent(evidence.mean_quality)],
    ["Unsafe rate", percent(evidence.unsafe_rate)],
    ["Acceptance rate", percent(evidence.acceptance_rate)],
    ["Fallback rate", percent(evidence.fallback_rate)],
  ];
  return (
    <div className="evidence-panel">
      <div className="routing-subhead">
        <div>
          <span className="eyebrow">Decision outcomes</span>
          <h3>Quality and reliability are separate signals</h3>
          <p>
            Savings count as quality-safe only when that decision segment met the
            contract quality floor.
          </p>
        </div>
        <span className={`status-pill ${evidence.status === "ready" ? "success" : "warning"}`}>
          {evidence.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="evidence-metric-grid">
        {metrics.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="rollout-gate-card">
        <div>
          <span>Observed samples</span>
          <strong>{evidence.samples} / {evidence.minimum_samples}</strong>
        </div>
        <div>
          <span>Quality floor</span>
          <strong>{percent(evidence.quality_floor)}</strong>
        </div>
        <div>
          <span>Maximum unsafe rate</span>
          <strong>{percent(evidence.maximum_unsafe_rate)}</strong>
        </div>
      </div>
    </div>
  );
}
