import { useEffect, useMemo, useState } from "react";
import { Activity, Boxes, KeyRound, RefreshCw, Route, Save, Users } from "lucide-react";

import { getAdminAuthHeaders } from "../lib/admin-auth";
import { getProxyUrl } from "../lib/api";

const TABS = [
  ["providers", "Providers", KeyRound],
  ["models", "Models", Boxes],
  ["roles", "Roles", Users],
  ["routing", "Routing", Route],
  ["activity", "Activity", Activity],
];

async function orchestrationApi(path, options = {}) {
  const response = await fetch(getProxyUrl(`/v1/orchestration${path}`), {
    cache: "no-store",
    ...options,
    headers: {
      ...getAdminAuthHeaders(),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // A non-JSON error is converted to the status below.
  }
  if (!response.ok) {
    const detail = payload?.detail?.message || payload?.detail || `${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function emptyConfig() {
  return {
    version: 1,
    providers: [],
    roles: [],
    bindings: [],
    settings: {
      mode: "strict",
      policy: "role_locked",
      retries: 1,
      timeout_seconds: 120,
      fallback_triggers: [],
      global_fallback_chain: [],
    },
  };
}

function modelDeploymentKey(model) {
  return model.deployment_key || model.key;
}

function providerRuntimeLabel(provider) {
  if (!provider?.runtime) {
    return "Provider runtime unavailable";
  }
  if (provider.runtime === "litellm") {
    return `LiteLLM · ${provider.runtime_provider || provider.id}`;
  }
  return provider.runtime;
}

export default function OrchestrationStudio() {
  const [tab, setTab] = useState("roles");
  const [config, setConfig] = useState(emptyConfig());
  const [providers, setProviders] = useState({ catalog: [], accounts: [] });
  const [models, setModels] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [modelSearch, setModelSearch] = useState("");
  const [newRole, setNewRole] = useState("");
  const [previewRole, setPreviewRole] = useState("");
  const [preview, setPreview] = useState(null);
  const [newProvider, setNewProvider] = useState({
    provider: "openai",
    display_name: "",
    base_url: "",
    api_key: "",
  });

  async function load() {
    setLoading(true);
    try {
      const [nextConfig, nextProviders, nextModels, nextExecutions] = await Promise.all([
        orchestrationApi("/config"),
        orchestrationApi("/providers"),
        orchestrationApi("/models"),
        orchestrationApi("/executions?limit=50"),
      ]);
      const defaults = emptyConfig();
      setConfig({
        ...defaults,
        ...(nextConfig || {}),
        providers: Array.isArray(nextConfig?.providers) ? nextConfig.providers : [],
        models: Array.isArray(nextConfig?.models) ? nextConfig.models : [],
        roles: Array.isArray(nextConfig?.roles) ? nextConfig.roles : [],
        bindings: Array.isArray(nextConfig?.bindings) ? nextConfig.bindings : [],
        settings: { ...defaults.settings, ...(nextConfig?.settings || {}) },
      });
      setProviders({
        catalog: Array.isArray(nextProviders?.catalog) ? nextProviders.catalog : [],
        accounts: Array.isArray(nextProviders?.accounts) ? nextProviders.accounts : [],
      });
      setModels(nextModels?.models || []);
      setExecutions(nextExecutions?.executions || []);
      setError(null);
    } catch (err) {
      setError(err?.message || "Orchestration platform is unavailable");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Initial data loading synchronizes this view with the orchestration API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  const filteredModels = useMemo(() => {
    const query = modelSearch.trim().toLowerCase();
    if (!query) {
      return models;
    }
    return models.filter((model) =>
      [model.key, model.deployment_key, model.account_id, model.display_name, ...(model.capabilities || [])]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [modelSearch, models]);

  const providerById = useMemo(
    () => new Map(providers.catalog.map((provider) => [provider.id, provider])),
    [providers.catalog],
  );

  const bindingForRole = (roleId) =>
    config.bindings.find(
      (binding) => binding.role === roleId && Object.keys(binding.selectors || {}).length === 0,
    );

  async function save(nextConfig = config, message = "Orchestration configuration saved") {
    setSaving(true);
    setError(null);
    try {
      const stored = await orchestrationApi("/config", {
        method: "PUT",
        body: JSON.stringify(nextConfig),
      });
      setConfig(stored);
      if (message) {
        setNotice(message);
        window.setTimeout(() => setNotice(null), 3000);
      }
      return stored;
    } catch (err) {
      setError(err?.message || "Unable to save orchestration configuration");
      return null;
    } finally {
      setSaving(false);
    }
  }

  function updateRoleModel(roleId, modelKey) {
    const existing = bindingForRole(roleId);
    const nextBindings = existing
      ? config.bindings.map((binding) =>
          binding.id === existing.id ? { ...binding, model: modelKey } : binding,
        )
      : [
          ...config.bindings,
          {
            id: `${roleId}-default`,
            role: roleId,
            model: modelKey,
            selectors: {},
            fallback_chain: [],
            required_capabilities: [],
            enabled: true,
          },
        ];
    setConfig({ ...config, bindings: nextBindings });
  }

  function addRole() {
    const name = newRole.trim();
    if (!name) {
      return;
    }
    const id = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    if (config.roles.some((role) => role.id === id)) {
      setError(`Role ${name} already exists`);
      return;
    }
    setConfig({
      ...config,
      roles: [
        ...config.roles,
        { id, name, description: "", required_capabilities: [] },
      ],
    });
    setNewRole("");
  }

  async function addProviderAccount(event) {
    event.preventDefault();
    const id = `${newProvider.provider}-${Date.now()}`;
    const providerSpec = providerById.get(newProvider.provider);
    const authMethod = providerSpec?.auth_methods?.includes("none") ? "none" : "api_key";
    const account = {
      id,
      provider: newProvider.provider,
      display_name: newProvider.display_name || newProvider.provider,
      auth_method: authMethod,
      credential_ref: null,
      base_url: newProvider.base_url || null,
      organization_id: null,
      workspace_id: null,
      custom_headers: {},
      enabled: true,
      metadata: {},
    };
    try {
      await orchestrationApi(`/providers/${id}`, {
        method: "PUT",
        body: JSON.stringify(account),
      });
    } catch (err) {
      setError(err?.message || "Unable to save provider account");
      return;
    }
    if (newProvider.api_key) {
      try {
        await orchestrationApi(`/providers/${id}/credential`, {
          method: "PUT",
          body: JSON.stringify({ api_key: newProvider.api_key }),
        });
      } catch (err) {
        setError(
          `Account was added, but its credential was not stored: ${err?.message || "unknown error"}`,
        );
        await load();
        return;
      }
    }
    setNewProvider({ provider: "openai", display_name: "", base_url: "", api_key: "" });
    await load();
    setNotice("Provider account and credential saved");
  }

  async function testProvider(accountId) {
    setNotice("Testing provider connection…");
    try {
      const result = await orchestrationApi(`/providers/${accountId}/test`, { method: "POST" });
      setNotice(result.ok ? `Connection healthy (${Math.round(result.latency_ms || 0)} ms)` : result.status);
    } catch (err) {
      setError(err?.message || "Provider connection test failed");
    }
  }

  async function refreshModels(accountId) {
    setNotice("Refreshing provider models…");
    try {
      await orchestrationApi(`/models/refresh/${accountId}`, { method: "POST" });
      await load();
      setNotice("Model registry refreshed");
    } catch (err) {
      setError(err?.message || "Model refresh failed");
    }
  }

  async function runPreview() {
    try {
      const result = await orchestrationApi("/route", {
        method: "POST",
        body: JSON.stringify({ role: previewRole }),
      });
      setPreview(result);
      setError(null);
    } catch (err) {
      setPreview(null);
      setError(err?.message || "Route preview failed");
    }
  }

  if (loading) {
    return <section className="panel orchestration-studio">Loading orchestration platform…</section>;
  }

  if (error && !config.roles.length && !providers.catalog.length) {
    return (
      <section className="panel orchestration-studio">
        <div className="eyebrow">Orchestration platform</div>
        <h2>Configuration API unavailable</h2>
        <p className="text-secondary">{error}</p>
      </section>
    );
  }

  return (
    <section className="panel orchestration-studio">
      <div className="section-heading orchestration-heading">
        <div>
          <div className="eyebrow">Orchestration platform</div>
          <h2>Provider-neutral model control plane</h2>
          <p>Configure accounts, discover capabilities, lock roles, test fallbacks, and inspect every decision.</p>
        </div>
        <button className="primary-button" onClick={() => save()} disabled={saving} type="button">
          <Save size={15} /> {saving ? "Saving…" : "Save changes"}
        </button>
      </div>

      {error ? <div className="alert-card" role="alert">{error}</div> : null}
      {notice ? <div className="orchestration-notice" role="status">{notice}</div> : null}

      <div className="orchestration-tabs" role="tablist" aria-label="Orchestration configuration">
        {TABS.map(([id, label, Icon]) => (
          <button
            key={id}
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}
            role="tab"
            aria-selected={tab === id}
            type="button"
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === "providers" ? (
        <div className="orchestration-pane">
          <div className="orchestration-card-grid">
            {providers.accounts.map((account) => (
              <article className="orchestration-card" key={account.id}>
                <span className="status-pill">{account.enabled ? "Enabled" : "Disabled"}</span>
                <span className={`status-pill ${account.credential_configured || account.auth_method === "none" ? "" : "warning"}`}>
                  {account.auth_method === "none"
                    ? "Local authentication"
                    : account.credential_configured
                      ? "Credential stored"
                      : "Credential missing"}
                </span>
                <h3>{account.display_name || account.id}</h3>
                <p>{account.provider} · {account.auth_method}</p>
                <p className="text-secondary">
                  {providerRuntimeLabel(providerById.get(account.provider))}
                </p>
                <p className="text-secondary">{account.base_url || "Provider default endpoint"}</p>
                <div className="orchestration-actions">
                  <button className="ghost-button" onClick={() => testProvider(account.id)} type="button">Test</button>
                  <button className="ghost-button" onClick={() => refreshModels(account.id)} type="button">
                    <RefreshCw size={13} /> Refresh models
                  </button>
                </div>
              </article>
            ))}
          </div>
          <form className="orchestration-form" onSubmit={addProviderAccount}>
            <h3>Add provider account</h3>
            <select aria-label="Provider" value={newProvider.provider} onChange={(event) => setNewProvider({ ...newProvider, provider: event.target.value })}>
              {providers.catalog.map((provider) => <option value={provider.id} key={provider.id}>{provider.display_name} — {providerRuntimeLabel(provider)}</option>)}
            </select>
            <input aria-label="Account display name" placeholder="Account display name" value={newProvider.display_name} onChange={(event) => setNewProvider({ ...newProvider, display_name: event.target.value })} />
            <input aria-label="Custom base URL" placeholder="Custom base URL (optional)" value={newProvider.base_url} onChange={(event) => setNewProvider({ ...newProvider, base_url: event.target.value })} />
            <input aria-label="API key" type="password" autoComplete="new-password" placeholder="API key (encrypted at rest)" value={newProvider.api_key} onChange={(event) => setNewProvider({ ...newProvider, api_key: event.target.value })} />
            <button className="primary-button" type="submit">Add account</button>
          </form>
        </div>
      ) : null}

      {tab === "models" ? (
        <div className="orchestration-pane">
          <input aria-label="Search models or capabilities" className="orchestration-search" placeholder="Search models or capabilities" value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} />
          <div className="orchestration-model-list">
            {filteredModels.slice(0, 100).map((model) => (
              <article key={modelDeploymentKey(model)}>
                <div><strong>{model.display_name || model.id}</strong><span>{modelDeploymentKey(model)}</span></div>
                <div className="capability-list">{(model.capabilities || []).map((capability) => <span key={capability}>{capability}</span>)}</div>
                <span className={`availability ${model.available && !model.deprecated && model.executable !== false ? "ok" : "bad"}`}>
                  {model.deprecated
                    ? "Deprecated"
                    : !model.available
                      ? "Unavailable"
                      : model.executable === false
                        ? "No enabled account"
                        : "Available"}
                </span>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {tab === "roles" ? (
        <div className="orchestration-pane">
          <div className="orchestration-role-list">
            {config.roles.map((role) => {
              const binding = bindingForRole(role.id);
              return (
                <article key={role.id}>
                  <div><strong>{role.name}</strong><span>{role.description || "Custom role"}</span></div>
                  <select value={binding?.model || ""} onChange={(event) => updateRoleModel(role.id, event.target.value)} aria-label={`Model for ${role.name}`}>
                    <option value="">Unassigned</option>
                    {models.map((model) => {
                      const deploymentKey = modelDeploymentKey(model);
                      return <option value={deploymentKey} key={deploymentKey} disabled={model.executable === false}>{model.display_name || model.key} · {model.account_id || model.provider}{model.executable === false ? " · unavailable" : ""}</option>;
                    })}
                  </select>
                  <span className={binding ? "role-state assigned" : "role-state"}>{binding ? "Locked" : "Needs assignment"}</span>
                </article>
              );
            })}
          </div>
          <div className="orchestration-inline-form">
            <input
              aria-label="New custom role"
              placeholder="New custom role"
              value={newRole}
              onChange={(event) => setNewRole(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addRole();
                }
              }}
            />
            <button className="ghost-button" onClick={addRole} type="button">Add role</button>
          </div>
        </div>
      ) : null}

      {tab === "routing" ? (
        <div className="orchestration-pane routing-settings-grid">
          <label><span>Enforcement mode</span><select value={config.settings.mode} onChange={(event) => setConfig({ ...config, settings: { ...config.settings, mode: event.target.value } })}><option value="strict">Strict — refuse unavailable assignments</option><option value="relaxed">Relaxed — use configured fallbacks</option></select></label>
          <label><span>Routing policy</span><select value={config.settings.policy} onChange={(event) => setConfig({ ...config, settings: { ...config.settings, policy: event.target.value } })}><option value="role_locked">Role locked</option><option value="manual">Manual</option><option value="fastest">Fastest</option><option value="cheapest">Cheapest</option><option value="highest_quality">Highest quality</option><option value="balanced">Balanced</option></select></label>
          <label><span>Retries per model</span><input type="number" min="0" max="10" value={config.settings.retries} onChange={(event) => setConfig({ ...config, settings: { ...config.settings, retries: Number(event.target.value) } })} /></label>
          <label><span>Timeout (seconds)</span><input type="number" min="1" value={config.settings.timeout_seconds} onChange={(event) => setConfig({ ...config, settings: { ...config.settings, timeout_seconds: Number(event.target.value) } })} /></label>
          <div className="route-preview">
            <h3>Deterministic route preview</h3>
            <div className="orchestration-inline-form">
              <select value={previewRole} onChange={(event) => setPreviewRole(event.target.value)}><option value="">Select role</option>{config.roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select>
              <button className="ghost-button" onClick={runPreview} disabled={!previewRole} type="button">Preview</button>
            </div>
            {preview ? <div className="route-preview-result"><strong>{preview.provider}:{preview.actual_model}</strong><span>{preview.reason}</span><span>{preview.fallback_used ? `Fallback from ${preview.fallback_from}` : "Assigned model enforced"}</span></div> : null}
          </div>
        </div>
      ) : null}

      {tab === "activity" ? (
        <div className="orchestration-pane orchestration-table-wrap">
          <table className="orchestration-table"><thead><tr><th>Role</th><th>Assigned</th><th>Actual</th><th>Latency</th><th>Fallback</th><th>Result</th></tr></thead><tbody>{executions.map((item) => <tr key={`${item.request_id}-${item.started_at}`}><td>{item.requested_role || "Manual"}</td><td>{item.assigned_model || "—"}</td><td>{item.provider}:{item.actual_model}</td><td>{Math.round(item.latency_ms || 0)} ms</td><td>{item.fallback_used ? item.fallback_trigger : "No"}</td><td>{item.error || "Success"}</td></tr>)}</tbody></table>
          {!executions.length ? <p className="text-secondary">No orchestrated executions recorded yet.</p> : null}
        </div>
      ) : null}
    </section>
  );
}
