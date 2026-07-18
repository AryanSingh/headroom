import { useEffect, useMemo, useState } from "react";
import { Activity, Boxes, KeyRound, Network, RefreshCw, Route, Save, Trash2, Users } from "lucide-react";

import { getAdminAuthHeaders } from "../lib/admin-auth";
import { getProxyUrl } from "../lib/api";
import RoleBindingEditor from "./RoleBindingEditor";

const TABS = [
  ["providers", "Providers", KeyRound],
  ["models", "Models", Boxes],
  ["harnesses", "Harnesses", Network],
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

function displayLabel(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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

export default function OrchestrationStudio({ searchQuery = "" }) {
  const [tab, setTab] = useState("roles");
  const [config, setConfig] = useState(emptyConfig());
  const [providers, setProviders] = useState({ catalog: [], accounts: [] });
  const [models, setModels] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [harnesses, setHarnesses] = useState([]);
  const [harnessManifestAvailable, setHarnessManifestAvailable] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [removingCredentialId, setRemovingCredentialId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [newRole, setNewRole] = useState("");
  const [modelSearch, setModelSearch] = useState("");
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
      const [nextConfig, nextProviders, nextModels, nextExecutions, nextHarnesses] = await Promise.all([
        orchestrationApi("/config"),
        orchestrationApi("/providers"),
        orchestrationApi("/models"),
        orchestrationApi("/executions?limit=50"),
        orchestrationApi("/harness-compatibility").catch(() => null),
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
      setHarnesses(Array.isArray(nextHarnesses?.harnesses) ? nextHarnesses.harnesses : []);
      setHarnessManifestAvailable(nextHarnesses !== null);
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

  const providerById = useMemo(
    () => new Map(providers.catalog.map((provider) => [provider.id, provider])),
    [providers.catalog],
  );

  const filteredModels = useMemo(() => {
    const query = [searchQuery, modelSearch].filter(Boolean).join(" ").trim().toLowerCase();
    if (!query) {
      return models;
    }
    return models.filter((model) =>
      [model.key, model.deployment_key, model.account_id, model.display_name, ...(model.capabilities || [])]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [models, modelSearch, searchQuery]);

  const filteredAccounts = useMemo(() => {
    const query = String(searchQuery || "").trim().toLowerCase();
    if (!query) {
      return providers.accounts;
    }
    return providers.accounts.filter((account) =>
      matchesSearch(
        query,
        account.id,
        account.provider,
        account.display_name,
        account.auth_method,
        account.base_url,
        providerRuntimeLabel(providerById.get(account.provider)),
        account.credential_configured ? "credential stored" : "credential missing",
      ),
    );
  }, [providerById, providers.accounts, searchQuery]);

  const filteredHarnesses = useMemo(() => {
    const query = String(searchQuery || "").trim().toLowerCase();
    if (!query) {
      return harnesses;
    }
    return harnesses.filter((harness) =>
      matchesSearch(query, harness.id, harness.support_level, harness.notes, harness.routing ? "routing" : "", harness.artifact_handoffs ? "artifact handoffs" : "", harness.hidden_session_sharing ? "session sharing" : ""),
    );
  }, [harnesses, searchQuery]);

  const filteredRoles = (() => {
    const query = String(searchQuery || "").trim().toLowerCase();
    if (!query) {
      return config.roles;
    }
    return config.roles.filter((role) => {
      const binding = bindingForRole(role.id);
      return matchesSearch(query, role.id, role.name, role.description, binding?.model);
    });
  })();

  const filteredExecutions = useMemo(() => {
    const query = String(searchQuery || "").trim().toLowerCase();
    if (!query) {
      return executions;
    }
    return executions.filter((item) =>
      matchesSearch(
        query,
        item.request_id,
        item.requested_role,
        item.assigned_model,
        item.provider,
        item.actual_model,
        item.fallback_trigger,
        item.error,
      ),
    );
  }, [executions, searchQuery]);

  function roleBindingsFor(roleId) {
    return config.bindings
      .filter((binding) => binding.role === roleId)
      .slice()
      .sort((left, right) => {
        const leftDefault = Object.keys(left.selectors || {}).length === 0;
        const rightDefault = Object.keys(right.selectors || {}).length === 0;
        if (leftDefault !== rightDefault) {
          return leftDefault ? -1 : 1;
        }
        return String(left.id || "").localeCompare(String(right.id || ""));
      });
  }

  function bindingForRole(roleId) {
    return roleBindingsFor(roleId).find(
      (binding) => Object.keys(binding.selectors || {}).length === 0,
    );
  }

  function updateBinding(bindingId, patch) {
    setConfig((current) => {
      const nextId = typeof patch.id === "string" ? patch.id.trim() : bindingId;
      if (Object.prototype.hasOwnProperty.call(patch, "id")) {
        if (!nextId) {
          setError("Binding id cannot be empty");
          return current;
        }
        if (nextId !== bindingId && current.bindings.some((binding) => binding.id === nextId)) {
          setError("Binding " + nextId + " already exists");
          return current;
        }
      }
      return {
        ...current,
        bindings: current.bindings.map((binding) =>
          binding.id === bindingId ? { ...binding, ...patch, ...(Object.prototype.hasOwnProperty.call(patch, "id") ? { id: nextId } : {}) } : binding,
        ),
      };
    });
  }

  function removeBinding(bindingId) {
    setConfig((current) => ({
      ...current,
      bindings: current.bindings.filter((binding) => binding.id !== bindingId),
    }));
  }

  function addBinding(roleId, draft) {
    const nextId = String(draft.bindingId || "").trim();
    const nextModel = String(draft.model || "").trim();
    const nextSelectors = draft.selectors && typeof draft.selectors === "object" ? draft.selectors : {};
    if (!nextId || !nextModel || !Object.keys(nextSelectors).length) {
      return;
    }
    if (config.bindings.some((binding) => binding.id === nextId)) {
      setError("Binding " + nextId + " already exists");
      return;
    }
    setConfig((current) => ({
      ...current,
      bindings: [
        ...current.bindings,
        {
          id: nextId,
          role: roleId,
          model: nextModel,
          selectors: nextSelectors,
          fallback_chain: [],
          equivalent_deployments: [],
          required_capabilities: [],
          enabled: draft.enabled !== false,
        },
      ],
    }));
  }

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

  async function removeCredential(account) {
    const accountName = account.display_name || account.id;
    if (!window.confirm(`Remove the saved credential for ${accountName}? This cannot be undone.`)) {
      return;
    }

    setRemovingCredentialId(account.id);
    setError(null);
    try {
      await orchestrationApi(`/providers/${account.id}/credential`, { method: "DELETE" });
      await load();
      setNotice(`Credential removed for ${accountName}`);
    } catch (err) {
      setError(err?.message || "Unable to remove provider credential");
    } finally {
      setRemovingCredentialId(null);
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
            {filteredAccounts.length ? (
              filteredAccounts.map((account) => (
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
                    {account.auth_method !== "none" && account.credential_configured ? (
                      <button
                        className="ghost-button danger-button"
                        onClick={() => removeCredential(account)}
                        disabled={removingCredentialId === account.id}
                        type="button"
                      >
                        <Trash2 size={13} /> {removingCredentialId === account.id ? "Removing…" : "Remove credential"}
                      </button>
                    ) : null}
                  </div>
                </article>
              ))
            ) : (
              <p className="text-secondary">No provider accounts match your search.</p>
            )}
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

      {tab === "harnesses" ? (
        <div className="orchestration-pane">
          <div className="section-heading">
            <div>
              <h3>Harness compatibility</h3>
              <p className="text-secondary">Model deployment availability is verified separately.</p>
            </div>
          </div>
          {!harnessManifestAvailable ? (
            <p className="text-secondary">Harness compatibility is unavailable.</p>
          ) : !harnesses.length ? (
            <p className="text-secondary">No harness contracts are configured.</p>
          ) : (
            <div className="orchestration-card-grid">
              {filteredHarnesses.map((harness) => (
                <article className="orchestration-card" key={harness.id}>
                  <span className="status-pill">{displayLabel(harness.support_level)}</span>
                  <h3>{displayLabel(harness.id)}</h3>
                  <p>{harness.routing ? "Routing supported" : "Routing unavailable"}</p>
                  <p>{harness.artifact_handoffs ? "Artifact handoffs supported" : "Artifact handoffs unavailable"}</p>
                  <p>{harness.hidden_session_sharing ? "Session sharing enabled" : "Session sharing isolated"}</p>
                  <p className="text-secondary">{harness.notes}</p>
                </article>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {tab === "roles" ? (
        <div className="orchestration-pane">
          <div className="orchestration-role-list">
            {filteredRoles.length === 0 ? (
              <div className="orchestration-empty-state">
                <strong>No roles yet</strong>
                <span>
                  Roles bind a workload (planner, implementer, reviewer) to an
                  approved provider and model. Add your first role below to
                  start locking assignments.
                </span>
              </div>
            ) : null}
            {filteredRoles.map((role) => {
              const binding = bindingForRole(role.id);
              const bindings = roleBindingsFor(role.id);
              return (
                <article key={role.id} className="orchestration-role-card">
                  <div className="orchestration-role-row">
                    <div>
                      <strong>{role.name}</strong>
                      <span>{role.description || "Custom role"}</span>
                    </div>
                    <select value={binding?.model || ""} onChange={(event) => updateRoleModel(role.id, event.target.value)} aria-label={"Model for " + role.name}>
                      <option value="">Unassigned</option>
                      {models.map((model) => {
                        const deploymentKey = modelDeploymentKey(model);
                        return <option value={deploymentKey} key={deploymentKey} disabled={model.executable === false}>{model.display_name || model.key} · {model.account_id || model.provider}{model.executable === false ? " · unavailable" : ""}</option>;
                      })}
                    </select>
                    <span className={binding ? "role-state assigned" : "role-state"}>{binding ? "Locked" : "Needs assignment"}</span>
                  </div>
                  <div className="orchestration-role-summary text-secondary">
                    {bindings.length ? bindings.length + " binding" + (bindings.length === 1 ? "" : "s") + " total" : "No bindings configured"}
                  </div>
                  <RoleBindingEditor
                    role={role}
                    bindings={bindings}
                    models={models}
                    onCreateBinding={addBinding}
                    onUpdateBinding={updateBinding}
                    onDeleteBinding={removeBinding}
                  />
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
          <label><span>Deployment cooldown (seconds)</span><input type="number" min="1" max="3600" value={config.settings.deployment_cooldown_seconds ?? 30} onChange={(event) => setConfig({ ...config, settings: { ...config.settings, deployment_cooldown_seconds: Number(event.target.value) } })} /></label>
          <div className="route-preview">
            <h3>Deterministic route preview</h3>
            <div className="orchestration-inline-form">
              <select value={previewRole} onChange={(event) => setPreviewRole(event.target.value)}><option value="">Select role</option>{config.roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select>
              <button className="ghost-button" onClick={runPreview} disabled={!previewRole} type="button">Preview</button>
            </div>
            {preview ? (
              <div className="route-preview-result">
                <strong>{preview.provider}:{preview.actual_model}</strong>
                <span>{preview.reason}</span>
                <span>{preview.fallback_used ? `Fallback from ${preview.fallback_from}` : "Assigned model enforced"}</span>
                {Array.isArray(preview.required_capabilities) && preview.required_capabilities.length ? (
                  <section className="route-preview-evidence">
                    <h4>Required capabilities</h4>
                    <div className="capability-list">
                      {preview.required_capabilities.map((capability) => <span key={capability}>{capability}</span>)}
                    </div>
                  </section>
                ) : null}
                {Array.isArray(preview.policy_constraints?.allowed_providers) && preview.policy_constraints.allowed_providers.length ? (
                  <span>Provider policy: {preview.policy_constraints.allowed_providers.join(", ")}</span>
                ) : null}
                {preview.selection_evidence?.strategy === "equivalent_weighted" ? (
                  <section className="route-preview-evidence">
                    <h4>Weighted allocation</h4>
                    <span>Cohort {Number(preview.selection_evidence.cohort_fraction).toFixed(2)}</span>
                    <ul>
                      {(preview.selection_evidence.eligible_weights || []).map((candidate) => (
                        <li key={candidate.deployment}>
                          <span>{candidate.deployment}</span>
                          <span>Weight {Number(candidate.weight).toFixed(2)}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}
                {Array.isArray(preview.selection_evidence?.scores) && preview.selection_evidence.scores.length ? (
                  <section className="route-preview-evidence">
                    <h4>Candidate scores</h4>
                    <ul>
                      {preview.selection_evidence.scores.map((candidate) => (
                        <li key={candidate.deployment}>
                          <span>{candidate.deployment}</span>
                          <span>Score {Number(candidate.score).toFixed(2)}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}
                {Array.isArray(preview.selection_evidence?.rejected) && preview.selection_evidence.rejected.length ? (
                  <section className="route-preview-evidence">
                    <h4>Rejected candidates</h4>
                    <ul>
                      {preview.selection_evidence.rejected.map((candidate) => (
                        <li key={`${candidate.model}:${candidate.reason}`}>
                          <span>{candidate.model}</span>
                          <span>{candidate.reason}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {tab === "activity" ? (
        <div className="orchestration-pane orchestration-table-wrap">
          <table className="orchestration-table"><thead><tr><th>Role</th><th>Assigned</th><th>Actual</th><th>Latency</th><th>Fallback</th><th>Result</th></tr></thead><tbody>{filteredExecutions.map((item) => <tr key={`${item.request_id}-${item.started_at}`}><td>{item.requested_role || "Manual"}</td><td>{item.assigned_model || "—"}</td><td>{item.provider}:{item.actual_model}</td><td>{Math.round(item.latency_ms || 0)} ms</td><td>{item.fallback_used ? item.fallback_trigger : "No"}</td><td>{item.error || "Success"}</td></tr>)}</tbody></table>
          {!executions.length ? <p className="text-secondary">No orchestrated executions recorded yet.</p> : null}
        </div>
      ) : null}
    </section>
  );
}
