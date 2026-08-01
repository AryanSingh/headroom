import { useRef } from "react";
import { Gauge, Settings2, Waypoints } from "lucide-react";

const WORKSPACES = [
  ["operate", "Operate", Gauge],
  ["contracts", "Contracts", Waypoints],
  ["configuration", "Configuration", Settings2],
];

export default function OrchestratorWorkspaceTabs({ value, onChange }) {
  const tabsRef = useRef([]);

  function select(index, focus = false) {
    const [next] = WORKSPACES[index];
    onChange(next);
    if (focus) {
      window.requestAnimationFrame(() => tabsRef.current[index]?.focus());
    }
  }

  function onKeyDown(event, index) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const next = event.key === "Home"
      ? 0
      : event.key === "End"
        ? WORKSPACES.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + WORKSPACES.length) % WORKSPACES.length;
    select(next, true);
  }

  return (
    <nav className="orchestrator-workspace-nav" aria-label="Orchestrator workspace">
      <div className="orchestrator-workspace-tabs" role="tablist" aria-label="Orchestrator workspaces">
        {WORKSPACES.map(([id, label, Icon], index) => (
          <button
            aria-controls={`orchestrator-workspace-${id}`}
            aria-selected={value === id}
            className={value === id ? "active" : ""}
            id={`orchestrator-workspace-tab-${id}`}
            key={id}
            onClick={() => select(index)}
            onKeyDown={(event) => onKeyDown(event, index)}
            ref={(node) => { tabsRef.current[index] = node; }}
            role="tab"
            tabIndex={value === id ? 0 : -1}
            type="button"
          >
            <Icon aria-hidden="true" size={16} />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
