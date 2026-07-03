import { AlertTriangle, History, Search } from 'lucide-react';
import { useState } from 'react';
import { formatRelativeTime } from '../lib/format';
import { fetchDashboardJson } from '../lib/use-dashboard-data';

function replayEndpoint(sessionId) {
  return `/v1/sessions/${encodeURIComponent(sessionId)}/replay`;
}

function eventTitle(event) {
  if (event.event_type === 'policy_blocked') {
    return 'Context policy blocked request';
  }
  if (event.event_type === 'policy_redacted') {
    return 'Context policy redacted request';
  }
  return event.event_type || 'Replay event';
}

export default function Replay() {
  const [sessionId, setSessionId] = useState('');
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const events = Array.isArray(payload?.events) ? payload.events : [];

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = sessionId.trim();
    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    setPayload(null);

    try {
      setPayload(await fetchDashboardJson(replayEndpoint(trimmed)));
    } catch (replayError) {
      setError(replayError.message || String(replayError));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-stack">
      <section className="panel panel-wide">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Session replay</div>
            <h2>Inspect policy decisions for a session</h2>
          </div>
          <p>
            Replay is flag-gated with <code>CUTCTX_REPLAY=1</code> and shows structured
            context-policy block/redaction events captured by the proxy.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="feature-config-row" style={{ alignItems: 'center' }}>
          <label className="field" style={{ flex: 1, margin: 0 }}>
            <span>Session ID</span>
            <input
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              placeholder="sess-prod-123 or x-cutctx-session-id"
              aria-label="Session ID"
            />
          </label>
          <button className="primary-button" type="submit" disabled={loading || !sessionId.trim()}>
            <Search size={16} />
            {loading ? 'Loading…' : 'Load replay'}
          </button>
        </form>

        {error && (
          <div className="alert-card" role="alert" style={{ marginTop: 'var(--space-md)' }}>
            {error.includes('404')
              ? 'No replay events found for that session, or replay is disabled on the proxy.'
              : `Failed to load replay: ${error}`}
          </div>
        )}
      </section>

      <section className="panel panel-wide" aria-busy={loading}>
        <div className="section-heading">
          <div>
            <div className="eyebrow">Timeline</div>
            <h2>{payload?.session_id || 'No session loaded'}</h2>
          </div>
          <p>{events.length} event{events.length === 1 ? '' : 's'} recorded.</p>
        </div>

        {!payload && !loading && !error && (
          <div className="empty-row" style={{ padding: 'var(--space-xl)' }}>
            Enter a session id to inspect replay events.
          </div>
        )}

        {loading && (
          <div className="empty-row" style={{ padding: 'var(--space-xl)' }}>
            Loading replay timeline…
          </div>
        )}

        {payload && events.length === 0 && (
          <div className="empty-row" style={{ padding: 'var(--space-xl)' }}>
            This session has no replay events yet.
          </div>
        )}

        {events.length > 0 && (
          <div className="stack-list">
            {events.map((event, index) => (
              <article className="status-bullet" key={`${event.timestamp}-${index}`}>
                <strong>
                  <History size={14} aria-hidden="true" /> {eventTitle(event)}
                </strong>
                <p>
                  {event.timestamp ? formatRelativeTime(event.timestamp * 1000) : 'Unknown time'}
                  {' · '}
                  {event.surface || 'unknown surface'}
                  {event.request_id ? ` · ${event.request_id}` : ''}
                </p>
                {event.detail?.matched_rules?.length > 0 && (
                  <p>Rules: {event.detail.matched_rules.join(', ')}</p>
                )}
                {event.detail?.message && (
                  <p>
                    <AlertTriangle size={14} aria-hidden="true" /> {event.detail.message}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
