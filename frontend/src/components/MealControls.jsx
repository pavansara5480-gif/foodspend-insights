import { GOALS, MEALS, SOURCES, humanize } from '../utils/format';

/** Meal type, goal (with adjustable target), budget and source controls shared by the simulators. */
export default function MealControls({ value, onChange, goalInfo, showSource = true, budgetMax = 1000 }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  return (
    <div className="row g-3 align-items-end mb-3">
      <div className="col-6 col-md-2">
        <label className="form-label small mb-1" htmlFor="mc-meal">Meal</label>
        <select id="mc-meal" className="form-select form-select-sm" value={value.meal_type} onChange={(e) => set('meal_type', e.target.value)}>
          {MEALS.map((m) => <option key={m} value={m}>{humanize(m)}</option>)}
        </select>
      </div>
      <div className="col-6 col-md-3">
        <label className="form-label small mb-1" htmlFor="mc-goal">Nutrition goal</label>
        <select id="mc-goal" className="form-select form-select-sm" value={value.goal}
          onChange={(e) => onChange({ ...value, goal: e.target.value, target: '' })}>
          {GOALS.map((g) => <option key={g.key} value={g.key}>{g.label}</option>)}
        </select>
      </div>
      <div className="col-6 col-md-2">
        <label className="form-label small mb-1" htmlFor="mc-target">
          Daily target {goalInfo ? `(${goalInfo.unit})` : ''}
        </label>
        <div className="input-group input-group-sm">
          <input id="mc-target" type="number" min="1" step="any" className="form-control"
            placeholder={goalInfo ? String(goalInfo.documented_target) : ''} value={value.target}
            onChange={(e) => set('target', e.target.value)} />
          {value.target !== '' && <button className="btn btn-outline-secondary" type="button" title="Reset to documented target"
            onClick={() => set('target', '')}>↺</button>}
        </div>
      </div>
      <div className="col-12 col-md-3">
        <label className="form-label small mb-1" htmlFor="mc-budget">Budget for this meal: ₹{value.budget}</label>
        <div className="d-flex gap-2 align-items-center">
          <input id="mc-budget" type="range" className="form-range" min="0" max={budgetMax} step="10" value={value.budget}
            onChange={(e) => set('budget', Number(e.target.value))} />
          <input type="number" aria-label="Budget in rupees" className="form-control form-control-sm" style={{ width: 84 }} min="0"
            max="100000" value={value.budget} onChange={(e) => set('budget', e.target.value === '' ? 0 : Number(e.target.value))} />
        </div>
      </div>
      {showSource && (
        <div className="col-6 col-md-2">
          <label className="form-label small mb-1" htmlFor="mc-source">Meal source</label>
          <select id="mc-source" className="form-select form-select-sm" value={value.source} onChange={(e) => set('source', e.target.value)}>
            {SOURCES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </div>
      )}
    </div>
  );
}

export const DEFAULT_CONTROLS = { meal_type: 'lunch', goal: 'protein', target: '', budget: 350, source: 'any' };
