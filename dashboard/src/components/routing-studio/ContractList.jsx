import { FileCode2, Plus } from "lucide-react";

export default function ContractList({ contracts, selected, onSelect, onNew }) {
  return (
    <aside className="contract-list" aria-label="Workload contracts">
      <div className="contract-list-heading">
        <div>
          <span className="eyebrow">Versioned intent</span>
          <h3>Contracts</h3>
        </div>
        <button
          className="primary-button compact-button"
          type="button"
          onClick={onNew}
        >
          <Plus size={14} /> New contract
        </button>
      </div>
      {contracts.length ? (
        <div className="contract-list-items">
          {contracts.map((contract) => (
            <button
              className={
                selected?.id === contract.id &&
                selected?.version === contract.version
                  ? "active"
                  : ""
              }
              key={`${contract.id}:${contract.version}`}
              onClick={() => onSelect(contract)}
              type="button"
            >
              <FileCode2 size={16} />
              <span>
                <strong>{contract.name}</strong>
                <small>
                  v{contract.version} · {contract.state}
                </small>
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className="routing-empty-state">
          <FileCode2 size={22} />
          <strong>No contracts yet</strong>
          <span>
            Start with a coding-agent template, then preview it before saving.
          </span>
        </div>
      )}
    </aside>
  );
}
