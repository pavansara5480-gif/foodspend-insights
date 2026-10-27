// Date-range filter. Presets are relative to the last date in the dataset (2026-10-26), not today,
// because the history is fixed.
export const DATA_END = '2026-10-26';
export const DATA_START = '2025-10-27';

function minus(days) {
  const d = new Date(`${DATA_END}T00:00:00`);
  d.setDate(d.getDate() - days + 1);
  return d.toISOString().slice(0, 10);
}

const PRESETS = [
  ['All 365 days', '', ''],
  ['Last 90 days', minus(90), DATA_END],
  ['Last 30 days', minus(30), DATA_END],
  ['Q1 2026', '2026-01-01', '2026-03-31'],
];

export default function PeriodFilter({ value, onChange }) {
  const { start = '', end = '' } = value;
  return (
    <div className="filter-row">
      <div className="btn-group btn-group-sm flex-wrap" role="group" aria-label="Period presets">
        {PRESETS.map(([label, s, e]) => (
          <button key={label} type="button"
            className={`btn ${start === s && end === e ? 'btn-primary' : 'btn-outline-secondary'}`}
            onClick={() => onChange({ start: s, end: e })}>
            {label}
          </button>
        ))}
      </div>
      <label className="d-flex align-items-center gap-1 small">
        From
        <input type="date" className="form-control form-control-sm" min={DATA_START} max={DATA_END} value={start}
          onChange={(e) => onChange({ start: e.target.value, end })} />
      </label>
      <label className="d-flex align-items-center gap-1 small">
        To
        <input type="date" className="form-control form-control-sm" min={DATA_START} max={DATA_END} value={end}
          onChange={(e) => onChange({ start, end: e.target.value })} />
      </label>
    </div>
  );
}
