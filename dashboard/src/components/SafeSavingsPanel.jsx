import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";

import {
  fetchDashboardJson,
  isUnsupportedDashboardEndpointError,
} from "../lib/use-dashboard-data";

function decisionLabel(decision) {
  if (!decision?.state) {
    return "No recent routing decision";
  }
  return decision.state.charAt(0).toUpperCase() + decision.state.slice(1);
}

export default function SafeSavingsPanel() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;

    fetchDashboardJson("/v1/orchestration/safe-savings/status")
      .then((data) => {
        if (!active) {
          return;
        }
        setStatus(data);
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setStatus(null);
        setError(isUnsupportedDashboardEndpointError(err) ? null : err?.message || "Unable to load Safe Savings status");
      });

    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <div className="alert-card" role="status">
        Safe Savings status unavailable: {error}
      </div>
    );
  }

  if (!status?.experience_enabled) {
    return null;
  }

  const decision = status.decision;
  const requiredCapabilities = decision?.required_capabilities || [];
  const missingCapabilities = decision?.missing_capabilities || [];

  return (
    <section className="panel" aria-labelledby="safe-savings-heading">
      <div className="section-heading">
        <div className="heading-with-icon">
          <div className="heading-icon">
            <ShieldCheck size={18} />
          </div>
          <div>
            <div className="eyebrow">Opt-in guidance</div>
            <h2 id="safe-savings-heading">Guided Safe Savings</h2>
            <p>Explains the active router without changing your provider, account, or model selection.</p>
          </div>
        </div>
        <span className="status-pill">{status.enabled ? "Active" : "Off"}</span>
      </div>

      <div className="metric-grid metric-grid-three">
        <article className="metric-card metric-card-compact">
          <div className="metric-label">Routing mode</div>
          <div className="metric-value">{status.mode || "off"}</div>
          <div className="metric-footnote">{status.preset || "No preset selected"}</div>
        </article>
        <article className="metric-card metric-card-compact">
          <div className="metric-label">Configured routes</div>
          <div className="metric-value">{status.route_count || 0}</div>
          <div className="metric-footnote">{status.transport_safe_targets || 0} transport-safe targets</div>
        </article>
        <article className="metric-card metric-card-compact">
          <div className="metric-label">Latest decision</div>
          <div className="metric-value">{decisionLabel(decision)}</div>
          <div className="metric-footnote">{status.rollback_available ? "Off is available in routing mode control" : "No routing change is available"}</div>
        </article>
      </div>

      {decision ? (
        <div className="safe-savings-decision" role="status">
          <strong>{decision.reason_title || decisionLabel(decision)}</strong>
          {decision.reason_explanation ? <p>{decision.reason_explanation}</p> : null}
          {typeof decision.confidence === "number" ? <span>Confidence: {decision.confidence.toFixed(2)}</span> : null}
          {requiredCapabilities.length ? <span>Required: {requiredCapabilities.join(", ")}</span> : null}
          {missingCapabilities.length ? <span>Unavailable: {missingCapabilities.join(", ")}</span> : null}
        </div>
      ) : null}

      <p className="text-secondary" style={{ marginTop: "var(--space-md)" }}>
        No automatic provider switching. Capability, account, transport, and credential protections remain enforced.
      </p>
    </section>
  );
}
