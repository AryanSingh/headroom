import { useEffect, useState } from "react";
import { ArrowDownCircle, CheckCircle2, Network, X } from "lucide-react";
import { formatCurrency, formatInteger } from "../lib/format";
import {
  patchDashboardConfig,
  useDashboardData,
} from "../lib/use-dashboard-data";

function ToggleSwitch({ checked, onChange, disabled, label }) {
  return (
    <label
      className="toggle-switch"
      style={{
        position: "relative",
        display: "inline-block",
        width: "36px",
        height: "20px",
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
disabled={disabled}
aria-label={label}
style={{ opacity: 0, width: 0, height: 0 }}
      />
      <span
        style={{
          position: "absolute",
          cursor: "pointer",
          inset: 0,
          backgroundColor: checked ? "var(--accent)" : "var(--surface-3)",
          transition: ".2s",
          borderRadius: "20px",
        }}
      >
        <span
          style={{
            position: "absolute",
            height: "14px",
            width: "14px",
            left: "3px",
            bottom: "3px",
            backgroundColor: "white",
            transition: ".2s",
            borderRadius: "50%",
            transform: checked ? "translateX(16px)" : "translateX(0)",
          }}
        />
      </span>
    </label>
  );
}

export default function Orchestrator() {
  const { stats, loading, error, configFlagsError, refresh } =
    useDashboardData();
  const [updating, setUpdating] = useState(false);
  const [optimisticState, setOptimisticState] = useState(null);
  const [toggleError, setToggleError] = useState(null);
  const [stalled, setStalled] = useState(false);

  const handleRetry = () => {
    setStalled(false);
    refresh?.();
  };

  // Show a "still waiting" message after 8s of loading
  useEffect(() => {
    if (loading) {
      const timer = setTimeout(() => setStalled(true), 8000);
      return () => clearTimeout(timer);
    }
  }, [loading]);

  if (loading) {
    return (
      <div className="page-shell">
        <div className="loading-message">
          {stalled ? (
            <>
              <p><strong>Still loading orchestrator data...</strong></p>
              <p className="text-secondary">The stats endpoint may be slow or unreachable. Check that the proxy is running and accepting requests.</p>
              <button className="ghost-button" onClick={handleRetry} style={{ marginTop: '12px' }} type="button">Retry</button>
            </>
          ) : (
            <p>Loading orchestrator data...</p>
          )}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-shell error">
        <div className="error-message">
          <p><strong>Could not load orchestrator data</strong></p>
          <p className="text-secondary">{error}</p>
          <button className="ghost-button" onClick={() => refresh?.()} style={{ marginTop: '12px' }}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const modelRouting = stats?.model_routing || {};
  const backendState =
    modelRouting.requested ?? stats?.config?.orchestrator ?? false;
  const isActive = optimisticState ?? backendState;
  const usdSaved = Number(
    stats?.cost?.savings_by_source?.usd?.model_routing || 0,
  );
  const tokensSaved = Number(
    stats?.cost?.savings_by_source?.tokens?.model_routing || 0,
  );
  const canToggle = !configFlagsError;

  const handleToggle = async (event) => {
    const newValue = event.target.checked;
    setOptimisticState(newValue);
    setToggleError(null);
    setUpdating(true);

    try {
      await patchDashboardConfig({ orchestrator: newValue });
      await refresh?.();
    } catch (err) {
      console.error("Failed update orchestrator config", err);
      setToggleError(err?.message || "Failed to update setting");
      setOptimisticState(null);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="page-stack">
      {toggleError ? (
        <div className="alert-card" role="alert">
          <span>Failed update orchestrator setting: {toggleError}</span>
          <button
            className="ghost-button"
            style={{ marginLeft: "auto" }}
            onClick={() => setToggleError(null)}
            type="button"
          >
            <X size={14} /> Dismiss
          </button>
        </div>
      ) : null}

      {modelRouting.reason ? (
        <div className="alert-card" role="status">
          Model routing is currently unavailable: {modelRouting.reason}.{" "}
          {modelRouting.install_hint}
        </div>
      ) : null}

      {configFlagsError ? (
        <div className="alert-card" role="status">
          Runtime config API unavailable in proxy: {configFlagsError}. Toggles
          may require a newer backend build.
        </div>
      ) : null}

      <section className="panel">
        <div className="section-heading">
          <div className="heading-with-icon">
            <div className="heading-icon">
              <Network size={18} />
            </div>
            <div>
              <div className="eyebrow">Orchestrator</div>
              <h2>Orchestrator Insights</h2>
              <p>Smart model routing based on task complexity.</p>
            </div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              background: "var(--surface-2)",
              padding: "0.5rem 1rem",
              borderRadius: "8px",
            }}
          >
            <span
              style={{
                fontSize: "0.85rem",
                fontWeight: 500,
                color: isActive
                  ? "var(--text-primary)"
                  : "var(--text-secondary)",
              }}
            >
              {isActive ? "Routing enabled" : "Routing disabled"}
            </span>
            <ToggleSwitch
              checked={Boolean(isActive)}
              onChange={handleToggle}
              disabled={updating || !canToggle}
              label={`${isActive ? "Disable" : "Enable"} orchestrator routing`}
            />
          </div>
        </div>

        <section className="metric-grid metric-grid-two">
          <article className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Routed USD savings</span>
              <div className="metric-icon amber">
                <ArrowDownCircle size={16} />
              </div>
            </div>
            <div className="metric-value">{formatCurrency(usdSaved)}</div>
            <div className="metric-footnote">Delta vs requested models</div>
          </article>

          <article className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Routed token savings</span>
              <div className="metric-icon green">
                <CheckCircle2 size={16} />
              </div>
            </div>
            <div className="metric-value">{formatInteger(tokensSaved)}</div>
            <div className="metric-footnote">
              Offloaded to cheaper local models
            </div>
          </article>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Routing status</div>
              <h2>Why it is not routing yet</h2>
            </div>
          </div>

          <div className="graphify-kv-grid">
            <div className="graphify-kv">
              <span>Configured</span>
              <strong>{modelRouting.requested ? "Yes" : "No"}</strong>
            </div>
            <div className="graphify-kv">
              <span>Router available</span>
              <strong>{modelRouting.available ? "Yes" : "No"}</strong>
            </div>
            <div className="graphify-kv">
              <span>Configured routes</span>
              <strong>
                {formatInteger(modelRouting.configured_routes || 0)}
              </strong>
            </div>
            <div className="graphify-kv">
              <span>Reason</span>
              <strong>{modelRouting.reason || "Ready"}</strong>
            </div>
          </div>
        </section>
      </section>
    </div>
  );
}
