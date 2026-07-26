import { ArrowRight, CheckCircle2, ShieldAlert } from "lucide-react";

export default function DecisionPipeline({ receipt }) {
  if (!receipt) {
    return null;
  }
  const rejected = receipt.rejected_candidates || [];
  return (
    <div className="decision-pipeline" aria-label="Draft decision pipeline">
      <div>
        <span>Contract</span>
        <strong>
          {receipt.contract_id}@{receipt.contract_version}
        </strong>
      </div>
      <ArrowRight size={16} aria-hidden="true" />
      <div>
        <span>Eligible set</span>
        <strong>{receipt.eligible_candidates?.length || 1} deployment</strong>
      </div>
      <ArrowRight size={16} aria-hidden="true" />
      <div className="selected">
        <CheckCircle2 size={15} aria-hidden="true" />
        <span>Selected</span>
        <strong>{receipt.selected_deployment}</strong>
      </div>
      {rejected.length ? (
        <div className="pipeline-rejections">
          <ShieldAlert size={15} aria-hidden="true" />
          <span>{rejected.length} rejected</span>
        </div>
      ) : null}
    </div>
  );
}
