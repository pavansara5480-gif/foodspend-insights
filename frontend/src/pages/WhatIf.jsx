import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import MealControls, { DEFAULT_CONTROLS } from '../components/MealControls';
import Plot from '../components/Plot';
import { Card, Disclaimer, ErrorBox, Kpi, Loading } from '../components/ui';
import { useApi, useDebounced } from '../hooks/useApi';
import { api } from '../services/api';
import { NUTRIENTS, inr, num, nutrientLabel, nutrientUnit, signed } from '../utils/format';
import { SERIES } from '../utils/palette';

const SERVINGS = [0.5, 1, 1.5, 2, 2.5, 3];

export default function WhatIf() {
  const location = useLocation();
  const [controls, setControls] = useState(location.state?.controls || DEFAULT_CONTROLS);
  const [baseline, setBaseline] = useState(location.state?.baseline || null);
  const [ops, setOps] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const c = useDebounced(controls, 300);
  const foodsState = useApi('/meal-options/');

  // Without a baseline from the recommendation page, start from the current recommendation.
  useEffect(() => {
    if (baseline) return;
    api.get('/recommendations/next-meal/', { meal_type: c.meal_type, goal: c.goal, budget: c.budget })
      .then((d) => setBaseline(d.recommended ? d.recommended.lines : [{ food_id: 'F027', servings: 1 }]))
      .catch(setError);
  }, [baseline, c]);

  const run = useCallback(async (nextOps) => {
    if (!baseline) return false;
    setBusy(true);
    try {
      const body = { meal_type: c.meal_type, goal: c.goal, budget: c.budget, baseline, operations: nextOps,
        ...(c.target !== '' ? { target: Number(c.target) } : {}) };
      const r = await api.post('/scenarios/simulate/', body);
      setResult(r);
      setError(null);
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      setBusy(false);
    }
  }, [baseline, c]);

  useEffect(() => { run(ops); }, [baseline, c]); // eslint-disable-line react-hooks/exhaustive-deps

  const apply = async (op) => {
    const next = [...ops, op];
    if (await run(next)) setOps(next);
  };
  const undo = async () => { const next = ops.slice(0, -1); if (await run(next)) setOps(next); };
  const reset = async () => { if (await run([])) setOps([]); };

  const foods = useMemo(() => {
    const seen = new Map();
    (foodsState.data || []).forEach((o) => !seen.has(o.food) && seen.set(o.food, o));
    return [...seen.values()].sort((a, b) => a.food_name.localeCompare(b.food_name));
  }, [foodsState.data]);

  return (
    <>
      <h1 className="page-title">What-if simulator</h1>
      <p className="page-lead">
        Change servings, add a food, substitute or remove an item. Each change is sent to the server, which
        recalculates nutrients and cost from the reference data and compares the result with the baseline meal.
      </p>
      <MealControls value={controls} onChange={setControls} goalInfo={result?.context?.goal} showSource={false} />
      <ErrorBox error={error} />
      {!result ? <Loading /> : (
        <div className={busy ? 'is-refreshing' : ''}>
          <div className="row g-3 mb-3">
            <div className="col-lg-5">
              <Card title="Modified meal" subtitle={`Baseline: ${result.baseline.name}`}
                actions={<div className="btn-group btn-group-sm">
                  <button className="btn btn-outline-secondary" disabled={!ops.length || busy} onClick={undo}>Undo</button>
                  <button className="btn btn-outline-secondary" disabled={!ops.length || busy} onClick={reset}>Reset</button>
                </div>}>
                <ItemEditor result={result} foods={foods} apply={apply} busy={busy} />
                {ops.length > 0 && (
                  <>
                    <h3 className="h6 mt-3">Changes applied</h3>
                    <ol className="small mb-0">{result.operations_applied.map((o, i) => <li key={i}>{o}</li>)}</ol>
                  </>
                )}
                {result.warnings.length > 0 && <div className="alert alert-warning small mt-2 mb-0">{result.warnings.join('. ')}</div>}
              </Card>
            </div>
            <div className="col-lg-7"><Comparison r={result} /></div>
          </div>
          <Card title="Assumptions">
            <ul className="small">{result.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            <Disclaimer text={result.disclaimer} />
          </Card>
        </div>
      )}
    </>
  );
}

function ItemEditor({ result, foods, apply, busy }) {
  const [add, setAdd] = useState({ food_id: '', servings: 1 });
  const items = result.modified.items;
  const inMeal = new Set(items.map((i) => i.food_id));
  return (
    <>
      <div className="table-responsive">
        <table className="table table-sm align-middle">
          <thead><tr><th>Item</th><th>Servings</th><th>Substitute with</th><th /></tr></thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.food_id}>
                <td>{it.food_name}<div className="small text-secondary">{num(it.amount, 0)} {it.unit} · {inr(it.price_per_serving * it.servings, 2)}</div></td>
                <td>
                  <select className="form-select form-select-sm" aria-label={`Servings of ${it.food_name}`} disabled={busy}
                    value={it.servings} onChange={(e) => apply({ op: 'set_servings', food_id: it.food_id, servings: Number(e.target.value) })}>
                    {[...new Set([...SERVINGS, it.servings])].sort((a, b) => a - b).map((s) => <option key={s} value={s}>{s}×</option>)}
                  </select>
                </td>
                <td>
                  <select className="form-select form-select-sm" aria-label={`Substitute ${it.food_name}`} disabled={busy} value=""
                    onChange={(e) => e.target.value && apply({ op: 'substitute', food_id: it.food_id, with_food_id: e.target.value })}>
                    <option value="">Choose…</option>
                    {foods.filter((f) => !inMeal.has(f.food)).map((f) => <option key={f.food} value={f.food}>{f.food_name}</option>)}
                  </select>
                </td>
                <td><button className="btn btn-sm btn-outline-danger" disabled={busy || items.length < 2}
                  title={items.length < 2 ? 'A meal needs at least one item' : 'Remove'}
                  onClick={() => apply({ op: 'remove', food_id: it.food_id })}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="d-flex gap-2">
        <select className="form-select form-select-sm" aria-label="Food to add" value={add.food_id} onChange={(e) => setAdd({ ...add, food_id: e.target.value })}>
          <option value="">Add a food…</option>
          {foods.filter((f) => !inMeal.has(f.food)).map((f) => (
            <option key={f.food} value={f.food}>{f.food_name} ({f.role === 'pantry' ? 'pantry' : f.vendor_name}) · ₹{f.price_per_serving_inr}/serving</option>
          ))}
        </select>
        <select className="form-select form-select-sm" style={{ width: 90 }} aria-label="Servings to add" value={add.servings}
          onChange={(e) => setAdd({ ...add, servings: Number(e.target.value) })}>
          {SERVINGS.map((s) => <option key={s} value={s}>{s}×</option>)}
        </select>
        <button className="btn btn-sm btn-primary" disabled={!add.food_id || busy}
          onClick={() => { apply({ op: 'add', food_id: add.food_id, servings: add.servings }); setAdd({ food_id: '', servings: 1 }); }}>Add</button>
      </div>
    </>
  );
}

function Comparison({ r }) {
  const b = r.baseline;
  const m = r.modified;
  const ctx = r.context;
  const gk = ctx.goal.nutrient;
  const grams = NUTRIENTS.filter((n) => n.unit === 'g');
  return (
    <Card title="Baseline vs modified" subtitle={r.verdict.goal_direction}>
      <div className="row g-2 mb-3">
        <div className="col-6 col-md-3"><Kpi label="Cost" value={inr(m.cost.total, 2)} hint={`${signed(r.differences.cost, 2)} vs ${inr(b.cost.total, 2)}`} /></div>
        <div className="col-6 col-md-3"><Kpi label="Budget remaining" value={inr(m.budget.remaining, 2)}
          hint={m.budget.within_budget ? `${num(m.budget.utilization_pct)}% used` : 'Over budget'} /></div>
        <div className="col-6 col-md-3"><Kpi label={`${nutrientLabel(gk)} vs meal target`} value={`${num(m.goal_contribution.pct_of_meal_target)}%`}
          hint={`Baseline ${num(b.goal_contribution.pct_of_meal_target)}% of ${num(ctx.meal_target)} ${nutrientUnit(gk)}`} /></div>
        <div className="col-6 col-md-3"><Kpi label="Calories" value={`${num(m.nutrients.calories_kcal, 0)} kcal`}
          hint={`${signed(r.differences.nutrients.calories_kcal, 0)} · allowance ${ctx.kcal_allowance}`} /></div>
      </div>
      <Plot title="Nutrients: baseline vs modified (g)" height={260}
        data={[
          { type: 'bar', name: 'Baseline', x: grams.map((n) => n.label), y: grams.map((n) => b.nutrients[n.key]), marker: { color: SERIES[0] },
            hovertemplate: 'Baseline %{x}: %{y:.1f} g<extra></extra>' },
          { type: 'bar', name: 'Modified', x: grams.map((n) => n.label), y: grams.map((n) => m.nutrients[n.key]), marker: { color: SERIES[1] },
            hovertemplate: 'Modified %{x}: %{y:.1f} g<extra></extra>' },
        ]}
        layout={{ barmode: 'group', bargroupgap: 0.08, yaxis: { title: { text: 'grams' } }, legend: { orientation: 'h', y: 1.12 } }} />
      <div className="table-responsive">
        <table className="table table-sm mb-0">
          <thead><tr><th>Measure</th><th className="num">Baseline</th><th className="num">Modified</th><th className="num">Difference</th></tr></thead>
          <tbody>
            {NUTRIENTS.map((n) => (
              <tr key={n.key} className={n.key === gk ? 'fw-semibold' : ''}>
                <td>{n.label} ({n.unit}){n.key === gk ? ' — goal' : ''}{(m.nutrients_missing[n.key] || b.nutrients_missing[n.key]) && <span className="small text-secondary"> (some values unknown)</span>}</td>
                <td className="num">{num(b.nutrients[n.key])}</td><td className="num">{num(m.nutrients[n.key])}</td>
                <td className="num">{signed(r.differences.nutrients[n.key])}</td>
              </tr>
            ))}
            <tr><td>Cost (₹, incl. tax/fees)</td><td className="num">{num(b.cost.total, 2)}</td><td className="num">{num(m.cost.total, 2)}</td><td className="num">{signed(r.differences.cost, 2)}</td></tr>
            <tr><td>Within ₹{ctx.budget} budget</td><td className="num">{b.budget.within_budget ? 'Yes' : 'No'}</td><td className="num">{m.budget.within_budget ? 'Yes' : 'No'}</td><td /></tr>
            <tr><td>Goal progress (capped at 100%)</td><td className="num">{num(b.scores.goal_progress * 100, 0)}%</td><td className="num">{num(m.scores.goal_progress * 100, 0)}%</td><td className="num">{signed(r.differences.goal_progress_pct_points, 1, ' pts')}</td></tr>
          </tbody>
        </table>
      </div>
    </Card>
  );
}
