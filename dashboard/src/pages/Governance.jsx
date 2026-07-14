import { CheckCircle2, Copy, MinusCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { formatInteger, formatRelativeTime } from "../lib/format";
import {
  fetchDashboardJson,
  patchDashboardConfig,
  useDashboardData,
} from "../lib/use-dashboard-data";
import { formatCurrency } from "../lib/format";

const GOVERNANCE_PATHS = {
  audit: "/audit/events",
  entitlements: "/entitlements",
  rbac: "/rbac/roles",
};

const FEATURE_CONFIG = [
  {
    key: "firewall",
    flagKey: "firewall_enabled",
    label: "Request firewall",
    envVar: "CUTCTX_FIREWALL_ENABLED=1",
    description:
      "Scan every request for prompt injection, jailbreaks, and PII before it reaches the model.",
    tier: "free",
    liveToggle: false,
    statPath: (stats) => stats?.config?.firewall,
  },
  {
    key: "rate_limit",
    flagKey: "rate_limit_enabled",
    label: "Rate limiting",
    envVar: "CUTCTX_RATE_LIMIT_ENABLED=true",
    description:
      "Token-bucket rate limiting per API key. Configure limits with CUTCTX_RATE_LIMIT_TPM and CUTCTX_RATE_LIMIT_RPM.",
    tier: "free",
    liveToggle: false,
    statPath: (stats) => stats?.config?.rate_limiter,
  },
  {
    key: "task_aware",
    flagKey: "task_aware_enabled",
    label: "Task-aware compression",
    envVar: "CUTCTX_TASK_AWARE_ENABLED=1",
    description: "Modulate compression depth based on relevance to the active task.",
    tier: "free",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "dedup",
    flagKey: "dedup_enabled",
    label: "Semantic deduplication",
    envVar: "CUTCTX_DEDUP_ENABLED=1",
    description:
      "Detect and collapse repeated content across messages using reversible CCR pointers.",
    tier: "free",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "context_budget",
    flagKey: "context_budget_enabled",
    label: "Context budget controller",
    envVar: "CUTCTX_CONTEXT_BUDGET_ENABLED=1",
    description:
      "Progressively increase compression as the context window fills.",
    tier: "free",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "profiles",
    flagKey: "profiles_enabled",
    label: "Compression profiles",
    envVar: "CUTCTX_PROFILES_ENABLED=1",
    description:
      "Learn per-workspace compression patterns across sessions for future reuse.",
    tier: "free",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "shared_context",
    flagKey: "shared_context_enabled",
    entitlementKey: "cross_agent_memory",
    label: "Cross-agent memory",
    envVar: "CUTCTX_SHARED_CONTEXT_ENABLED=1",
    description:
      "Share compressed context and cache hits across agents working in the same workspace.",
    tier: "business",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "episodic_memory",
    flagKey: "episodic_memory_enabled",
    entitlementKey: "episodic_memory",
    label: "Episodic memory",
    envVar: "CUTCTX_EPISODIC_MEMORY_ENABLED=1",
    description: "Store and reinject project memories across sessions.",
    tier: "business",
    liveToggle: true,
    statPath: (stats) => stats?.config?.memory,
  },
  {
    key: "cost_forecast",
    flagKey: "cost_forecast_enabled",
    label: "Cost forecasting",
    envVar: "CUTCTX_COST_FORECAST_ENABLED=1",
    description:
      "Estimate request cost up front to feed policy decisions before compression runs.",
    tier: "free",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "autopilot",
    flagKey: "autopilot_enabled",
    label: "Compression autopilot",
    envVar: "CUTCTX_AUTOPILOT=1",
    description:
      "Adjust compression aggressiveness per task type from recent quality signals.",
    tier: "free",
    liveToggle: true,
    statPath: () => null,
  },
  {
    key: "orchestrator",
    flagKey: null,
    linkTo: "/orchestrator",
    label: "Routing mode",
    envVar: "CUTCTX_MODEL_ROUTING_PRESET=codex-gpt54mini-high",
    description:
      "Choose Off, Balanced, or Aggressive on the dedicated routing page.",
    tier: "free",
    liveToggle: false,
    statPath: (stats) => stats?.model_routing?.mode || (stats?.config?.orchestrator ? "balanced" : "off"),
  },
  {
    key: "audit",
    flagKey: "audit_enabled",
    entitlementKey: "audit_logs",
    label: "Audit trail",
    envVar: "CUTCTX_AUDIT_DISABLED=0",
    description:
      "Persist admin and governance activity in an audit log. Restart required to fully apply changes.",
    tier: "enterprise",
    liveToggle: false,
    statPath: (_, sections) => sections?.audit?.ok || false,
  },
  {
    key: "rbac",
    flagKey: null,
    entitlementKey: "rbac",
    label: "RBAC admin controls",
    envVar: "Enterprise entitlement required",
    description:
      "Role assignment and permission enforcement surfaces. This is control-plane state, not a simple boolean flag.",
    tier: "enterprise",
    liveToggle: false,
    statPath: (_, sections) => sections?.rbac?.ok ?? null,
  },
];

function emptySection() {
  return { ok: false, data: null, error: "Loading...", status: null };
}

function normalizeAssignments(rbacData) {
  const raw = rbacData?.assignments;
  if (Array.isArray(raw)) {
    return raw;
  }
  if (raw && typeof raw === "object") {
    return Object.entries(raw).map(([userId, role]) => ({
      user_id: userId,
      role,
    }));
  }
  return [];
}

function titleCase(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function formatBudgetPeriodLabel(period) {
  if (!period) {
    return "Current window";
  }
  return `${titleCase(period)} window`;
}

function getEntitlementEntry(feature, sections) {
  if (!feature.entitlementKey) {
    return null;
  }
  return sections?.entitlements?.data?.features?.[feature.entitlementKey] || null;
}

function getFeatureAvailability(feature, sections) {
  const entitlement = getEntitlementEntry(feature, sections);
  if (!entitlement) {
    return null;
  }
  return Boolean(entitlement.available);
}

function getRequiredTierLabel(feature, sections) {
  const entitlement = getEntitlementEntry(feature, sections);
  return titleCase(entitlement?.required_tier || feature.tier);
}

function describeSectionStatus(section, sections) {
  if (section.ok) {
    return "Reachable";
  }
  if (section.status === 403) {
    const tier = sections?.entitlements?.data?.current_tier;
    return tier ? `Unavailable on ${tier} tier` : "Unavailable on current tier";
  }
  return section.error || "Unavailable";
}

function CopyButton({ text, label = "Copy to clipboard" }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  const handleCopy = useCallback(async () => {
    setCopyError(false);
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable');
      }
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopyError(true);
    }
  }, [text]);

  return (
    <>
      <button
        className="copy-btn"
        onClick={handleCopy}
        title="Copy to clipboard"
        aria-label={label}
        type="button"
      >
        {copied ? <CheckCircle2 size={13} /> : <Copy size={13} />}
      </button>
      {copyError ? (
        <span className="copy-feedback" role="status">
          Could not copy to clipboard. Copy the value manually.
        </span>
      ) : null}
    </>
  );
}

function FeatureToggle({ enabled, onToggle, busy, disabled, label }) {
  return (
    <button
      className={`feature-toggle ${enabled ? "feature-toggle-on" : "feature-toggle-off"}`}
      onClick={onToggle}
      disabled={busy || disabled}
      aria-label={label || (enabled ? "Disable feature" : "Enable feature")}
      type="button"
    >
      <span className="feature-toggle-knob" />
    </button>
  );
}

function resolveFeatureState(feature, stats, configFlags, liveFlags, sections) {
  if (!feature.flagKey) {
    return feature.statPath(stats, sections);
  }
  if (feature.flagKey in liveFlags) {
    return liveFlags[feature.flagKey];
  }
  if (configFlags?.live_toggleable?.[feature.flagKey]?.enabled != null) {
    return Boolean(configFlags.live_toggleable[feature.flagKey].enabled);
  }
  if (configFlags?.restart_required?.[feature.flagKey]?.enabled != null) {
    return Boolean(configFlags.restart_required[feature.flagKey].enabled);
  }
  return feature.statPath(stats, sections);
}

function normalizeAppliedLiveFlags(appliedLive) {
  const next = {};
  for (const [key, value] of Object.entries(appliedLive || {})) {
    if (value && typeof value === "object" && "enabled" in value) {
      next[key] = Boolean(value.enabled);
    } else if (value && typeof value === "object" && "mode" in value) {
      next[key] = String(value.mode);
    } else if (typeof value === "boolean") {
      next[key] = value;
    } else if (typeof value === "string") {
      next[key] = value;
    }
  }
  return next;
}

function FeatureRow({
  feature,
  stats,
  configFlags,
  liveFlags,
  sections,
  onToggle,
  toggleBusy,
}) {
  const isActive = resolveFeatureState(feature, stats, configFlags, liveFlags, sections);
  const availability = getFeatureAvailability(feature, sections);
  const requiredTier = getRequiredTierLabel(feature, sections);
  const toggleable = Boolean(feature.flagKey);
  const locked = availability === false;
  const statusText = locked
    ? "Unavailable"
    : typeof isActive === "string"
      ? titleCase(isActive)
      : isActive === true
      ? "Active"
      : isActive === false
        ? "Inactive"
        : null;

  return (
    <div className="feature-config-row">
      <div className="feature-config-main">
        <div className="feature-config-header">
          <span className="feature-config-name">{feature.label}</span>
          {feature.tier !== "free" ? (
            <span className="tier-badge tier-enterprise">{titleCase(feature.tier)}</span>
          ) : null}
          {toggleable && !feature.liveToggle ? (
            <span className="tier-badge tier-restart">
              <RefreshCw size={10} /> Restart required
            </span>
          ) : null}
          {statusText ? (
            <span className={locked || isActive === false ? "status-inactive" : "status-active"}>
              {locked || isActive === false ? <MinusCircle size={12} /> : <CheckCircle2 size={12} />}
              {statusText}
            </span>
          ) : null}
        </div>
        <p className="feature-config-desc">{feature.description}</p>
        {locked ? (
          <p className="feature-config-desc">Available on {requiredTier} tier.</p>
        ) : null}
      </div>

      <div className="feature-config-controls">
        {toggleable ? (
          <>
            <FeatureToggle
              enabled={!locked && Boolean(isActive)}
              onToggle={() => onToggle(feature.flagKey, !isActive)}
              busy={toggleBusy === feature.flagKey}
              disabled={locked}
              label={`${isActive ? "Disable" : "Enable"} ${feature.label}`}
            />
            <div className="feature-config-env">
              <code>{feature.envVar}</code>
              <CopyButton text={feature.envVar} label={`Copy ${feature.envVar}`} />
            </div>
          </>
        ) : (
          <>
            <div className="feature-config-env">
              <code>{feature.envVar}</code>
              <CopyButton text={feature.envVar} label={`Copy ${feature.envVar}`} />
            </div>
            {feature.linkTo ? (
              <Link className="ghost-button" to={feature.linkTo} style={{ width: "fit-content" }}>
                Open routing page
              </Link>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

export default function Governance({ searchQuery = "" }) {
  const {
    stats,
    health,
    loading: statsLoading,
    configFlags,
    configFlagsError,
    refresh,
  } = useDashboardData();

  const [sections, setSections] = useState({
    audit: emptySection(),
    entitlements: emptySection(),
    rbac: emptySection(),
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [liveFlags, setLiveFlags] = useState({});
  const [toggleBusy, setToggleBusy] = useState(null);

  const configLiveFlags = useMemo(() => {
    if (!configFlags) {
      return {};
    }

    const next = {};
    for (const [key, value] of Object.entries(configFlags.live_toggleable || {})) {
      if (value?.enabled != null) {
        next[key] = Boolean(value.enabled);
      }
    }
    for (const [key, value] of Object.entries(configFlags.restart_required || {})) {
      if (value?.enabled != null) {
        next[key] = Boolean(value.enabled);
      }
    }
    return next;
  }, [configFlags]);

  const effectiveLiveFlags = { ...configLiveFlags, ...liveFlags };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      const entries = await Promise.all(
        Object.entries(GOVERNANCE_PATHS).map(async ([key, path]) => {
          try {
            const data = await fetchDashboardJson(path);
            return [key, { ok: true, data, error: null, status: 200 }];
          } catch (error) {
            return [
              key,
              {
                ok: false,
                data: null,
                error: error?.message || String(error),
                status: error?.status ?? null,
              },
            ];
          }
        }),
      );

      if (cancelled) {
        return;
      }

      setSections(Object.fromEntries(entries));
      setLoading(false);
      setLastUpdated(new Date().toISOString());
    };

    load();
    const id = setInterval(load, 15_000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const handleToggle = useCallback(
    async (flagKey, value) => {
      setToggleBusy(flagKey);
      try {
        const response = await patchDashboardConfig({ [flagKey]: value });
        const appliedLive = normalizeAppliedLiveFlags(response?.applied_live);

        setLiveFlags((prev) => ({
          ...prev,
          [flagKey]: value,
          ...appliedLive,
        }));
        await refresh?.();
      } finally {
        setToggleBusy(null);
      }
    },
    [refresh],
  );

  const assignments = useMemo(
    () => normalizeAssignments(sections.rbac.data),
    [sections.rbac.data],
  );

  const failedSections = Object.entries(sections).filter(
    ([key, section]) => key !== "entitlements" && !section.ok && section.status !== 403 && !loading,
  );

  const rateLimiter = stats?.rate_limiter || null;
  const rateLimiterHealth = health?.checks?.rate_limiter || null;
  const budget = stats?.cost?.budget || null;
  const rateLimitEnabled =
    stats?.config?.rate_limiter ??
    configFlags?.restart_required?.rate_limit_enabled?.enabled ??
    false;
  const rateLimitStatusLabel = rateLimitEnabled
    ? rateLimiter
      ? "Active"
      : "Configured"
    : "Inactive";
  const rateLimitSummary = rateLimitEnabled
    ? rateLimiter
      ? "Token-bucket throttling is active and reporting live metrics."
      : "Rate limiting is enabled, but this proxy is not exposing live limiter metrics on /stats."
    : "Rate limiting is not enabled yet.";
  const budgetEnabled = Boolean(budget?.enabled);
  const budgetStatusLabel = budgetEnabled
    ? budget?.exceeded
      ? "Exceeded"
      : "Tracking"
    : "Unlimited";
  const budgetSummary = budgetEnabled
    ? budget?.exceeded
      ? "Spend has crossed the configured proxy budget for this period."
      : "Cost tracking is publishing live budget usage for the active window."
    : "No proxy budget is configured; spend is being tracked without a hard cap.";
  const query = searchQuery.trim().toLowerCase();
  const filteredFeatures = FEATURE_CONFIG.filter((feature) => {
    if (!query) {
      return true;
    }
    return (
      feature.label.toLowerCase().includes(query) ||
      feature.description.toLowerCase().includes(query)
    );
  });

  return (
    <section className="page-stack">
      {failedSections.length > 0 ? (
        <div className="alert-card" role="alert">
          Some governance surfaces could not be reached: {failedSections.map(([key]) => key).join(", ")}.
        </div>
      ) : null}

      {configFlagsError ? (
        <div className="alert-card" role="status">
          Runtime config API unavailable: {configFlagsError}. Dashboard toggles only work once the backend exposes config flag routes.
        </div>
      ) : null}

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Live control</div>
            <h2>Rate limiting</h2>
          </div>
          <p>{rateLimitSummary}</p>
        </div>

        <div className="metric-grid metric-grid-four" aria-busy={statsLoading}>
          <article className="metric-card metric-card-compact">
            <div className="metric-label">Status</div>
            <div className="metric-value">{rateLimitStatusLabel}</div>
            <div className="metric-footnote">
              {rateLimiter
                ? "Dashboard toggle updates config. Restart may still be required."
                : rateLimiterHealth?.ready
                  ? "Health checks report the limiter is loaded, but /stats has no live limiter payload."
                  : "Dashboard toggle updates config. Restart may still be required."}
            </div>
          </article>

          <article className="metric-card metric-card-compact">
            <div className="metric-label">Active keys</div>
            <div className="metric-value">{formatInteger(rateLimiter?.active_keys || 0)}</div>
            <div className="metric-footnote">Keys with live rate state</div>
          </article>

          <article className="metric-card metric-card-compact">
            <div className="metric-label">Token limit</div>
            <div className="metric-value">
              {rateLimiter ? formatInteger(rateLimiter.tokens_per_minute || 0) : "-"}
            </div>
            <div className="metric-footnote">Tokens per minute per key</div>
          </article>

          <article className="metric-card metric-card-compact">
            <div className="metric-label">Request limit</div>
            <div className="metric-value">
              {rateLimiter ? formatInteger(rateLimiter.requests_per_minute || 0) : "-"}
            </div>
            <div className="metric-footnote">Requests per minute per key</div>
          </article>
        </div>
      </div>

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Budget guardrail</div>
            <h2>Cost budget</h2>
          </div>
          <p>{budgetSummary}</p>
        </div>

        <div className="metric-grid metric-grid-four" aria-busy={statsLoading}>
          <article className="metric-card metric-card-compact">
            <div className="metric-label">Status</div>
            <div className="metric-value">{budgetStatusLabel}</div>
            <div className="metric-footnote">
              {budgetEnabled
                ? `${formatBudgetPeriodLabel(budget?.period)} budget is enforced before upstream calls.`
                : "Configure --budget or CUTCTX_BUDGET_LIMIT_USD to enforce spend caps."}
            </div>
          </article>

          <article className="metric-card metric-card-compact">
            <div className="metric-label">Budget limit</div>
            <div className="metric-value">
              {budgetEnabled ? formatCurrency(budget?.limit_usd || 0) : "-"}
            </div>
            <div className="metric-footnote">{formatBudgetPeriodLabel(budget?.period)}</div>
          </article>

          <article className="metric-card metric-card-compact">
            <div className="metric-label">Spend used</div>
            <div className="metric-value">{formatCurrency(budget?.spent_usd || 0)}</div>
            <div className="metric-footnote">
              {budgetEnabled ? `${budget?.percent_used || 0}% of limit used` : "Tracked in the current proxy window"}
            </div>
          </article>

          <article className="metric-card metric-card-compact">
            <div className="metric-label">Remaining</div>
            <div className="metric-value">
              {budgetEnabled ? formatCurrency(budget?.remaining_usd || 0) : "Unlimited"}
            </div>
            <div className="metric-footnote">
              {budgetEnabled
                ? budget?.exceeded
                  ? "New requests will be rejected until the window resets."
                  : "Budget remaining before proxy rejects new spend."
                : "No budget cutoff is active."}
            </div>
          </article>
        </div>
      </div>

      <div className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Feature configuration</div>
            <h2>Enable optional features</h2>
          </div>
          <p>
            Dashboard toggles write proxy config when supported. Some features apply on the next request, while others need a restart to take full effect.
          </p>
        </div>

        <div className="feature-config-list">
          {filteredFeatures.map((feature) => (
            <FeatureRow
              key={feature.key}
              feature={feature}
              stats={stats}
              configFlags={configFlags}
              liveFlags={effectiveLiveFlags}
              sections={sections}
              onToggle={handleToggle}
              toggleBusy={toggleBusy}
            />
          ))}
        </div>
      </div>

      <div className="metric-grid metric-grid-two">
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise</div>
              <h2>Audit surface</h2>
            </div>
            <p>
              {lastUpdated
                ? `Refreshed ${formatRelativeTime(lastUpdated)}`
                : "Polling every 15 seconds"}
            </p>
          </div>
          <div className="graphify-kv-grid">
            <div className="graphify-kv">
              <span>Status</span>
              <strong>{describeSectionStatus(sections.audit, sections)}</strong>
            </div>
            <div className="graphify-kv">
              <span>Recent events</span>
              <strong>{formatInteger(sections.audit.data?.events?.length || 0)}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Enterprise</div>
              <h2>RBAC surface</h2>
            </div>
            <p>
              {lastUpdated
                ? `Refreshed ${formatRelativeTime(lastUpdated)}`
                : "Polling every 15 seconds"}
            </p>
          </div>
          <div className="graphify-kv-grid">
            <div className="graphify-kv">
              <span>Status</span>
              <strong>{describeSectionStatus(sections.rbac, sections)}</strong>
            </div>
            <div className="graphify-kv">
              <span>Assignments</span>
              <strong>{formatInteger(assignments.length)}</strong>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
