import { useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

function deploymentKey(model) {
  return model ? model.deployment_key || model.key || "" : "";
}

function listToCsv(values) {
  return Array.isArray(values) ? values.join(", ") : "";
}

function csvToList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function selectorsToText(selectors) {
  return Object.entries(selectors || {})
    .map(([key, value]) => key + "=" + value)
    .join("\\n");
}

function textToSelectors(text) {
  const selectors = {};
  String(text || "")
    .split("\\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const index = line.indexOf("=");
      if (index === -1) {
        return;
      }
      const key = line.slice(0, index).trim();
      const value = line.slice(index + 1).trim();
      if (key && value) {
        selectors[key] = value;
      }
    });
  return selectors;
}

function defaultSelectorKey(bindings) {
  const existing = bindings.find((binding) => Object.keys(binding.selectors || {}).length > 0);
  return existing ? Object.keys(existing.selectors || {})[0] || "workflow" : "workflow";
}

export default function RoleBindingEditor({
  role,
  bindings,
  models,
  onCreateBinding,
  onUpdateBinding,
  onDeleteBinding,
}) {
  const modelOptions = useMemo(() => {
    return models.map((model) => ({
      value: deploymentKey(model),
      label: (model.display_name || model.key) + " · " + (model.account_id || model.provider),
      disabled: model.executable === false,
    }));
  }, [models]);

  const [draft, setDraft] = useState({
    bindingId: role.id + "-selector",
    selectorKey: defaultSelectorKey(bindings),
    selectorValue: "",
    model: modelOptions[0] ? modelOptions[0].value : "",
    enabled: true,
  });

  const summary = bindings.length
    ? bindings.length + " binding" + (bindings.length === 1 ? "" : "s") + " configured"
    : "No bindings configured";

  function submitNewBinding() {
    const selectorKey = draft.selectorKey.trim();
    const selectorValue = draft.selectorValue.trim();
    const bindingId = draft.bindingId.trim();
    if (!bindingId || !selectorKey || !selectorValue || !draft.model) {
      return;
    }
    onCreateBinding(role.id, {
      bindingId,
      model: draft.model,
      selectors: { [selectorKey]: selectorValue },
      enabled: draft.enabled,
    });
    setDraft((current) => ({
      ...current,
      bindingId: role.id + "-selector",
      selectorValue: "",
      enabled: true,
    }));
  }

  return (
    <details className="orchestration-binding-editor">
      <summary>
        <span>Advanced bindings</span>
        <span>{summary}</span>
      </summary>

      <div className="orchestration-binding-editor-body">
        <p className="text-secondary">
          Use bindings for selector-based overrides, required capabilities, fallback chains, and
          equivalent deployments. The first matching binding wins deterministically.
        </p>

        {bindings.length ? (
          <div className="orchestration-binding-list">
            {bindings.map((binding) => {
              const selectorText = selectorsToText(binding.selectors);
              return (
                <article className="orchestration-binding-card" key={binding.id}>
                  <div className="orchestration-binding-header">
                    <div>
                      <strong>{binding.id}</strong>
                      <span>{Object.keys(binding.selectors || {}).length ? "Selector binding" : "Default binding"}</span>
                    </div>
                    <span className={"status-pill " + (binding.enabled === false ? "warning" : "")}>
                      {binding.enabled === false ? "Disabled" : "Enabled"}
                    </span>
                  </div>

                  <div className="orchestration-binding-grid">
                    <label>
                      <span>Binding id</span>
                      <input
                        aria-label={"Binding id for " + role.name + " " + binding.id}
                        value={binding.id}
                        onChange={(event) => onUpdateBinding(binding.id, { id: event.target.value })}
                      />
                    </label>

                    <label>
                      <span>Model</span>
                      <select
                        aria-label={role.name + " binding model " + binding.id}
                        value={binding.model || ""}
                        onChange={(event) => onUpdateBinding(binding.id, { model: event.target.value })}
                      >
                        <option value="">Unassigned</option>
                        {modelOptions.map((option) => (
                          <option key={option.value} value={option.value} disabled={option.disabled}>
                            {option.label}
                            {option.disabled ? " · unavailable" : ""}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="orchestration-binding-wide">
                      <span>Selectors</span>
                      <textarea
                        aria-label={"Selectors for " + role.name + " " + binding.id}
                        rows={3}
                        value={selectorText}
                        onChange={(event) =>
                          onUpdateBinding(binding.id, { selectors: textToSelectors(event.target.value) })
                        }
                        placeholder={"workflow=docs\\nrepository=headroom"}
                      />
                    </label>

                    <label>
                      <span>Required capabilities</span>
                      <input
                        aria-label={"Required capabilities for " + role.name + " " + binding.id}
                        value={listToCsv(binding.required_capabilities)}
                        onChange={(event) =>
                          onUpdateBinding(binding.id, {
                            required_capabilities: csvToList(event.target.value),
                          })
                        }
                        placeholder="tool_calling, reasoning"
                      />
                    </label>

                    <label>
                      <span>Fallback chain</span>
                      <input
                        aria-label={"Fallback chain for " + role.name + " " + binding.id}
                        value={listToCsv(binding.fallback_chain)}
                        onChange={(event) =>
                          onUpdateBinding(binding.id, {
                            fallback_chain: csvToList(event.target.value),
                          })
                        }
                        placeholder="openai:gpt-5.4-mini, anthropic:claude-sonnet-4"
                      />
                    </label>

                    <label>
                      <span>Equivalent deployments</span>
                      <input
                        aria-label={"Equivalent deployments for " + role.name + " " + binding.id}
                        value={listToCsv(binding.equivalent_deployments)}
                        onChange={(event) =>
                          onUpdateBinding(binding.id, {
                            equivalent_deployments: csvToList(event.target.value),
                          })
                        }
                        placeholder="openai:account-b:gpt-5.4-mini"
                      />
                    </label>

                    <label className="orchestration-binding-enabled">
                      <span>Enabled</span>
                      <input
                        aria-label={"Enabled for " + role.name + " " + binding.id}
                        type="checkbox"
                        checked={binding.enabled !== false}
                        onChange={(event) =>
                          onUpdateBinding(binding.id, { enabled: event.target.checked })
                        }
                      />
                    </label>

                    <button
                      className="ghost-button danger-button orchestration-binding-delete"
                      onClick={() => onDeleteBinding(binding.id)}
                      type="button"
                    >
                      <Trash2 size={13} /> Remove binding
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}

        <div className="orchestration-binding-create">
          <h4>Add selector binding</h4>
          <div className="orchestration-binding-grid">
            <label>
              <span>Binding id</span>
              <input
                aria-label={"New binding id for " + role.name}
                value={draft.bindingId}
                onChange={(event) => setDraft((current) => ({ ...current, bindingId: event.target.value }))}
                placeholder={role.id + "-selector"}
              />
            </label>

            <label>
              <span>Selector key</span>
              <input
                aria-label={"New selector key for " + role.name}
                value={draft.selectorKey}
                onChange={(event) => setDraft((current) => ({ ...current, selectorKey: event.target.value }))}
                placeholder="workflow"
              />
            </label>

            <label>
              <span>Selector value</span>
              <input
                aria-label={"New selector value for " + role.name}
                value={draft.selectorValue}
                onChange={(event) => setDraft((current) => ({ ...current, selectorValue: event.target.value }))}
                placeholder="docs"
              />
            </label>

            <label>
              <span>Model</span>
              <select
                aria-label={role.name + " new binding model"}
                value={draft.model}
                onChange={(event) => setDraft((current) => ({ ...current, model: event.target.value }))}
              >
                <option value="">Unassigned</option>
                {modelOptions.map((option) => (
                  <option key={option.value} value={option.value} disabled={option.disabled}>
                    {option.label}
                    {option.disabled ? " · unavailable" : ""}
                  </option>
                ))}
              </select>
            </label>

            <label className="orchestration-binding-enabled">
              <span>Enabled</span>
              <input
                aria-label={"New binding enabled for " + role.name}
                type="checkbox"
                checked={draft.enabled}
                onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
              />
            </label>

            <button
              className="primary-button"
              onClick={submitNewBinding}
              disabled={!draft.bindingId.trim() || !draft.selectorKey.trim() || !draft.selectorValue.trim() || !draft.model}
              type="button"
            >
              <Plus size={13} /> Add binding
            </button>
          </div>
        </div>
      </div>
    </details>
  );
}
