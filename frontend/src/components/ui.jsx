import { humanize } from '../utils/format';

export function Loading({ text = 'Loading…' }) {
  return (
    <div className="d-flex align-items-center gap-2 text-secondary py-4" role="status">
      <div className="spinner-border spinner-border-sm" aria-hidden="true" /> {text}
    </div>
  );
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="alert alert-danger d-flex justify-content-between align-items-start gap-3" role="alert">
      <div>
        <strong>Could not load data.</strong> {error.message}
      </div>
      {onRetry && (
        <button className="btn btn-sm btn-outline-danger" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ children = 'No data for the selected filters.' }) {
  return <div className="text-secondary fst-italic py-3">{children}</div>;
}

/** Wraps page content: shows spinner on first load, error with retry, otherwise children. */
export function AsyncBlock({ state, children }) {
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading />;
  return (
    <div className={state.loading ? 'is-refreshing' : ''} aria-busy={state.loading}>
      {children(state.data)}
    </div>
  );
}

export function Card({ title, subtitle, children, className = '', actions }) {
  return (
    <section className={`card panel ${className}`}>
      <div className="card-body">
        {(title || actions) && (
          <div className="d-flex justify-content-between align-items-start gap-2 mb-2">
            <div>
              {title && <h2 className="panel-title">{title}</h2>}
              {subtitle && <div className="panel-subtitle">{subtitle}</div>}
            </div>
            {actions}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}

export function Kpi({ label, value, hint }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

const STATUS_STYLE = {
  'Within range': { cls: 'status-good', icon: '✓' },
  'Below target': { cls: 'status-serious', icon: '↓' },
  'Above target': { cls: 'status-serious', icon: '↑' },
  'Insufficient data': { cls: 'status-muted', icon: '?' },
};

/** Status label always carries an icon and text, never colour alone. */
export function StatusBadge({ status }) {
  const s = STATUS_STYLE[status] || { cls: 'status-muted', icon: '•' };
  return (
    <span className={`status-badge ${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span> {status || 'Not assessed'}
    </span>
  );
}

export function ConsumptionBadge({ status }) {
  const map = { consumed: 'bg-success-subtle text-success-emphasis', partially_consumed: 'bg-info-subtle text-info-emphasis',
    not_consumed: 'bg-secondary-subtle text-secondary-emphasis', unknown: 'bg-warning-subtle text-warning-emphasis' };
  return <span className={`badge ${map[status] || 'bg-light text-dark'}`}>{status === 'unknown' ? 'Purchased (consumption unknown)' : humanize(status)}</span>;
}

export function LabelBadge({ label }) {
  if (!label) return <span className="badge bg-light text-secondary border">No feedback</span>;
  const map = { liked: 'bg-success-subtle text-success-emphasis', acceptable: 'bg-secondary-subtle text-secondary-emphasis',
    disliked: 'bg-danger-subtle text-danger-emphasis', avoid: 'bg-danger text-white' };
  return <span className={`badge ${map[label] || 'bg-light text-dark'}`}>{humanize(label)}</span>;
}

export function Confidence({ confidence }) {
  if (!confidence) return null;
  const cls = { High: 'status-good', Medium: 'status-warning', Low: 'status-serious' }[confidence.level];
  return (
    <details className="small">
      <summary>
        <span className={`status-badge ${cls}`}>Confidence: {confidence.level} ({confidence.score})</span>
      </summary>
      <ul className="mt-2 mb-0">
        {confidence.factors.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>
    </details>
  );
}

export function Disclaimer({ text }) {
  return (
    <p className="disclaimer small mb-0">
      <strong>Not medical advice.</strong> {text}
    </p>
  );
}
