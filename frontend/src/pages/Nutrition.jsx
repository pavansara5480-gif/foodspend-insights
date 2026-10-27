import { useState } from 'react';
import Plot from '../components/Plot';
import PeriodFilter from '../components/PeriodFilter';
import { AsyncBlock, Card, Empty, Kpi, StatusBadge } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { NUTRIENTS, humanize, num, nutrientLabel } from '../utils/format';
import { INK, SERIES } from '../utils/palette';

const targetLine = (x, y, name) => ({
  type: 'scatter', mode: 'lines', x: [x[0], x[x.length - 1]], y: [y, y], name,
  line: { color: INK.muted, dash: 'dash', width: 1.5 }, hovertemplate: `${name}: %{y}<extra></extra>`,
});

export default function Nutrition() {
  const [period, setPeriod] = useState({ start: '', end: '' });
  const [freq, setFreq] = useState('M');
  const state = useApi('/analytics/nutrition/', { ...period, freq });
  return (
    <>
      <h1 className="page-title">Nutrition analysis</h1>
      <p className="page-lead">
        Estimated intake from logged meals (quantity × serving ÷ nutrition basis × portion eaten). Days without any
        logged meal are excluded, and unlogged food is not represented, so these are likely underestimates. Nutrient
        values are synthetic estimates.
      </p>
      <PeriodFilter value={period} onChange={setPeriod} />
      <div className="filter-row">
        <div className="btn-group btn-group-sm" role="group" aria-label="Trend granularity">
          {[['W', 'Weekly'], ['M', 'Monthly']].map(([k, l]) => (
            <button key={k} className={`btn ${freq === k ? 'btn-primary' : 'btn-outline-secondary'}`} onClick={() => setFreq(k)}>{l}</button>
          ))}
        </div>
      </div>
      <AsyncBlock state={state}>{(d) => <Body d={d} />}</AsyncBlock>
    </>
  );
}

function Body({ d }) {
  const s = d.summary;
  if (!d.trend.length) return <Empty>No logged meals in this period.</Empty>;
  const x = d.trend.map((t) => t.period);
  const goal = (k) => s.goals.find((g) => g.nutrient === k);
  const kcal = goal('calories_kcal');
  const prot = goal('protein_g');
  const fib = goal('fiber_g');
  const hover = (label, unit) => `%{x}<br>${label}: %{y:.1f} ${unit}/day<br>%{customdata} logged days<extra></extra>`;
  return (
    <>
      <div className="row g-3 mb-3">
        {NUTRIENTS.map((n) => (
          <div className="col-6 col-md-4 col-xl" key={n.key}>
            <Kpi label={`${n.label}, avg per logged day`} value={`${num(s.average_daily_logged[n.key])} ${n.unit}`}
              hint={goal(n.key) ? <StatusBadge status={goal(n.key).status} /> : 'No documented target'} />
          </div>
        ))}
      </div>
      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <Card>
            <Plot title={`Energy per logged day (kcal) — ${d.freq === 'W' ? 'weekly' : 'monthly'} average`}
              subtitle={`Dashed line: documented reference ${num(kcal?.target, 0)} kcal/day (ICMR-NIN 2020)`}
              data={[
                { type: 'scatter', mode: 'lines+markers', name: 'Calories', x, y: d.trend.map((t) => t.calories_kcal),
                  customdata: d.trend.map((t) => t.days_logged), line: { color: SERIES[0], width: 2 }, marker: { size: 8 },
                  hovertemplate: hover('Calories', 'kcal') },
                ...(kcal ? [targetLine(x, kcal.target, 'Reference')] : []),
              ]}
              layout={{ yaxis: { title: { text: 'kcal per day' }, rangemode: 'tozero' }, hovermode: 'x unified' }} />
          </Card>
        </div>
        <div className="col-lg-6">
          <Card>
            <Plot title="Protein and fibre per logged day (g)"
              subtitle={`Dashed lines: targets — protein ${num(prot?.target)} g, fibre ${num(fib?.target)} g`}
              data={[
                { type: 'scatter', mode: 'lines+markers', name: 'Protein', x, y: d.trend.map((t) => t.protein_g),
                  customdata: d.trend.map((t) => t.days_logged), line: { color: SERIES[0], width: 2 }, marker: { size: 8 },
                  hovertemplate: hover('Protein', 'g') },
                { type: 'scatter', mode: 'lines+markers', name: 'Fibre', x, y: d.trend.map((t) => t.fiber_g),
                  customdata: d.trend.map((t) => t.days_logged), line: { color: SERIES[1], width: 2 }, marker: { size: 8, symbol: 'square' },
                  hovertemplate: hover('Fibre', 'g') },
                ...(prot ? [{ ...targetLine(x, prot.target, 'Protein target'), line: { color: SERIES[0], dash: 'dash', width: 1 } }] : []),
                ...(fib ? [{ ...targetLine(x, fib.target, 'Fibre target'), line: { color: SERIES[1], dash: 'dot', width: 1 } }] : []),
              ]}
              layout={{ yaxis: { title: { text: 'grams per day' }, rangemode: 'tozero' }, hovermode: 'x unified' }} />
          </Card>
        </div>
      </div>
      <div className="row g-3">
        <div className="col-lg-7">
          <Card title="Comparison with documented targets" subtitle={`Average over ${s.days_logged} logged days (${s.logging_coverage_pct}% of ${s.period_days} days)`}>
            <div className="table-responsive">
              <table className="table table-sm">
                <thead><tr><th>Measure</th><th className="num">Average</th><th className="num">Target / range</th><th className="num">% of target</th><th>Status</th><th>Reference</th></tr></thead>
                <tbody>
                  {s.goals.map((g) => (
                    <tr key={g.goal_key}>
                      <td>{nutrientLabel(g.nutrient)} <span className="small text-secondary">({g.direction === 'at_least' ? 'minimum' : 'maximum'})</span></td>
                      <td className="num">{num(g.average_logged)}</td><td className="num">{num(g.target)} {g.unit}</td>
                      <td className="num">{num(g.pct_of_target)}%</td><td><StatusBadge status={g.status} /></td>
                      <td className="small text-secondary">{g.reference_source}</td>
                    </tr>
                  ))}
                  {s.energy_distribution.map((e) => (
                    <tr key={e.indicator}>
                      <td>{humanize(e.indicator.replace('_pct', ''))}</td><td className="num">{num(e.value)}%</td>
                      <td className="num">{e.lower != null ? `${e.lower}–` : '≤ '}{e.upper}%</td><td className="num">—</td>
                      <td><StatusBadge status={e.status} /></td><td className="small text-secondary">{e.reference_source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
        <div className="col-lg-5">
          <Card title="Data completeness and uncertainty">
            <ul className="small mb-0">
              <li>{s.completeness.meal_items} meal items logged; {s.completeness.meal_items_unknown_consumption} have unknown consumption and are excluded from intake.</li>
              <li>{s.completeness.meal_items_unknown_fiber} meal items are foods with <strong>unknown fibre</strong> ({s.completeness.foods_with_unknown_nutrients.join(', ')}); fibre totals are lower bounds, not zero-filled.</li>
              <li>{s.completeness.grocery_items_consumption_unknown} grocery items were purchased with unknown consumption; pantry food that was eaten is logged as separate home meals.</li>
              <li>Meal shares used for per-meal targets: {Object.entries(d.meal_shares).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(', ')}.</li>
              <li>Nutrient values are synthetic estimates; serving sizes may vary by ±15%.</li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
