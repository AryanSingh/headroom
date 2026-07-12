import { useEffect, useState } from "react";
import { ArrowDownCircle, CheckCircle2, Network, X } from "lucide-react";

import { getAdminAuthHeaders } from "../lib/admin-auth";
import { getProxyUrl } from "../lib/api";
import { formatCurrency, formatInteger } from "../lib/format";
import {
  fetchDashboardJson,
  isUnsupportedDashboardEndpointError,
  patchDashboardConfig,
  useDashboardData,
} from "../lib/use-dashboard-data";
import OrchestrationStudio from "../components/OrchestrationStudio";

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

async function postProviderControl(providerName, action) {
  const response = await fetch(getProxyUrl(`/v1/providers/${providerName}/${action}`), {
    method: "POST",
    headers: getAdminAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Provider ${action} failed: ${response.status}`);
  }

  return response.json();
}

export default function Orchestrator() {
  const { stats, loading, error, configFlagsError, refresh } = useDashboardData();
  const [updating, setUpdating] = useState(false);
  const [optimisticState, setOptimisticState] = useState(null);
  const [toggleError, setToggleError] = useState(null);
  const [stalled, setStalled] = useState(false);
  const [policyStatus, setPolicyStatus] = useState(null);
  const [policyError, setPolicyError] = useState(null);
  const [policyLoading, setPolicyLoading] = useState(true);
  const [providerStatus, setProviderStatus] = useState([]);
  const [providerError, setProviderError] = useState(null);
  const [providerLoading, setProviderLoading] = useState(true);
  const [providerMutation, setProviderMutation] = useState({});

  useEffect(() => {
    if (!loading) {
      return undefined;
    }

    const timeout = window.setTimeout(() => setStalled(true), 1500);
    return () => {
      window.clearTimeout(timeout);
      setStalled(false);
    };
  }, [loading]);

  useEffect(() => {
    let active = true;

    async function loadPolicyStatus() {
      setPolicyLoading(true);
      try {
        const data = await fetchDashboardJson("/policy/status");
        if (!active) {
          return;
        }
        setPolicyStatus(data);
        setPolicyError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        setPolicyError(err?.message || "Unable to load policy status");
      } finally {
        if (active) {
          setPolicyLoading(false);
        }
      }
    }

    async function loadProviderStatus() {
      setProviderLoading(true);
      try {
        const data = await fetchDashboardJson("/v1/providers");
        if (!active) {
          return;
        }
        setProviderStatus(Array.isArray(data?.providers) ? data.providers : []);
        setProviderError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        if (isUnsupportedDashboardEndpointError(err)) {
          setProviderError("Provider failover API unavailable in this proxy build.");
        } else {
          setProviderError(err?.message || "Unable to load provider controls");
        }
      } finally {
        if (active) {
          setProviderLoading(false);
        }
      }
    }

    loadPolicyStatus();
    loadProviderStatus();

    return () => {
      active = false;
    };
  }, []);

  const handleRetry = () => {
    setStalled(false);
    refresh?.();
  };

  const handleToggle = async (event) => {
    const newValue = event.target.checked;
    setOptimisticState(newValue);
    setToggleError(null);
    setUpdating(true);
    try {
      await patchDashboardConfig({ orchestrator: newValue });
      await refresh?.();
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error("Failed update orchestrator config", err);
      }
      setToggleError(err?.message || "Failed to update setting");
      setOptimisticState(null);
    } finally {
      setUpdating(false);
    }
  };

  const handleProviderAction = async (providerName, action) => {
    setToggleError(null);
    setProviderMutation((current) => ({ ...current, [providerName]: true }));
    try {
      await postProviderControl(providerName, action);
      const next = await fetchDashboardJson("/v1/providers");
      setProviderStatus(Array.isArray(next?.providers) ? next.providers : []);
      setProviderError(null);
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error(`Failed to ${action} provider`, err);
      }
      setProviderError(err?.message || `Unable to ${action} provider`);
    } finally {
      setProviderMutation((current) => ({ ...current, [providerName]: false }));
    }
  };

  if (loading) {
    return (
      <div className="page-shell">
        <div className="panel">
          {stalled ? (
            <>
              <p>
                <strong>Still loading orchestrator data...</strong>
              </p>
              <p className="text-secondary">
                The stats endpoint may be slow or unreachable. Check that the proxy is
                running and accepting requests.
              </p>
              <button
                className="ghost-button"
                onClick={handleRetry}
                style={{ marginTop: "12px" }}
                type="button"
              >
                Retry
              </button>
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
          <p>
            <strong>Could not load orchestrator data</strong>
          </p>
          <p className="text-secondary">{error}</p>
          <button className="ghost-button" onClick={() => refresh?.()} style={{ marginTop: "12px" }}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const modelRouting = stats?.model_routing || {};
  const backendState = modelRouting.requested ?? stats?.config?.orchestrator ?? false;
  const isActive = optimisticState ?? backendState;
  const usdSaved = Math.max(
    Number(stats?.cost?.savings_by_source?.usd?.model_routing || 0),
    Number(stats?.savings_by_source?.usd?.model_routing || 0),
  );
  const tokensSaved = Math.max(
    Number(stats?.cost?.savings_by_source?.tokens?.model_routing || 0),
    Number(stats?.savings_by_source?.tokens?.model_routing || 0),
  );
  const canToggle = !configFlagsError;
  const providerDecisions = policyStatus?.provider_decisions || {};

  return (
    <div className="page-stack">
      {toggleError ? (
        <div className="alert-card" role="alert">
          <span>Failed to update orchestrator setting: {toggleError}</span>
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
          Model routing is currently unavailable: {modelRouting.reason}. {modelRouting.install_hint}
        </div>
      ) : null}

      {configFlagsError ? (
        <div className="alert-card" role="status">
          Runtime config API unavailable in proxy: {configFlagsError}. Toggles may require a newer
          backend build.
        </div>
      ) : null}

      <OrchestrationStudio />

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
                color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
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
            <div className="metric-footnote">Offloaded lower-cost route targets</div>
          </article>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Routing status</div>
              <h2>{modelRouting.reason ? "Why routing is blocked" : "Routing readiness"}</h2>
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
              <strong>{formatInteger(modelRouting.configured_routes || 0)}</strong>
            </div>
            <div className="graphify-kv">
              <span>Reason</span>
              <strong>{modelRouting.reason || "Ready"}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Provider policy</div>
              <h2>Fallback and selection posture</h2>
              <p>
                Provider-aware policy decisions shape cache preservation, semantic cache use,
                and how aggressively the proxy compresses before a request ever needs fallback
                handling.
              </p>
            </div>
          </div>

          {policyError ? (
            <div className="alert-card" role="status">
              Policy status unavailable: {policyError}
            </div>
          ) : null}

          {policyLoading ? (
            <div className="metric-grid metric-grid-three">
              <article className="metric-card metric-card-compact">
                <div className="metric-label">Policy status</div>
                <div className="metric-value">Loading</div>
              </article>
            </div>
          ) : null}

          {!policyLoading && !policyError ? (
            <>
              <div className="graphify-kv-grid" style={{ marginBottom: "var(--space-lg)" }}>
                <div className="graphify-kv">
                  <span>Workload class</span>
                  <strong>{policyStatus?.workload_class || "unknown"}</strong>
                </div>
                <div className="graphify-kv">
                  <span>Resolver</span>
                  <strong>{policyStatus?.resolver_disabled ? "Disabled" : "Active"}</strong>
                </div>
              </div>
              <div className="metric-grid metric-grid-three">
                {Object.entries(providerDecisions).map(([provider, decision]) => (
                  <article key={provider} className="metric-card metric-card-compact">
                    <div className="metric-label">{provider}</div>
                    <div className="metric-value">{decision?.strategy_label || "default"}</div>
                    <div className="metric-footnote">
                      Prefix cache: {decision?.preserve_prefix_for_provider_cache ? "preserve" : "compress"}
                    </div>
                    <div className="metric-footnote">
                      Semantic cache: {decision?.semantic_cache_enabled ? "on" : "off"}
                    </div>
                    <div className="metric-footnote">
                      Tool-only compression: {decision?.compress_tool_outputs_only ? "yes" : "no"}
                    </div>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Failover controls</div>
              <h2>Compatibility-provider health and overrides</h2>
              <p>
                These controls affect the legacy compatibility retry path. Role-locked
                orchestration accounts are managed in the Providers tab above and are never
                silently redirected by this panel.
              </p>
            </div>
          </div>

          {providerError ? (
            <div className="alert-card" role="status">
              {providerError}
            </div>
          ) : null}

          {providerLoading ? (
            <div className="metric-grid metric-grid-three">
              <article className="metric-card metric-card-compact">
                <div className="metric-label">Provider controls</div>
                <div className="metric-value">Loading</div>
              </article>
            </div>
          ) : null}

          {!providerLoading && !providerError ? (
            <div className="metric-grid metric-grid-three">
              {providerStatus.map((provider) => {
                const action = provider.healthy ? "disable" : "enable";
                const busy = Boolean(providerMutation[provider.name]);
                return (
                  <article key={provider.name} className="metric-card metric-card-compact">
                    <div className="metric-label">{provider.name}</div>
                    <div className="metric-value">{provider.healthy ? "Healthy" : "Disabled"}</div>
                    <div className="metric-footnote">Priority: {provider.priority ?? "n/a"}</div>
                    <div className="metric-footnote">Base URL: {provider.base_url || "unknown"}</div>
                    <button
                      className="ghost-button"
                      onClick={() => handleProviderAction(provider.name, action)}
                      disabled={busy}
                      type="button"
                      style={{ marginTop: "0.75rem", width: "fit-content" }}
                    >
                      {busy ? "Updating..." : action === "disable" ? "Disable provider" : "Enable provider"}
                    </button>
                  </article>
                );
              })}
            </div>
          ) : null}
        </section>
      </section>
    </div>
  );
}
