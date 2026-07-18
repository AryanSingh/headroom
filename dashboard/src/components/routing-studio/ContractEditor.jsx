const CAPABILITIES = ["reasoning", "tool_calling", "streaming", "vision"];

function numberValue(value) {
  return value === "" ? null : Number(value);
}

export default function ContractEditor({ draft, onChange, onSave, saving }) {
  if (!draft) {
    return (
      <div className="routing-empty-state">
        <strong>Select or create a contract</strong>
        <span>
          Contracts turn coding-agent intent into auditable routing policy.
        </span>
      </div>
    );
  }
  const update = (path, value) => {
    const [group, field] = path.split(".");
    onChange(
      field
        ? { ...draft, [group]: { ...draft[group], [field]: value } }
        : { ...draft, [group]: value },
    );
  };
  return (
    <div className="contract-editor">
      <div className="routing-subhead">
        <div>
          <span className="status-pill warning">Unsaved draft</span>
          <h3>{draft.name}</h3>
          <p>
            Version {draft.version} stays isolated until it passes simulation
            and evidence gates.
          </p>
        </div>
        <button
          className="primary-button"
          type="button"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save immutable draft"}
        </button>
      </div>
      <div className="contract-editor-grid">
        <label className="field">
          <span>Contract template</span>
          <select
            value={draft.template || "implementation"}
            onChange={(event) => update("template", event.target.value)}
          >
            <option value="implementation">Implementation</option>
            <option value="review">Code review</option>
            <option value="research">Research</option>
          </select>
        </label>
        <label className="field">
          <span>Baseline model</span>
          <input
            value={draft.baseline_model || ""}
            onChange={(event) => update("baseline_model", event.target.value)}
          />
        </label>
        <label className="field">
          <span>Objective</span>
          <select
            value={draft.objective.type}
            onChange={(event) => update("objective.type", event.target.value)}
          >
            <option value="highest_quality_within_budget">
              Highest quality within budget
            </option>
            <option value="lowest_cost_within_quality_sla">
              Lowest cost within quality SLA
            </option>
            <option value="reliability_first">Reliability first</option>
            <option value="exact_assignment">Exact assignment</option>
          </select>
        </label>
        <label className="field">
          <span>Quality floor</span>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={draft.objective.quality_floor}
            onChange={(event) =>
              update("objective.quality_floor", numberValue(event.target.value))
            }
          />
        </label>
        <label className="field">
          <span>Cost ceiling (USD)</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={draft.objective.maximum_cost_usd ?? ""}
            onChange={(event) =>
              update(
                "objective.maximum_cost_usd",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Latency target (ms)</span>
          <input
            type="number"
            min="1"
            value={draft.objective.maximum_total_latency_ms ?? ""}
            onChange={(event) =>
              update(
                "objective.maximum_total_latency_ms",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <div
          className="field field-wide"
          role="group"
          aria-label="Required capabilities"
        >
          <span>Required capabilities</span>
          <div className="routing-check-grid">
            {CAPABILITIES.map((capability) => (
              <label key={capability}>
                <input
                  type="checkbox"
                  checked={draft.requirements.required_capabilities.includes(
                    capability,
                  )}
                  onChange={(event) =>
                    update(
                      "requirements.required_capabilities",
                      event.target.checked
                        ? [
                            ...draft.requirements.required_capabilities,
                            capability,
                          ]
                        : draft.requirements.required_capabilities.filter(
                            (item) => item !== capability,
                          ),
                    )
                  }
                />{" "}
                {capability.replaceAll("_", " ")}
              </label>
            ))}
          </div>
        </div>
        <label className="field">
          <span>Allowed providers</span>
          <input
            value={draft.requirements.allowed_providers.join(", ")}
            placeholder="openai, anthropic"
            onChange={(event) =>
              update(
                "requirements.allowed_providers",
                event.target.value
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean),
              )
            }
          />
        </label>
        <label className="field">
          <span>Attempt timeout (seconds)</span>
          <input
            type="number"
            min="1"
            value={draft.reliability.attempt_timeout_seconds}
            onChange={(event) =>
              update(
                "reliability.attempt_timeout_seconds",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Total deadline (seconds)</span>
          <input
            type="number"
            min="1"
            value={draft.reliability.total_deadline_seconds}
            onChange={(event) =>
              update(
                "reliability.total_deadline_seconds",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Retry count</span>
          <input
            type="number"
            min="0"
            max="9"
            value={draft.reliability.attempts_per_deployment - 1}
            onChange={(event) =>
              update(
                "reliability.attempts_per_deployment",
                Number(event.target.value) + 1,
              )
            }
          />
        </label>
        <label className="field">
          <span>Maximum deployments</span>
          <input
            type="number"
            min="1"
            max="10"
            value={draft.reliability.maximum_deployments}
            onChange={(event) =>
              update(
                "reliability.maximum_deployments",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Evidence samples</span>
          <input
            type="number"
            min="1"
            value={draft.evaluation.minimum_samples}
            onChange={(event) =>
              update(
                "evaluation.minimum_samples",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Unsafe quality floor</span>
          <input
            aria-label="Unsafe threshold"
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={draft.evaluation.unsafe_quality_floor}
            onChange={(event) =>
              update(
                "evaluation.unsafe_quality_floor",
                numberValue(event.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Canary percentage</span>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={draft.evaluation.canary_percentage}
            onChange={(event) =>
              update(
                "evaluation.canary_percentage",
                numberValue(event.target.value),
              )
            }
          />
        </label>
      </div>
    </div>
  );
}
