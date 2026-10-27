import { useState } from 'react';
import PeriodFilter from '../components/PeriodFilter';
import { AsyncBlock, Card, ConsumptionBadge, Empty } from '../components/ui';
import { useApi, useDebounced } from '../hooks/useApi';
import { humanize, inr, num } from '../utils/format';

const RECORD_TYPES = ['delivery_order', 'cafe_purchase', 'grocery_purchase', 'home_meal'];

export default function History() {
  const [period, setPeriod] = useState({ start: '', end: '' });
  const [f, setF] = useState({ meal_type: '', record_type: '', category: '', consumption: '', search: '' });
  const [page, setPage] = useState(1);
  const search = useDebounced(f.search, 350);
  const state = useApi('/history/', { ...period, ...f, search, page, page_size: 25 });
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPage(1); };

  return (
    <>
      <h1 className="page-title">Food history</h1>
      <p className="page-lead">
        Every logged item over 365 days. <strong>Purchased</strong> nutrients describe what was bought;{' '}
        <strong>consumed</strong> nutrients apply the recorded portion eaten and stay empty when consumption is unknown
        (e.g. grocery purchases).
      </p>
      <PeriodFilter value={period} onChange={(p) => { setPeriod(p); setPage(1); }} />
      <div className="filter-row">
        <select className="form-select form-select-sm" aria-label="Meal type" value={f.meal_type} onChange={set('meal_type')}>
          <option value="">All meal types</option>
          {['breakfast', 'lunch', 'snack', 'dinner', 'not_applicable'].map((m) => <option key={m} value={m}>{humanize(m)}</option>)}
        </select>
        <select className="form-select form-select-sm" aria-label="Record type" value={f.record_type} onChange={set('record_type')}>
          <option value="">All record types</option>
          {RECORD_TYPES.map((m) => <option key={m} value={m}>{humanize(m)}</option>)}
        </select>
        <select className="form-select form-select-sm" aria-label="Category" value={f.category} onChange={set('category')}>
          <option value="">All categories</option>
          {(state.data?.categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="form-select form-select-sm" aria-label="Consumption" value={f.consumption} onChange={set('consumption')}>
          <option value="">Any consumption status</option>
          {['consumed', 'partially_consumed', 'not_consumed', 'unknown'].map((m) => <option key={m} value={m}>{humanize(m)}</option>)}
        </select>
        <input className="form-control form-control-sm" type="search" placeholder="Search food…" aria-label="Search food"
          value={f.search} onChange={set('search')} />
      </div>
      <AsyncBlock state={state}>
        {(d) => (
          <Card title={`${d.count.toLocaleString()} items`} subtitle={d.note}>
            {d.results.length === 0 ? <Empty /> : (
              <div className="table-responsive">
                <table className="table table-sm table-hover">
                  <thead>
                    <tr>
                      <th>Date / time</th><th>Meal</th><th>Food</th><th>Source</th><th className="num">Qty × serving</th>
                      <th className="num">Line total</th><th>Status</th><th className="num">kcal bought</th>
                      <th className="num">kcal eaten</th><th className="num">Protein eaten (g)</th><th className="num">Fibre eaten (g)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.results.map((r) => (
                      <tr key={r.order_item_id}>
                        <td className="text-nowrap">{r.order_datetime.replace('T', ' ')}</td>
                        <td>{humanize(r.meal_type)}</td>
                        <td>{r.food_name}<div className="small text-secondary">{r.category}</div></td>
                        <td className="small">{humanize(r.record_type)}<div className="text-secondary">{r.vendor_name}</div></td>
                        <td className="num">{num(r.quantity, 2)} × {num(r.serving_size, 0)} {r.serving_unit}</td>
                        <td className="num">{inr(r.line_total_inr, 2)}</td>
                        <td><ConsumptionBadge status={r.consumption_status} /></td>
                        <td className="num">{num(r.purchased_calories_kcal, 0)}</td>
                        <td className="num">{num(r.consumed_calories_kcal, 0)}</td>
                        <td className="num">{num(r.consumed_protein_g)}</td>
                        <td className="num">{r.consumed_fiber_g == null && r.consumed_calories_kcal != null ? <span title="Fibre value unknown for this food">unknown</span> : num(r.consumed_fiber_g)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <nav className="d-flex align-items-center gap-2" aria-label="Pagination">
              <button className="btn btn-sm btn-outline-secondary" disabled={d.page <= 1} onClick={() => setPage(d.page - 1)}>Previous</button>
              <span className="small">Page {d.page} of {d.pages}</span>
              <button className="btn btn-sm btn-outline-secondary" disabled={d.page >= d.pages} onClick={() => setPage(d.page + 1)}>Next</button>
            </nav>
          </Card>
        )}
      </AsyncBlock>
    </>
  );
}
