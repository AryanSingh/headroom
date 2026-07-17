export default function SafeSavingsPanel({
  status,
  loading,
  error,
  disabling,
  disableError,
  onDisable,
}) {
  if (loading) {
    return <section className="panel safe-savings-panel">Loading Safe Savings…</section>;
  }
  if (error) {
    return null;
  }
  if (!status?.experience_enabled) {
    return null;
  }

  const decision = status.decision;
  return (
    <section className="panel safe-savings-panel" aria-labelledby="safe-savings-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Safe Savings</span>
          <h2 id="safe-savings-title">Conservative model routing</h2>
          <p>Exact routes with capability and transport protection.</p>
        </div>
        <strong>{status.mode === "off" ? "Off" : status.mode}</strong>
      </div>
      {status.mode === "off" ? (
        <p>Requests retain the originally requested model.</p>
      ) : (
        <>
          <p>Preset: {status.preset || "Custom"}</p>
          <div className="safe-savings-routes">
            {status.routes.map((route) => (
              <div key={`${route.source_model}:${route.low_target_model}`}>
                <strong>{route.source_model} → {route.low_target_model}</strong>
                <span>
                  {route.low_target_transport_safe ? "Transport-safe target" : "Restricted transport"}
                </span>
              </div>
            ))}
          </div>
          {decision ? (
            <div className="safe-savings-decision">
              <strong>{decision.title}</strong>
              <span>
                {decision.requested_model} → {decision.effective_model}
              </span>
              <p>{decision.explanation}</p>
              {decision.confidence != null ? (
                <span>Confidence {Number(decision.confidence).toFixed(2)}</span>
              ) : null}
              {decision.missing_capabilities?.length ? (
                <span>Missing capabilities: {decision.missing_capabilities.join(", ")}</span>
              ) : null}
            </div>
          ) : <p>No recent routing decision.</p>}
          <button type="button" onClick={onDisable} disabled={disabling}>
            {disabling ? "Turning off…" : "Turn Safe Savings off"}
          </button>
          {disableError ? <div role="alert">{disableError}</div> : null}
        </>
      )}
    </section>
  );
}
