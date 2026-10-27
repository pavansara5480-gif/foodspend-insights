import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MealControls, { DEFAULT_CONTROLS } from '../components/MealControls';
import Plot from '../components/Plot';
import { AsyncBlock, Card, Confidence, Disclaimer, Kpi, LabelBadge } from '../components/ui';
import { useApi, useDebounced } from '../hooks/useApi';
import { NUTRIENTS, inr, num, nutrientLabel, nutrientUnit, signed } from '../utils/format';
import { SERIES } from '../utils/palette';

export default function Recommend() {
  const [c, setC] = useState(DEFAULT_CONTROLS);
  const [w, setW] = useState({ goal: 0.5, pref: 0.3, cost: 0.2 });
  const params = useDebounced({ meal_type: c.meal_type, goal: c.goal, budget: c.budget, target: c.target, source: c.source,
    w_goal: w.goal, w_pref: w.pref, w_cost: w.cost }, 300);
  const state = useApi('/recommendations/next-meal/', params);
  const goalInfo = state.data?.context?.goal;
  return (
    <>
      <h1 className="page-title">Next-meal recommendation</h1>
      <p className="page-lead">
        Chooses from the dataset’s meal options using a transparent weighted score of goal progress, explicit
        preference and cost. Every control recalculates on the server.
      </p>
      <MealControls value={c} onChange={setC} goalInfo={goalInfo} />
      <details className="mb-3">
        <summary className="small text-primary">Ranking weights: goal {w.goal} · preference {w.pref} · cost {w.cost} (adjust)</summary>
        <div className="row g-3 mt-1">
          {[['goal', 'Goal progress'], ['pref', 'Preference'], ['cost', 'Cost']].map(([k, l]) => (
            <div className="col-md-4" key={k}>
              <label className="form-label small mb-0" htmlFor={`w-${k}`}>{l}: {w[k]}</label>
              <input id={`w-${k}`} type="range" className="form-range" min="0" max="1" step="0.05" value={w[k]}
                onChange={(e) => setW({ ...w, [k]: Number(e.target.value) })} />
            </div>
          ))}
          <div className="small text-secondary">Weights are re-normalised to sum to 1 on the server.</div>
        </div>
      </details>
      <AsyncBlock state={state}>{(d) => <Body d={d} controls={c} />}</AsyncBlock>
    </>
  );
}

function Body({ d, controls }) {
  const navigate = useNavigate();
  const ctx = d.context;
  const rec = d.recommended;
  const gk = ctx.goal.nutrient;
  const gUnit = nutrientUnit(gk);
  if (!rec) {
    return (
      <Card title="No recommendation">
        <p>{d.message}</p>
        <p className="small text-secondary mb-0">Nothing is invented when the constraints cannot be met. Increase the budget or change the source.</p>
      </Card>
    );
  }
  const options = [{ ...rec, title: 'Recommended' }, ...d.alternatives];
  const openWhatIf = (lines) => navigate('/what-if', { state: { baseline: lines, controls } });
  return (
    <>
      <div className="row g-3 mb-3">
        <div className="col-lg-7">
          <Card className="rec-card">
            <div className="alt-type">Recommended {ctx.meal_type} · goal: {ctx.goal.goal_name}</div>
            <div className="rec-name mb-2">{rec.name}</div>
            <div className="row g-2 mb-3">
              <div className="col-6 col-md-3"><Kpi label="Estimated cost" value={inr(rec.cost.total, 2)} hint={`Items ${inr(rec.cost.items_subtotal, 2)} + tax/fees ${inr(rec.cost.tax + rec.cost.fees, 2)}`} /></div>
              <div className="col-6 col-md-3"><Kpi label="Budget remaining" value={inr(rec.budget.remaining, 2)} hint={`${num(rec.budget.utilization_pct)}% of ₹${ctx.budget} used`} /></div>
              <div className="col-6 col-md-3"><Kpi label={`${nutrientLabel(gk)} (goal)`} value={`${num(rec.goal_contribution.amount)} ${gUnit}`}
                hint={`${num(rec.goal_contribution.pct_of_meal_target)}% of ${ctx.meal_type} target ${num(ctx.meal_target)} ${gUnit}`} /></div>
              <div className="col-6 col-md-3"><Kpi label="Calories" value={`${num(rec.nutrients.calories_kcal, 0)} kcal`} hint={`Allowance ${ctx.kcal_allowance} kcal`} /></div>
            </div>
            <div className="table-responsive">
              <table className="table table-sm">
                <thead><tr><th>Item</th><th className="num">Serving</th><th className="num">Price</th>
                  {NUTRIENTS.map((n) => <th key={n.key} className="num">{n.label} ({n.unit})</th>)}<th>Preference evidence</th></tr></thead>
                <tbody>
                  {rec.items.map((it) => (
                    <tr key={it.food_id}>
                      <td>{it.food_name}<div className="small text-secondary">{it.vendor}</div></td>
                      <td className="num">{it.servings} × = {num(it.amount, 0)} {it.unit}</td>
                      <td className="num">{inr(it.price_per_serving * it.servings, 2)}</td>
                      {NUTRIENTS.map((n) => <td key={n.key} className="num">{it.nutrients[n.key] == null ? 'unknown' : num(it.nutrients[n.key])}</td>)}
                      <td className="small"><LabelBadge label={it.preference.latest_label} />{' '}
                        {it.preference.n_ratings ? `${num(it.preference.mean_rating)}/5 (${it.preference.n_ratings})` : 'no ratings'}</td>
                    </tr>
                  ))}
                  <tr className="fw-semibold"><td>Total</td><td /><td className="num">{inr(rec.cost.items_subtotal, 2)}</td>
                    {NUTRIENTS.map((n) => <td key={n.key} className="num">{num(rec.nutrients[n.key])}</td>)}<td /></tr>
                  <tr className="small text-secondary"><td colSpan={3}>Range if servings vary ±15%</td>
                    {NUTRIENTS.map((n) => <td key={n.key} className="num">{num(rec.nutrient_range[n.key][0], 0)}–{num(rec.nutrient_range[n.key][1], 0)}</td>)}<td /></tr>
                </tbody>
              </table>
            </div>
            <div className="d-flex flex-wrap gap-2 align-items-start justify-content-between">
              <Confidence confidence={rec.confidence} />
              <button className="btn btn-sm btn-outline-primary" onClick={() => openWhatIf(rec.lines)}>Modify in what-if simulator →</button>
            </div>
          </Card>
        </div>
        <div className="col-lg-5">
          <Card title="Why this meal">
            <ol className="reason-list small ps-3">{rec.reasons.map((r) => <li key={r}>{r}</li>)}</ol>
            <div className="small mb-2">
              <strong>Score:</strong> {num(rec.scores.total, 3)} = {ctx.weights.goal} × goal {num(rec.scores.goal, 3)} + {ctx.weights.preference} × preference {num(rec.scores.preference, 3)} + {ctx.weights.cost} × cost {num(rec.scores.cost, 3)}
            </div>
            {d.excluded_by_feedback.length > 0 && (
              <div className="small mb-2"><strong>Excluded by feedback:</strong>{' '}
                {d.excluded_by_feedback.map((e) => `${e.food_name} (${e.latest_label}, ${e.latest_feedback_date})`).join('; ')}</div>
            )}
            <div className="small text-secondary mb-2">{d.feasible_candidates} feasible of {d.candidates_evaluated} candidates; {d.over_budget_candidates} over budget. {ctx.availability_note} {ctx.price_note}</div>
            <Disclaimer text={d.disclaimer} />
          </Card>
        </div>
      </div>

      <h2 className="h5 mt-4">Alternatives and trade-offs</h2>
      <div className="row g-3 mb-3">
        {d.alternatives.map((a) => (
          <div className="col-md-6 col-xl-3" key={a.alternative_type}>
            <Card>
              <div className="alt-type">{a.title}</div>
              <div className="fw-semibold mb-1">{a.name}</div>
              <div className="small text-secondary mb-2">{a.why}</div>
              <table className="table table-sm mb-2">
                <tbody>
                  <tr><td>Cost</td><td className="num">{inr(a.cost.total, 2)}</td><td className="num small">{signed(a.tradeoff.cost_difference, 2, '')}</td></tr>
                  <tr><td>{nutrientLabel(gk)}</td><td className="num">{num(a.nutrients[gk])} {gUnit}</td><td className="num small">{signed(a.tradeoff.goal_nutrient_difference)}</td></tr>
                  <tr><td>Calories</td><td className="num">{num(a.nutrients.calories_kcal, 0)}</td><td className="num small">{signed(a.tradeoff.calorie_difference, 0)}</td></tr>
                  <tr><td>Preference score</td><td className="num">{num(a.scores.preference, 2)}</td><td className="num small">{signed(a.tradeoff.preference_score_difference, 2)}</td></tr>
                  <tr><td>Total score</td><td className="num">{num(a.scores.total, 3)}</td><td className="num small">{signed(a.tradeoff.total_score_difference, 3)}</td></tr>
                </tbody>
              </table>
              <div className="small text-secondary mb-2">Differences are vs the recommendation.</div>
              <button className="btn btn-sm btn-outline-secondary" onClick={() => openWhatIf(a.lines)}>Simulate</button>
            </Card>
          </div>
        ))}
      </div>

      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <Card>
            <Plot title={`${nutrientLabel(gk)} per option (${gUnit})`} subtitle={`Dashed line: ${ctx.meal_type} share of the daily target (${num(ctx.meal_target)} ${gUnit})`}
              height={300}
              data={[{ type: 'bar', x: options.map((o) => o.title), y: options.map((o) => o.nutrients[gk]), marker: { color: SERIES[0] },
                text: options.map((o) => o.name), textposition: 'none', hovertemplate: `%{text}<br>%{y:.1f} ${gUnit}<extra></extra>` }]}
              layout={{ yaxis: { title: { text: gUnit } }, xaxis: { tickangle: 0 },
                shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: ctx.meal_target, y1: ctx.meal_target, line: { dash: 'dash', color: '#898781', width: 1.5 } }] }} />
          </Card>
        </div>
        <div className="col-lg-6">
          <Card>
            <Plot title="Estimated cost per option (₹)" subtitle={`Dashed line: budget ₹${ctx.budget}`} height={300}
              data={[{ type: 'bar', x: options.map((o) => o.title), y: options.map((o) => o.cost.total), marker: { color: SERIES[1] },
                text: options.map((o) => o.name), textposition: 'none', hovertemplate: '%{text}<br>₹%{y:.2f}<extra></extra>' }]}
              layout={{ yaxis: { title: { text: '₹' }, tickprefix: '₹' },
                shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: ctx.budget, y1: ctx.budget, line: { dash: 'dash', color: '#898781', width: 1.5 } }] }} />
          </Card>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-7">
          <Card title="Top-ranked candidates" subtitle="Tie-break: total score, then preference, then lower cost, then name">
            <div className="table-responsive">
              <table className="table table-sm table-hover">
                <thead><tr><th>#</th><th>Meal</th><th className="num">Cost</th><th className="num">{nutrientLabel(gk)}</th><th className="num">kcal</th>
                  <th className="num">Goal</th><th className="num">Pref.</th><th className="num">Cost sc.</th><th className="num">Total</th></tr></thead>
                <tbody>
                  {d.ranking.map((r) => (
                    <tr key={r.rank}><td>{r.rank}</td><td>{r.name}</td><td className="num">{inr(r.cost_inr, 2)}</td><td className="num">{num(r.goal_amount)}</td>
                      <td className="num">{num(r.calories, 0)}</td><td className="num">{num(r.goal_score, 3)}</td><td className="num">{num(r.preference_score, 3)}</td>
                      <td className="num">{num(r.cost_score, 3)}</td><td className="num fw-semibold">{num(r.total_score, 3)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
        <div className="col-lg-5">
          <Card title="Method (rule-based, no machine learning)">
            <dl className="small mb-0">
              {Object.entries(d.method.formulas).map(([k, v]) => (
                <div key={k} className="mb-1"><dt className="d-inline">{k.replace(/_/g, ' ')}: </dt><dd className="d-inline mono">{v}</dd></div>
              ))}
              <div className="mt-2"><dt className="d-inline">Constraints: </dt><dd className="d-inline">{d.method.constraints.join('; ')}</dd></div>
              <div><dt className="d-inline">Goal source: </dt><dd className="d-inline">{ctx.goal.reference_source}{ctx.goal.target_overridden ? ` (target overridden to ${ctx.goal.daily_target})` : ''}</dd></div>
            </dl>
          </Card>
        </div>
      </div>
    </>
  );
}
