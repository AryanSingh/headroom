import { useEffect, useMemo, useState } from "react";
import { ArrowDownCircle, CheckCircle2, Network, X } from "lucide-react";

import { getAdminAuthHeaders } from "../lib/admin-auth";
import { getProxyUrl } from "../lib/api";
import { formatCurrency, formatInteger, formatPercent } from "../lib/format";
import {
  fetchDashboardJson,
  isUnsupportedDashboardEndpointError,
  patchDashboardConfig,
  useDashboardData,
} from "../lib/use-dashboard-data";
import OrchestrationStudio from "../components/OrchestrationStudio";
import RoutingStudio from "../components/routing-studio/RoutingStudio";
import SafeSavingsPanel from "../components/SafeSavingsPanel";

const ROUTING_MODES = [
  { value: "off", label: "Off", description: "Disable model routing" },
  { value: "balanced", label: "Balanced", description: "Use codex-gpt54mini-high" },
  { value: "aggressive", label: "Aggressive", description: "Use economy" },
];

function RoutingModeSelector({ value, onChange, disabled }) {
  return (
    <div className="tab-group" aria-label="Routing mode selector">
      {ROUTING_MODES.map((mode) => {
        const active = value === mode.value;
        return (
          <button
            key={mode.value}
            className={`tab-button ${active ? "active" : ""}`}
            onClick={() => onChange(mode.value)}
            disabled={disabled}
            type="button"
            title={mode.description}
            aria-pressed={active}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
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

function matchesSearch(query, ...values) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return values
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .some((value) => String(value || "").toLowerCase().includes(normalized));
}

function acknowledgedRoutingMode(response) {
  return response?.applied_live?.orchestrator_mode?.mode;
}

export default function Orchestrator({ searchQuery = "" }) {
  const {
    stats,
    health,
    loading,
    error,
    configFlagsError,
    committedGeneration,
    lastUpdated,
    refreshError,
    refreshing,
    refresh,
  } = useDashboardData();
  const [updating, setUpdating] = useState(false);
  const [optimisticMode, setOptimisticMode] = useState(null);
  const [toggleError, setToggleError] = useState(null);
  const [modeConfirmationWarning, setModeConfirmationWarning] = useState(null);
  const [stalled, setStalled] = useState(false);
  const [policyStatus, setPolicyStatus] = useState(null);
  const [policyError, setPolicyError] = useState(null);
  const [policyLoading, setPolicyLoading] = useState(true);
  const [routingEvidence, setRoutingEvidence] = useState(null);
  const [routingEvidenceError, setRoutingEvidenceError] = useState(null);
  const [routingEvidenceLoading, setRoutingEvidenceLoading] = useState(true);
  const [providerStatus, setProviderStatus] = useState([]);
  const [providerError, setProviderError] = useState(null);
  const [providerLoading, setProviderLoading] = useState(true);
  const [providerMutation, setProviderMutation] = useState({});
  const [safeSavingsStatus, setSafeSavingsStatus] = useState(null);
  const [safeSavingsLoading, setSafeSavingsLoading] = useState(true);
  const [safeSavingsError, setSafeSavingsError] = useState(null);
  const [safeSavingsDisabling, setSafeSavingsDisabling] = useState(false);
  const [safeSavingsDisableError, setSafeSavingsDisableError] = useState(null);

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

    async function loadRoutingEvidence() {
      setRoutingEvidenceLoading(true);
      try {
        const data = await fetchDashboardJson("/v1/orchestration/routing/evidence");
        if (!active) {
          return;
        }
        setRoutingEvidence(data);
        setRoutingEvidenceError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        setRoutingEvidence(null);
        setRoutingEvidenceError(err?.message || "Unable to load routing evidence");
      } finally {
        if (active) {
          setRoutingEvidenceLoading(false);
        }
      }
    }

    async function loadSafeSavingsStatus() {
      setSafeSavingsLoading(true);
      try {
        const data = await fetchDashboardJson("/v1/orchestration/safe-savings/status");
        if (!active) {
          return;
        }
        setSafeSavingsStatus(data);
        setSafeSavingsError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        setSafeSavingsStatus(null);
        setSafeSavingsError(err?.message || "Unable to load Safe Savings status");
      } finally {
        if (active) {
          setSafeSavingsLoading(false);
        }
      }
    }

    loadPolicyStatus();
    loadProviderStatus();
    loadRoutingEvidence();
    loadSafeSavingsStatus();

    return () => {
      active = false;
    };
  }, []);

  const handleRetry = () => {
    setStalled(false);
    refresh?.();
  };

  const handleModeChange = async (mode) => {
    setOptimisticMode({ mode, generation: committedGeneration });
    setToggleError(null);
    setModeConfirmationWarning(null);
    setUpdating(true);
    let acknowledged = false;
    try {
      const response = await patchDashboardConfig({ orchestrator_mode: mode });
      if (acknowledgedRoutingMode(response) !== mode) {
        throw new Error(`Server did not acknowledge routing mode ${mode}`);
      }
      acknowledged = true;
      const result = await refresh?.();
      const confirmedMode = result?.stats?.model_routing?.mode;
      if (!result?.ok || !result.committed) {
        setModeConfirmationWarning(
          `Routing mode update is pending confirmation${result?.error ? `: ${result.error}` : "."}`,
        );
      } else if (confirmedMode === mode) {
        setOptimisticMode(null);
      } else {
        setOptimisticMode({ mode, generation: result.generation });
        setModeConfirmationWarning("Routing mode update is pending confirmation from newer stats.");
      }
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error("Failed update orchestrator mode", err);
      }
      if (acknowledged) {
        setModeConfirmationWarning(
          `Routing mode update is pending confirmation: ${err?.message || "refresh failed"}`,
        );
      } else {
        setToggleError(err?.message || "Failed to update routing mode");
        setOptimisticMode(null);
      }
    } finally {
      setUpdating(false);
    }
  };

  const handleSafeSavingsDisable = async () => {
    if (!window.confirm("Turn Safe Savings off? New requests will retain the requested model.")) {
      return;
    }
    setSafeSavingsDisabling(true);
    setSafeSavingsDisableError(null);
    try {
      const response = await patchDashboardConfig({ orchestrator_mode: "off" });
      if (acknowledgedRoutingMode(response) !== "off") {
        throw new Error("Server did not acknowledge routing mode off");
      }
      const next = await fetchDashboardJson("/v1/orchestration/safe-savings/status");
      setSafeSavingsStatus(next);
      await refresh?.();
    } catch (err) {
      setSafeSavingsDisableError(err?.message || "Unable to turn Safe Savings off");
    } finally {
      setSafeSavingsDisabling(false);
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

  const modelRouting = stats?.model_routing || {};
  const backendMode = modelRouting.mode || (modelRouting.requested ? "balanced" : "off");
  const pendingMode = optimisticMode?.mode ?? null;
  const activeMode = pendingMode ?? backendMode;
  const currentPreset =
    modelRouting.preset ||
    (activeMode === "aggressive"
      ? "economy"
      : activeMode === "balanced"
        ? "codex-gpt54mini-high"
        : "none");
  const usdSaved = Math.max(
    Number(stats?.cost?.savings_by_source?.usd?.model_routing || 0),
    Number(stats?.savings_by_source?.usd?.model_routing || 0),
  );
  const tokensSaved = Math.max(
    Number(stats?.cost?.savings_by_source?.tokens?.model_routing || 0),
    Number(stats?.savings_by_source?.tokens?.model_routing || 0),
  );
  const normalizedQuery = String(searchQuery || "").trim().toLowerCase();
  const canToggle = !configFlagsError;
  const providerDecisions = useMemo(() => policyStatus?.provider_decisions || {}, [policyStatus]);
  const filteredProviderDecisions = useMemo(
    () =>
      Object.entries(providerDecisions).filter(([provider, decision]) =>
        matchesSearch(
          normalizedQuery,
          provider,
          decision?.strategy_label,
          decision?.preserve_prefix_for_provider_cache ? "preserve" : "compress",
          decision?.semantic_cache_enabled ? "semantic cache on" : "semantic cache off",
          decision?.compress_tool_outputs_only ? "tool outputs only" : "all outputs",
        ),
      ),
    [normalizedQuery, providerDecisions],
  );
  const filteredProviderStatus = useMemo(
    () =>
      providerStatus.filter((provider) =>
        matchesSearch(
          normalizedQuery,
          provider?.name,
          provider?.base_url,
          provider?.priority,
          provider?.healthy ? "healthy" : "disabled",
        ),
      ),
    [normalizedQuery, providerStatus],
  );
  const evidenceRecommendation = routingEvidence?.recommendation || null;
  const evidenceStatus = routingEvidence?.status || "no_evidence";
  const scorerStatus = routingEvidence?.scorer?.status || "unknown";
  const scorerLabel = {
    promoted: "Promoted calibrated scorer",
    heuristic: "Heuristic scorer",
    invalid: "Invalid calibrated scorer",
  }[scorerStatus] || "Scorer status unavailable";
  const evidenceStatusLabel = {
    no_evidence: "No evidence",
    collecting: "Collecting evidence",
    quality_blocked: "Quality blocked",
    ready: "Ready to promote",
  }[evidenceStatus] || "Unknown";
  const modeDescription = activeMode === "custom"
    ? "A custom routing preset is active. Choosing a preset will replace it."
    : activeMode === "aggressive"
      ? "Aggressive routes to the economy preset after role bindings are applied."
      : activeMode === "balanced"
        ? "Balanced keeps the canonical codex-gpt54mini-high preset after role bindings are applied."
        : "Off disables routing while preserving locked role assignments.";

  useEffect(() => {
    if (
      !optimisticMode ||
      committedGeneration <= optimisticMode.generation ||
      backendMode !== optimisticMode.mode
    ) {
      return undefined;
    }

    const confirmation = window.setTimeout(() => {
      setOptimisticMode(null);
      setModeConfirmationWarning(null);
    }, 0);
    return () => window.clearTimeout(confirmation);
  }, [backendMode, committedGeneration, optimisticMode]);

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

  return (
    <div
      className="page-stack"
      data-committed-generation={committedGeneration}
      data-backend-mode={backendMode}
      data-health-status={health?.status || ""}
      data-last-updated={lastUpdated || ""}
      data-refresh-error={refreshError || ""}
      data-refreshing={refreshing ? "true" : "false"}
    >
      {toggleError ? (
        <div className="alert-card" role="alert">
          <span>Failed to update routing mode: {toggleError}</span>
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

      {modeConfirmationWarning && pendingMode ? (
        <div className="alert-card" role="status">
          {modeConfirmationWarning}
        </div>
      ) : null}

      {modelRouting.reason ? (
        <div className="alert-card" role="status">
          Model routing is currently unavailable: {modelRouting.reason}. {modelRouting.install_hint}
        </div>
      ) : null}

      {modelRouting.mode === "custom" ? (
        <div className="alert-card" role="status">
          A custom routing preset is active. Choosing Off, Balanced, or Aggressive will replace it.
        </div>
      ) : null}

      {configFlagsError ? (
        <div className="alert-card" role="status">
          Runtime config API unavailable in proxy: {configFlagsError}. Routing controls may require a newer
          backend build.
        </div>
      ) : null}

      <SafeSavingsPanel
        status={safeSavingsStatus}
        loading={safeSavingsLoading}
        error={safeSavingsError}
        disabling={safeSavingsDisabling}
        disableError={safeSavingsDisableError}
        onDisable={handleSafeSavingsDisable}
      />

      <RoutingStudio />
      <OrchestrationStudio searchQuery={normalizedQuery} />

      <section className="panel">
        <div className="section-heading">
          <div className="heading-with-icon">
            <div className="heading-icon">
              <Network size={18} />
            </div>
            <div>
              <div className="eyebrow">Orchestrator</div>
              <h2>Routing mode control</h2>
              <p>Choose how aggressively Cutctx routes requests after role bindings are locked.</p>
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
                color: activeMode !== "off" ? "var(--text-primary)" : "var(--text-secondary)",
              }}
            >
              {activeMode === "off" ? "Routing off" : `Routing ${activeMode}`}
            </span>
          </div>
        </div>

        <div style={{ marginBottom: "var(--space-lg)" }}>
          <RoutingModeSelector
            value={activeMode}
            onChange={handleModeChange}
            disabled={updating || !canToggle}
          />
          <p className="text-secondary" style={{ marginTop: "0.5rem" }}>
            {modeDescription}
          </p>
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

        <section className="panel routing-evidence-panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Measured policy</div>
              <h2>Routing evidence</h2>
              <p>Shadow comparisons verify quality and savings without storing prompt or response text.</p>
            </div>
            {!routingEvidenceLoading && !routingEvidenceError ? (
              <span className={`status-pill routing-evidence-${evidenceStatus}`}>
                {evidenceStatusLabel}
              </span>
            ) : null}
          </div>

          {routingEvidenceError ? (
            <div className="alert-card" role="status">
              Routing evidence unavailable: {routingEvidenceError}
            </div>
          ) : null}

          {routingEvidenceLoading ? (
            <div className="metric-grid metric-grid-three">
              <article className="metric-card metric-card-compact">
                <div className="metric-label">Evidence status</div>
                <div className="metric-value">Loading</div>
              </article>
            </div>
          ) : null}

          {!routingEvidenceLoading && !routingEvidenceError ? (
            <>
              <div className="routing-evidence-summary">
                <strong>
                  {formatInteger(routingEvidence?.sample_progress?.observed || 0)} / {formatInteger(routingEvidence?.sample_progress?.required || 0)} samples
                </strong>
                <span>
                  Shadow sampling {routingEvidence?.shadow?.enabled ? "enabled" : "disabled"}
                  {routingEvidence?.shadow?.enabled
                    ? ` at ${formatPercent((routingEvidence?.shadow?.sample_rate || 0) * 100)}`
                    : ""}
                </span>
                <span>{scorerLabel}</span>
                {scorerStatus === "promoted" ? (
                  <span>
                    {formatInteger(routingEvidence?.scorer?.training_samples || 0)} training samples · minimum confidence {Number(routingEvidence?.scorer?.minimum_confidence || 0).toFixed(2)}
                  </span>
                ) : null}
              </div>

              {evidenceStatus === "ready" && evidenceRecommendation ? (
                <div className="metric-grid metric-grid-three">
                  <article className="metric-card metric-card-compact">
                    <div className="metric-label">Measured mean quality</div>
                    <div className="metric-value">{formatPercent(evidenceRecommendation.mean_quality * 100)}</div>
                    <div className="metric-footnote">Floor {formatPercent((routingEvidence?.constraints?.minimum_mean_quality || 0) * 100)}</div>
                  </article>
                  <article className="metric-card metric-card-compact">
                    <div className="metric-label">Unsafe rate</div>
                    <div className="metric-value">{formatPercent(evidenceRecommendation.unsafe_rate * 100)}</div>
                    <div className="metric-footnote">Maximum {formatPercent((routingEvidence?.constraints?.maximum_unsafe_rate || 0) * 100)}</div>
                  </article>
                  <article className="metric-card metric-card-compact">
                    <div className="metric-label">Verified savings</div>
                    <div className="metric-value">{formatCurrency(evidenceRecommendation.total_savings_usd)}</div>
                    <div className="metric-footnote">Across {formatInteger(evidenceRecommendation.routed_samples)} routed samples</div>
                  </article>
                  <article className="metric-card metric-card-compact">
                    <div className="metric-label">Recommended confidence</div>
                    <div className="metric-value">{Number(evidenceRecommendation.minimum_confidence).toFixed(2)}</div>
                    <div className="metric-footnote">Read-only recommendation</div>
                  </article>
                  <article className="metric-card metric-card-compact">
                    <div className="metric-label">Measured routing rate</div>
                    <div className="metric-value">{formatPercent(evidenceRecommendation.routing_rate * 100)}</div>
                    <div className="metric-footnote">At the recommended threshold</div>
                  </article>
                </div>
              ) : (
                <p className="text-secondary routing-evidence-guidance">
                  {evidenceStatus === "collecting"
                    ? "Continue shadow sampling until the minimum evidence requirement is met."
                    : evidenceStatus === "quality_blocked"
                      ? "Observed candidates do not satisfy the configured quality and unsafe-rate guardrails."
                      : "Enable sampled shadow evaluation to build a verified quality and cost frontier."}
                </p>
              )}
            </>
          ) : null}
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
              <span>Mode</span>
              <strong>{activeMode}</strong>
            </div>
            <div className="graphify-kv">
              <span>Preset</span>
              <strong>{currentPreset}</strong>
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
                {filteredProviderDecisions.length > 0 ? (
                  filteredProviderDecisions.map(([provider, decision]) => (
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
                  ))
                ) : (
                  <div className="text-secondary" style={{ gridColumn: "1 / -1", padding: "0.25rem 0" }}>
                    No provider policy entries match your search.
                  </div>
                )}
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
              {filteredProviderStatus.length > 0 ? filteredProviderStatus.map((provider) => {
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
              }) : (
                <div className="text-secondary" style={{ gridColumn: "1 / -1", padding: "0.25rem 0" }}>
                  No provider controls match your search.
                </div>
              )}
            </div>
          ) : null}
        </section>
      </section>
    </div>
  );
}
