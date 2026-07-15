export function PageHeader({ eyebrow, title, description, actions, status }) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <div className="page-header-title-row">
          <h1>{title}</h1>
          {status ? <div className="page-header-status">{status}</div> : null}
        </div>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </header>
  );
}
