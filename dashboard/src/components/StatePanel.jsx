export function StatePanel({ tone = 'neutral', icon: Icon, title, children, action, compact = false }) {
  const role = tone === 'error' ? 'alert' : 'status';

  return (
    <div className={`state-panel state-panel-${tone}${compact ? ' state-panel-compact' : ''}`} role={role}>
      {Icon ? <div className="state-panel-icon"><Icon size={20} aria-hidden="true" /></div> : null}
      <div className="state-panel-copy">
        <strong>{title}</strong>
        {children ? <div>{children}</div> : null}
      </div>
      {action ? <div className="state-panel-action">{action}</div> : null}
    </div>
  );
}
