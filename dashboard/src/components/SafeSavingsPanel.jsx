import { ShieldCheck } from "lucide-react";

function decisionLabel(decision) {
  if (!decision) {
    return "No recent routing decision";
  }
  return decision.applied ? "Applied" : "Retained";
}

export default function SafeSavingsPanel({
  status,
  loading,
  error,
  disabling,
  disableError,
  onDisable,
}) {
  if (loading || error || !status?.experience_enabled) {
    return null;
  }

    const decision = status.decision;
    const routes = Array.isArray(status.routes) ? status.routes : [];
    const transportSafeTargets = Array.isArray(status.transport_safe_targets)
      ? status.transport_safe_targets
      : [];
    const signals = decision?.signals || [];
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
          <div className="metric-footnote">{transportSafeTargets.length} transport-safe targets</div>
        </article>
        <article className="metric-card metric-card-compact">
          <div className="metric-label">Latest decision</div>
          <div className="metric-value">{decisionLabel(decision)}</div>
          <div className="metric-footnote">{status.rollback_available ? "Off is available in routing mode control" : "No routing change is available"}</div>
        </article>
      </div>

      {!status.enabled ? (
        <p>Requests retain the originally requested model.</p>
      ) : null}

      {status.enabled && routes.length ? (
        <div className="safe-savings-routes" aria-label="Eligible exact routes">
          {routes.map((route) => (
            <div
              className="safe-savings-route"
              key={`${route.source_model}:${route.low_target_model}`}
            >
              <div>
                <strong>{route.source_model} → {route.low_target_model}</strong>
                <span>
                  {route.low_target_transport_safe
                    ? "Transport-safe target"
                    : "Restricted transport"}
                </span>
              </div>
              {route.medium_target_model ? (
                <div>
                  <strong>{route.source_model} → {route.medium_target_model}</strong>
                  <span>
                    {route.medium_target_transport_safe
                      ? "Transport-safe target"
                      : "Restricted transport"}
                  </span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {status.enabled && decision ? (
        <div className="safe-savings-decision" role="status">
          <strong>{decision.title || decisionLabel(decision)}</strong>
          <span>{decision.requested_model} → {decision.effective_model}</span>
          {decision.explanation ? <p>{decision.explanation}</p> : null}
          {typeof decision.confidence === "number" ? <span>Confidence {decision.confidence.toFixed(2)}</span> : null}
          {signals.length ? <span>Signals: {signals.join(", ")}</span> : null}
          {requiredCapabilities.length ? <span>Required: {requiredCapabilities.join(", ")}</span> : null}
          {missingCapabilities.length ? <span>Unavailable: {missingCapabilities.join(", ")}</span> : null}
        </div>
      ) : null}

      {status.enabled && status.rollback_available ? (
        <button
          className="ghost-button"
          type="button"
          onClick={onDisable}
          disabled={disabling}
        >
          {disabling ? "Turning Safe Savings off…" : "Turn Safe Savings off"}
        </button>
      ) : null}

      {disableError ? (
        <div className="alert-card" role="alert">
          {disableError}
        </div>
      ) : null}

      <p className="text-secondary" style={{ marginTop: "var(--space-md)" }}>
        No automatic provider switching. Capability, account, transport, and credential protections remain enforced.
      </p>
    </section>
  );
}
