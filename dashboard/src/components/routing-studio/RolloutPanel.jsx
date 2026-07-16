import { Pause, RotateCcw, ShieldCheck } from "lucide-react";

const STAGES = ["draft", "shadow", "canary", "active"];

export default function RolloutPanel({ contract, evidence, busy, onAction }) {
  if (!contract) {
    return (
      <div className="routing-empty-state">
        <ShieldCheck size={22} />
        <strong>Select a contract</strong>
        <span>Rollout gates are evaluated per immutable version.</span>
      </div>
    );
  }
  const blocked = evidence?.status !== "ready";
  const isDraft = contract.state === "draft";
  const nextLabel = isDraft
    ? "Start shadow"
    : contract.state === "canary"
      ? "Promote to active"
      : "Promote to canary";
  const gateMessage =
    evidence?.status === "quality_blocked"
      ? "Quality floor not met"
      : evidence?.status === "ready"
        ? "Evidence gate passed"
        : "More evidence required";
  return (
    <div className="rollout-panel">
      <div className="routing-subhead">
        <div>
          <span className="eyebrow">Version {contract.version}</span>
          <h3>Evidence-gated rollout</h3>
          <p>Shadow first, then a bounded canary, with an atomic rollback path.</p>
        </div>
        <span className={`status-pill ${blocked ? "warning" : "success"}`}>
          {gateMessage}
        </span>
      </div>
      <ol className="rollout-timeline" aria-label="Contract lifecycle">
        {STAGES.map((stage) => (
          <li key={stage} className={contract.state === stage ? "current" : ""}>
            <span>{stage}</span>
          </li>
        ))}
      </ol>
      <div className="rollout-gate-card">
        <div>
          <span>Canary cohort</span>
          <strong>{Math.round((contract.evaluation?.canary_percentage || 0) * 100)}%</strong>
        </div>
        <div>
          <span>Evidence coverage</span>
          <strong>{Math.round((evidence?.coverage || 0) * 100)}%</strong>
        </div>
        <div>
          <span>Gate</span>
          <strong>{gateMessage}</strong>
        </div>
      </div>
      <div className="rollout-actions">
        <button
          type="button"
          className="primary-button"
          disabled={
            busy ||
            (!isDraft && blocked) ||
            !["draft", "shadow", "canary"].includes(contract.state)
          }
          onClick={() => onAction(isDraft ? "shadow" : "promote")}
        >
          <ShieldCheck size={15} /> {nextLabel}
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={busy || !["shadow", "canary", "active"].includes(contract.state)}
          onClick={() => onAction("pause")}
        >
          <Pause size={15} /> Pause rollout
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={busy || contract.state !== "active"}
          onClick={() => onAction("rollback")}
        >
          <RotateCcw size={15} /> Roll back
        </button>
      </div>
    </div>
  );
}
