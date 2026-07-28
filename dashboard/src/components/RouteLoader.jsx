export function RouteLoader({ label = 'Loading…' }) {
  return (
    <div className="route-loader" role="status" aria-live="polite" data-testid="route-loader">
      <div className="route-loader-spinner" aria-hidden="true" />
      <p className="route-loader-label">{label}</p>
    </div>
  );
}
