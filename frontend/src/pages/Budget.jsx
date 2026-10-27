import { useState } from 'react';
import MealControls, { DEFAULT_CONTROLS } from '../components/MealControls';
import Plot from '../components/Plot';
import { AsyncBlock, Card, Disclaimer, Kpi } from '../components/ui';
import { useApi, useDebounced } from '../hooks/useApi';
import { inr, num, nutrientLabel, nutrientUnit } from '../utils/format';
import { MUTED, SERIES } from '../utils/palette';

export default function Budget() {
  const [c, setC] = useState({ ...DEFAULT_CONTROLS, budget: 250 });
  const p = useDebounced(c, 300);
  const params = { budget: p.budget, meal_type: p.meal_type, goal: p.goal, source: p.source, target: p.target };
  const state = useApi('/scenarios/budget/', params);
  const sens = useApi('/scenarios/sensitivity/', { meal_type: p.meal_type, goal: p.goal, source: p.source, target: p.target });
  return (
    <>
      <h1 className="page-title">Budget simulator</h1>
      <p className="page-lead">
        Set a budget for the next meal and compare the feasible options. Prices are the latest in the historical
        (synthetic) records, not current prices. Spending more does not automatically give a better nutritional result.
      </p>
      <MealControls value={c} onChange={setC} goalInfo={state.data?.context?.goal} budgetMax={1000} />
      <AsyncBlock state={state}>{(d) => <Body d={d} />}</AsyncBlock>
      <div className="mt-3">
        <AsyncBlock state={sens}>{(s) => <Sensitivity s={s} budget={p.budget} />}</AsyncBlock>
      </div>
    </>
  );
}

function Body({ d }) {
  const ctx = d.context;
  const gk = ctx.goal.nutrient;
  const unit = nutrientUnit(gk);
  const best = d.options[0];
  const all = [...d.options, ...d.nearest_over_budget];
  return (
    <>
      <div className="row g-3 mb-3">
        <div className="col-6 col-md-3"><Kpi label="Budget" value={inr(ctx.budget)} hint={`${d.feasible_count} feasible combinations, ${d.over_budget_count} over budget`} /></div>
        <div className="col-6 col-md-3"><Kpi label="Top option cost" value={best ? inr(best.cost.total, 2) : '—'} hint={best?.name} /></div>
        <div className="col-6 col-md-3"><Kpi label="Remaining" value={best ? inr(best.budget.remaining, 2) : '—'} /></div>
        <div className="col-6 col-md-3">
          <Kpi label="Budget utilisation" value={best?.budget.utilization_pct != null ? `${num(best.budget.utilization_pct)}%` : '—'}
            hint={best && <div className="progress mt-1" role="progressbar" aria-valuenow={best.budget.utilization_pct} aria-valuemin="0" aria-valuemax="100">
              <div className="progress-bar" style={{ width: `${Math.min(100, best.budget.utilization_pct || 0)}%` }} /></div>} />
        </div>
      </div>
      {!best && <div className="alert alert-warning">No option fits this budget. The cheapest candidate costs {inr(d.cheapest_candidate_cost, 2)}.</div>}
      <div className="row g-3 mb-3">
        <div className="col-lg-5">
          <Card>
            <Plot title={`Cost vs ${nutrientLabel(gk).toLowerCase()} per option`} subtitle="Filled: within budget · hollow grey: nearest over budget · dashed: budget"
              height={340}
              data={[
                { type: 'scatter', mode: 'markers', name: 'Within budget', x: d.options.map((o) => o.cost.total), y: d.options.map((o) => o.nutrients[gk]),
                  text: d.options.map((o) => o.name), marker: { size: 11, color: SERIES[0], line: { color: '#fcfcfb', width: 2 } },
                  hovertemplate: `%{text}<br>₹%{x:.2f} · %{y:.1f} ${unit}<extra></extra>` },
                { type: 'scatter', mode: 'markers', name: 'Over budget', x: d.nearest_over_budget.map((o) => o.cost.total),
                  y: d.nearest_over_budget.map((o) => o.nutrients[gk]), text: d.nearest_over_budget.map((o) => o.name),
                  marker: { size: 11, symbol: 'circle-open', color: MUTED, line: { width: 2 } },
                  hovertemplate: `%{text}<br>₹%{x:.2f} · %{y:.1f} ${unit} (over budget)<extra></extra>` },
              ]}
              layout={{ xaxis: { title: { text: 'Estimated cost (₹)' }, tickprefix: '₹' }, yaxis: { title: { text: `${nutrientLabel(gk)} (${unit})` } },
                shapes: [{ type: 'line', yref: 'paper', y0: 0, y1: 1, x0: ctx.budget, x1: ctx.budget, line: { dash: 'dash', color: MUTED, width: 1.5 } }] }} />
          </Card>
        </div>
        <div className="col-lg-7">
          <Card title="Feasible options (best per main dish)" subtitle={d.note}>
            <div className="table-responsive">
              <table className="table table-sm table-hover">
                <thead><tr><th>Option</th><th className="num">Cost</th><th className="num">Remaining</th><th className="num">Used</th>
                  <th className="num">{nutrientLabel(gk)}</th><th className="num">% meal target</th><th className="num">kcal</th>
                  <th className="num">Rating</th><th className="num">Score</th></tr></thead>
                <tbody>
                  {all.map((o) => (
                    <tr key={o.name} className={o.feasible ? '' : 'text-secondary'}>
                      <td>{o.name}{!o.feasible && <span className="badge bg-secondary-subtle text-secondary-emphasis ms-1">over budget</span>}</td>
                      <td className="num">{inr(o.cost.total, 2)}</td><td className="num">{inr(o.budget.remaining, 2)}</td>
                      <td className="num">{num(o.budget.utilization_pct)}%</td>
                      <td className="num">{num(o.nutrients[gk])}{o.goal_contribution.lower_bound_only ? '+' : ''}</td>
                      <td className="num">{num(o.goal_contribution.pct_of_meal_target)}%</td>
                      <td className="num">{num(o.nutrients.calories_kcal, 0)}</td>
                      <td className="num">{o.main_rating == null ? 'none' : num(o.main_rating)}</td>
                      <td className="num">{num(o.scores.total, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Disclaimer text={d.disclaimer} />
          </Card>
        </div>
      </div>
    </>
  );
}

function Sensitivity({ s, budget }) {
  return (
    <div className="row g-3">
      <div className="col-lg-6">
        <Card title="How the recommendation changes with budget" subtitle="Same goal and source; default weights">
          <table className="table table-sm mb-0">
            <thead><tr><th className="num">Budget</th><th>Recommended</th><th className="num">Cost</th><th className="num">Goal nutrient</th></tr></thead>
            <tbody>
              {s.by_budget.map((r) => (
                <tr key={r.budget} className={r.budget === budget ? 'fw-semibold' : ''}>
                  <td className="num">{inr(r.budget)}</td><td>{r.recommended || 'No feasible option'}</td>
                  <td className="num">{inr(r.cost, 2)}</td><td className="num">{num(r.goal_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      <div className="col-lg-6">
        <Card title="How the recommendation changes with weights" subtitle={`Budget ₹${s.context.budget}`}>
          <table className="table table-sm mb-0">
            <thead><tr><th>Preset</th><th>Weights (goal/pref/cost)</th><th>Recommended</th><th className="num">Cost</th></tr></thead>
            <tbody>
              {s.by_weights.map((r) => (
                <tr key={r.preset}><td>{r.preset}</td><td className="mono">{r.weights.goal}/{r.weights.preference}/{r.weights.cost}</td>
                  <td>{r.recommended || '—'}</td><td className="num">{inr(r.cost, 2)}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
