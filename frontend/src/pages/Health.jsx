import { useState } from 'react';
import Plot from '../components/Plot';
import PeriodFilter, { DATA_END } from '../components/PeriodFilter';
import { AsyncBlock, Card, Empty, StatusBadge } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { humanize, num } from '../utils/format';
import { SERIES } from '../utils/palette';

export default function Health() {
  const [period, setPeriod] = useState({ start: '', end: '' });
  const [indicator, setIndicator] = useState('weight');
  const state = useApi('/health/summary/', period);
  return (
    <>
      <h1 className="page-title">Health indicators</h1>
      <p className="page-lead">
        Simulated measurements with dates, units and documented reference ranges. Gaps are shown as gaps, never filled.
        Changes over time are associations only; they are not attributed to food choices, and status labels are not
        diagnoses.
      </p>
      <PeriodFilter value={period} onChange={setPeriod} />
      <AsyncBlock state={state}>
        {(d) => <Body d={d} indicator={indicator} setIndicator={setIndicator} reload={state.reload} />}
      </AsyncBlock>
    </>
  );
}

function Body({ d, indicator, setIndicator, reload }) {
  const series = d.series.filter((s) => s.indicator === indicator);
  const info = d.indicators.find((i) => i.indicator === indicator);
  const shapes = [];
  if (info && (info.reference_lower != null || info.reference_upper != null) && series.length) {
    const vals = series.map((s) => s.value);
    shapes.push({ type: 'rect', xref: 'paper', x0: 0, x1: 1, layer: 'below', line: { width: 0 }, fillcolor: 'rgba(12,163,12,0.08)',
      y0: info.reference_lower ?? Math.min(...vals) * 0.9, y1: info.reference_upper ?? Math.max(...vals) * 1.1 });
  }
  return (
    <>
      <div className="filter-row">
        <label className="small d-flex align-items-center gap-2">Indicator
          <select className="form-select form-select-sm" value={indicator} onChange={(e) => setIndicator(e.target.value)}>
            {d.indicators.map((i) => <option key={i.indicator} value={i.indicator}>{humanize(i.indicator)}{i.derived ? ' (derived)' : ''}</option>)}
          </select>
        </label>
      </div>
      <div className="row g-3 mb-3">
        <div className="col-lg-8">
          <Card>
            {series.length === 0 ? <Empty>No measurements of this indicator in the period.</Empty> : (
              <Plot title={`${humanize(indicator)} (${info?.unit})`}
                subtitle={info?.reference_source ? `Shaded band: reference range — ${info.reference_source}` : 'No documented reference range for this indicator'}
                data={[{ type: 'scatter', mode: 'lines+markers', x: series.map((s) => s.measurement_date), y: series.map((s) => s.value),
                  name: humanize(indicator), line: { color: SERIES[0], width: 2 }, marker: { size: 8, line: { color: '#fcfcfb', width: 2 } },
                  connectgaps: false, hovertemplate: `%{x}<br>%{y} ${info?.unit}<extra></extra>` }]}
                layout={{ shapes, yaxis: { title: { text: info?.unit } }, xaxis: { type: 'date' } }} />
            )}
            <p className="small text-secondary mb-0">
              {info?.measurements} readings, median {num(info?.median_days_between, 0)} days apart.
              {info?.derived && ' BMI = weight ÷ height² (height 172 cm). WHO notes lower action points (23) for Asian populations.'}
            </p>
          </Card>
        </div>
        <div className="col-lg-4">
          <AddMeasurement onSaved={reload} />
        </div>
      </div>
      <Card title="Indicator summary">
        <div className="table-responsive">
          <table className="table table-sm">
            <thead><tr><th>Indicator</th><th className="num">First</th><th className="num">Latest</th><th className="num">Change</th>
              <th className="num">Readings</th><th>Reference</th><th>Latest status</th></tr></thead>
            <tbody>
              {d.indicators.map((i) => (
                <tr key={i.indicator}>
                  <td>{humanize(i.indicator)}{i.derived && <span className="small text-secondary"> (derived)</span>}</td>
                  <td className="num">{num(i.first_value)} <span className="small text-secondary">{i.first_date}</span></td>
                  <td className="num">{num(i.latest_value)} {i.unit} <span className="small text-secondary">{i.latest_date}</span></td>
                  <td className="num">{i.change == null ? '—' : `${i.change > 0 ? '+' : ''}${num(i.change)}`}</td>
                  <td className="num">{i.measurements}</td>
                  <td className="small">{i.reference_source ? `${i.reference_lower ?? ''}${i.reference_lower != null ? '–' : '≤ '}${i.reference_upper ?? ''} ${i.unit}` : 'None documented'}</td>
                  <td>{i.reference_source ? <StatusBadge status={i.latest_status} /> : <span className="small text-secondary">Not assessed</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="small text-secondary mb-0">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </Card>
    </>
  );
}

function AddMeasurement({ onSaved }) {
  const [form, setForm] = useState({ indicator: 'weight', value: '', measurement_date: DATA_END, source: 'manual entry' });
  const [msg, setMsg] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/health/measurements/', { ...form, value: Number(form.value) });
      setMsg({ ok: true, text: 'Measurement saved.' });
      onSaved();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  };
  return (
    <Card title="Add a measurement" subtitle="Validated against plausible ranges; one reading per indicator per day">
      <form onSubmit={submit} className="d-grid gap-2">
        <select className="form-select form-select-sm" aria-label="Indicator" value={form.indicator} onChange={set('indicator')}>
          {['weight', 'waist_circumference', 'systolic_bp', 'diastolic_bp', 'fasting_glucose'].map((i) => <option key={i} value={i}>{humanize(i)}</option>)}
        </select>
        <input className="form-control form-control-sm" type="number" step="0.1" required placeholder="Value" aria-label="Value"
          value={form.value} onChange={set('value')} />
        <input className="form-control form-control-sm" type="date" required aria-label="Date" value={form.measurement_date}
          onChange={set('measurement_date')} />
        <button className="btn btn-sm btn-primary">Save</button>
        {msg && <div className={`small ${msg.ok ? 'text-success' : 'text-danger'}`} role="status">{msg.text}</div>}
      </form>
    </Card>
  );
}
