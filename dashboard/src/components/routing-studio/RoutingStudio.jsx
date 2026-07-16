import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart3, FileCode2, FlaskConical, Rocket } from "lucide-react";
import {
  getContractEvidence,
  listContracts,
  pauseContract,
  promoteContract,
  rollbackContract,
  saveDraft,
  shadowContract,
  simulateDraft,
} from "./api";
import ContractEditor from "./ContractEditor";
import ContractList from "./ContractList";
import EvidencePanel from "./EvidencePanel";
import RouteSimulator from "./RouteSimulator";
import RolloutPanel from "./RolloutPanel";

const WORKSPACES = ["contracts", "simulator", "rollouts", "evidence"];
const TABS = [
  ["contracts", "Contracts", FileCode2],
  ["simulator", "Simulator", FlaskConical],
  ["rollouts", "Rollouts", Rocket],
  ["evidence", "Evidence", BarChart3],
];

function newDraft() {
  return {
    id: "implementation",
    name: "Implementation",
    version: "2",
    state: "draft",
    template: "implementation",
    description: "Production coding and implementation tasks",
    role_aliases: ["implementation", "worker"],
    selectors: {},
    task_types: ["implementation"],
    baseline_model: "anthropic:sonnet",
    fallback_models: ["openai:gpt-5.4-mini"],
    requirements: {
      required_capabilities: ["reasoning", "tool_calling"],
      allowed_providers: [],
      allowed_accounts: [],
      allowed_regions: [],
      allowed_data_classifications: [],
    },
    objective: {
      type: "highest_quality_within_budget",
      quality_floor: 0.9,
      maximum_cost_usd: 1,
      maximum_total_latency_ms: 120000,
      weights: {},
    },
    reliability: {
      connect_timeout_seconds: 10,
      first_token_timeout_seconds: 30,
      attempt_timeout_seconds: 30,
      stream_idle_timeout_seconds: 30,
      total_deadline_seconds: 120,
      attempts_per_deployment: 2,
      maximum_deployments: 2,
      fallback_triggers: ["timeout", "provider_outage"],
      maximum_fallback_cost_usd: 1,
    },
    evaluation: {
      accepted_outcome_signals: ["verified", "review_accepted"],
      minimum_samples: 20,
      unsafe_quality_floor: 0.8,
      maximum_unsafe_rate: 0.01,
      canary_percentage: 0.1,
      automatic_rollback_conditions: {},
    },
  };
}

export default function RoutingStudio() {
  const [workspace, setWorkspace] = useState("contracts");
  const [contracts, setContracts] = useState([]);
  const [revision, setRevision] = useState(0);
  const [draft, setDraft] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const loadToken = useRef(0);
  const loadAbortController = useRef(null);

  const loadContracts = useCallback(() => {
    loadAbortController.current?.abort();
    const controller = new AbortController();
    const token = ++loadToken.current;
    loadAbortController.current = controller;
    setLoading(true);
    setLoadError(null);
    listContracts({ signal: controller.signal })
      .then((payload) => {
        if (token !== loadToken.current) {
          return;
        }
        setContracts(payload.contracts || []);
        setRevision(payload.revision || 0);
        setDraft((current) => current || payload.contracts?.[0] || null);
        setLoadError(null);
      })
      .catch((err) => {
        if (token === loadToken.current && !controller.signal.aborted) {
          setLoadError(err.message || "Routing Studio unavailable");
        }
      })
      .finally(() => {
        if (token === loadToken.current) {
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) {
        loadContracts();
      }
    });
    return () => {
      cancelled = true;
      loadToken.current += 1;
      loadAbortController.current?.abort();
    };
  }, [loadContracts]);
  useEffect(() => {
    if (!draft || draft.state === "draft") {
      return undefined;
    }
    let active = true;
    getContractEvidence(draft)
      .then((payload) => {
        if (active) {
          setEvidence(payload);
        }
      })
      .catch((err) => {
        if (active) {
          setActionError(err.message);
        }
      });
    return () => {
      active = false;
    };
  }, [draft]);
  function selectWorkspace(id, focus = false) {
    setWorkspace(id);
    if (focus) {
      window.requestAnimationFrame(() =>
        document.getElementById(`routing-tab-${id}`)?.focus(),
      );
    }
  }
  function onTabKeyDown(event, index) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? WORKSPACES.length - 1
          : (index +
              (event.key === "ArrowRight" ? 1 : -1) +
              WORKSPACES.length) %
            WORKSPACES.length;
    selectWorkspace(WORKSPACES[next], true);
  }
  async function persistDraft() {
    if (!draft) {
      return;
    }
    setSaving(true);
    try {
      const result = await saveDraft(draft, revision);
      setContracts((items) => {
        const index = items.findIndex(
          (item) =>
            item.id === result.contract.id &&
            item.version === result.contract.version,
        );
        return index === -1
          ? [...items, result.contract]
          : items.map((item, itemIndex) =>
              itemIndex === index ? result.contract : item,
            );
      });
      setRevision(result.revision);
      setDraft(result.contract);
      setActionError(null);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }
  async function runSimulation() {
    if (!draft) {
      return;
    }
    setRunning(true);
    try {
      setSimulation(
        await simulateDraft(draft, {
          role: draft.id,
          task_type: draft.task_types?.[0] || null,
          request_id: `studio-${Date.now()}`,
        }),
      );
      setActionError(null);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setRunning(false);
    }
  }
  async function rolloutAction(action) {
    if (!draft) {
      return;
    }
    setSaving(true);
    try {
      const operation =
        action === "shadow"
          ? shadowContract
          : action === "promote"
            ? promoteContract
          : action === "pause"
            ? pauseContract
            : rollbackContract;
      const result = await operation(draft);
      setDraft(result.contract);
      setRevision(result.revision);
      setContracts((items) =>
        items.map((item) =>
          item.id === result.contract.id && item.version === result.contract.version
            ? result.contract
            : item,
        ),
      );
      setActionError(null);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="panel routing-studio">
      <div className="section-heading routing-studio-heading">
        <div>
          <span className="eyebrow">Routing Studio</span>
          <h2>Workload contracts, before provider calls</h2>
          <p>
            Author immutable intent, inspect deterministic decisions, and
            graduate changes with measured evidence.
          </p>
        </div>
        <div className="routing-studio-posture">
          <span>Control posture</span>
          <strong>Evidence gated</strong>
        </div>
      </div>
      {actionError ? (
        <div className="alert-card" role="alert">
          {actionError}
        </div>
      ) : null}
      <div
        className="routing-workspace-tabs"
        role="tablist"
        aria-label="Routing Studio workspaces"
      >
        {TABS.map(([id, label, Icon], index) => (
          <button
            id={`routing-tab-${id}`}
            key={id}
            type="button"
            role="tab"
            aria-selected={workspace === id}
            aria-controls={`routing-panel-${id}`}
            tabIndex={workspace === id ? 0 : -1}
            onClick={() => selectWorkspace(id)}
            onKeyDown={(event) => onTabKeyDown(event, index)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
      <div
        id="routing-panel-contracts"
        role="tabpanel"
        aria-label="Contracts"
        aria-labelledby="routing-tab-contracts"
        hidden={workspace !== "contracts"}
      >
        {loading ? (
          <div className="routing-empty-state">Loading contracts…</div>
        ) : loadError ? (
          <div className="routing-empty-state" role="alert">
            <strong>{loadError}</strong>
            <button className="primary-button" type="button" onClick={loadContracts}>
              Retry
            </button>
          </div>
        ) : (
          <div className="routing-studio-grid">
            <ContractList
              contracts={contracts}
              selected={draft}
              onSelect={(contract) => {
                setDraft(contract);
                setSimulation(null);
                setEvidence(null);
              }}
              onNew={() => {
                setDraft(newDraft());
                setSimulation(null);
                setEvidence(null);
              }}
            />
            <ContractEditor
              draft={draft}
              onChange={(next) => {
                setDraft(next);
                setSimulation(null);
              }}
              onSave={persistDraft}
              saving={saving}
            />
          </div>
        )}
      </div>
      <div
        id="routing-panel-simulator"
        role="tabpanel"
        aria-label="Simulator"
        aria-labelledby="routing-tab-simulator"
        hidden={workspace !== "simulator"}
      >
        <RouteSimulator
          draft={draft}
          simulation={simulation}
          running={running}
          onRun={runSimulation}
        />
      </div>
      <div
        id="routing-panel-rollouts"
        role="tabpanel"
        aria-label="Rollouts"
        aria-labelledby="routing-tab-rollouts"
        hidden={workspace !== "rollouts"}
      >
        <RolloutPanel
          contract={draft}
          evidence={evidence}
          busy={saving}
          onAction={rolloutAction}
        />
      </div>
      <div
        id="routing-panel-evidence"
        role="tabpanel"
        aria-label="Evidence"
        aria-labelledby="routing-tab-evidence"
        hidden={workspace !== "evidence"}
      >
        <EvidencePanel contract={draft} evidence={evidence} />
      </div>
    </section>
  );
}
