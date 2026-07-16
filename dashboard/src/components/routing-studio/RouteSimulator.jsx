import { FlaskConical } from "lucide-react";
import DecisionPipeline from "./DecisionPipeline";

export default function RouteSimulator({ draft, simulation, running, onRun }) {
  if (!draft)
    {return (
      <div className="routing-empty-state">
        <FlaskConical size={22} />
        <strong>Create a draft first</strong>
        <span>
          The simulator evaluates the visible draft without executing a provider
          call.
        </span>
      </div>
    );}
  const receipt = simulation?.draft_receipt;
  const worstCase =
    draft.reliability.attempt_timeout_seconds *
    draft.reliability.attempts_per_deployment *
    draft.reliability.maximum_deployments;
  return (
    <div className="route-simulator">
      <div className="routing-subhead">
        <div>
          <span className="eyebrow">No-call preview</span>
          <h3>Draft route simulator</h3>
          <p>
            Compare the live route with the exact unsaved policy visible in the
            editor.
          </p>
        </div>
        <button
          className="primary-button"
          type="button"
          onClick={onRun}
          disabled={running}
        >
          {running ? "Simulating…" : "Run draft simulation"}
        </button>
      </div>
      <div className="simulation-scenario">
        <span>Scenario</span>
        <strong>{draft.id}</strong>
        <span>Worst-case plan</span>
        <strong>
          {worstCase}s within {draft.reliability.total_deadline_seconds}s
          deadline
        </strong>
      </div>
      {receipt ? (
        <>
          <div className="simulation-result-header">
            <div>
              <span className="status-pill">
                Draft version {receipt.contract_version}
              </span>
              <h3>{receipt.selected_model}</h3>
              <p>{receipt.selected_deployment}</p>
            </div>
            <div
              className={
                simulation.changed ? "route-change changed" : "route-change"
              }
            >
              {simulation.changed ? "Route changes" : "Same route"}
            </div>
          </div>
          <DecisionPipeline receipt={receipt} />
          <div className="simulation-evidence-grid">
            <div>
              <span>Evidence source</span>
              <strong>
                {receipt.evidence?.source || "deterministic registry"}
              </strong>
            </div>
            <div>
              <span>Rejected candidates</span>
              <strong>{receipt.rejected_candidates?.length || 0}</strong>
            </div>
            <div>
              <span>Provider calls</span>
              <strong>0</strong>
            </div>
            <div>
              <span>Lifecycle</span>
              <strong>{receipt.contract_state || "draft"}</strong>
            </div>
          </div>
          {receipt.rejected_candidates?.length ? (
            <div className="routing-table-wrap">
              <table className="routing-table">
                <thead>
                  <tr>
                    <th>Rejected model</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {receipt.rejected_candidates.map((item) => (
                    <tr key={`${item.model}:${item.reason}`}>
                      <td>{item.model}</td>
                      <td>{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : (
        <div className="routing-empty-state">
          <FlaskConical size={22} />
          <strong>Ready to simulate</strong>
          <span>
            The preview will show selected deployment, rejected candidates,
            evidence, and deadline math.
          </span>
        </div>
      )}
    </div>
  );
}
