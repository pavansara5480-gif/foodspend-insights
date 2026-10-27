import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Plot from '../components/Plot';
import PeriodFilter from '../components/PeriodFilter';
import { AsyncBlock, Card, Kpi, StatusBadge } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { humanize, inr, num, nutrientLabel } from '../utils/format';
import { SERIES } from '../utils/palette';

const RECORD_SERIES = [
  ['delivery_order', 'Delivery orders'],
  ['cafe_purchase', 'Cafe purchases'],
  ['grocery_purchase', 'Grocery purchases'],
];

export default function Dashboard() {
  const [period, setPeriod] = useState({ start: '', end: '' });
  const state = useApi('/analytics/dashboard/', period);
  return (
    <>
      <h1 className="page-title">Current status</h1>
      <p className="page-lead">
        Spending, logged nutrition, preferences and health indicators for the selected period, with today’s
        suggested next meal. Spending includes discounts, tax, delivery and platform charges.
      </p>
      <PeriodFilter value={period} onChange={setPeriod} />
      <AsyncBlock state={state}>{(d) => <DashboardBody d={d} />}</AsyncBlock>
    </>
  );
}

function DashboardBody({ d }) {
  const s = d.spending;
  const protein = d.nutrition.goals.find((g) => g.goal_key === 'protein');
  const monthly = useMemo(
    () => RECORD_SERIES.map(([key, name], i) => ({
      type: 'bar', name, x: d.monthly_spending.map((m) => m.month), y: d.monthly_spending.map((m) => m[key]),
      marker: { color: SERIES[i], line: { color: '#fcfcfb', width: 1.5 } },
      hovertemplate: `%{x}<br>${name}: ₹%{y:,.0f}<extra></extra>`,
    })),
    [d],
  );
  const cats = [...d.spending_by_category].reverse();
  const foods = [...d.top_foods].reverse();
  return (
    <>
      <div className="row g-3 mb-3">
        <div className="col-6 col-lg-3"><Kpi label="Total spending" value={inr(s.total_spending_inr)}
          hint={`${s.period_start} to ${s.period_end} (${s.period_days} days)`} /></div>
        <div className="col-6 col-lg-3"><Kpi label="Transactions" value={num(s.transactions, 0)}
          hint={`${s.food_orders} food orders + grocery runs`} /></div>
        <div className="col-6 col-lg-3"><Kpi label="Average food order value" value={inr(s.average_food_order_value_inr)}
          hint={`All transactions: ${inr(s.average_transaction_value_inr)}`} /></div>
        <div className="col-6 col-lg-3"><Kpi label="Logged protein, average per day"
          value={protein?.average_logged != null ? `${num(protein.average_logged)} g` : '—'}
          hint={protein ? `Target ${num(protein.target)} g/day · ${d.nutrition.days_logged} logged days` : ''} /></div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-lg-8">
          <Card>
            <Plot title="Monthly spending by transaction type (₹)" subtitle="Sum of order final totals; home-meal ingredient estimates excluded"
              data={monthly} layout={{ barmode: 'stack', legend: { orientation: 'h', y: -0.22, traceorder: 'normal' }, yaxis: { title: { text: '₹ per month' }, tickprefix: '₹' } }} />
          </Card>
        </div>
        <div className="col-lg-4">
          <Card title="Suggested next meal" subtitle="Lunch · protein goal · ₹350 budget (defaults)">
            {d.recommendation_preview ? (
              <>
                <div className="rec-name mb-1">{d.recommendation_preview.name}</div>
                <div className="mb-2 text-secondary small">
                  {inr(d.recommendation_preview.cost, 2)} · {num(d.recommendation_preview.nutrients.protein_g)} g protein ·{' '}
                  {num(d.recommendation_preview.nutrients.calories_kcal, 0)} kcal · confidence {d.recommendation_preview.confidence}
                </div>
                <Link to="/recommend" className="btn btn-primary btn-sm">See why and alternatives</Link>
              </>
            ) : <p>No feasible option within the default budget.</p>}
            <hr />
            <h3 className="h6">Nutrition vs documented targets</h3>
            <table className="table table-sm mb-1">
              <tbody>
                {d.nutrition.goals.map((g) => (
                  <tr key={g.goal_key}>
                    <td>{nutrientLabel(g.nutrient)}</td>
                    <td className="num">{num(g.average_logged)} / {num(g.target, 0)}</td>
                    <td><StatusBadge status={g.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="small text-secondary">Logged intake per day (meals × portion eaten); likely an underestimate.</div>
          </Card>
        </div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <Card>
            <Plot title="Spending by food category (₹)" subtitle="Item line totals; order-level charges shown separately so rows sum to the total"
              height={380} data={[{ type: 'bar', orientation: 'h', x: cats.map((c) => c.spending_inr), y: cats.map((c) => c.label),
                marker: { color: SERIES[0] }, hovertemplate: '%{y}<br>₹%{x:,.0f}<extra></extra>' }]}
              layout={{ margin: { l: 8, r: 16, t: 8, b: 40 }, xaxis: { tickprefix: '₹', title: { text: '₹' } } }} />
          </Card>
        </div>
        <div className="col-lg-6">
          <Card>
            <Plot title="Most frequently purchased foods" subtitle="Number of purchase transactions containing the food (not proof of liking)"
              height={380} data={[{ type: 'bar', orientation: 'h', x: foods.map((f) => f.purchase_events), y: foods.map((f) => f.food_name),
                marker: { color: SERIES[0] }, customdata: foods.map((f) => f.spending_inr),
                hovertemplate: '%{y}<br>%{x} purchases · ₹%{customdata:,.0f}<extra></extra>' }]}
              layout={{ margin: { l: 8, r: 16, t: 8, b: 40 }, xaxis: { title: { text: 'Purchases' } } }} />
          </Card>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-6">
          <Card title="Preference summary" subtitle={`${d.preferences.feedback_records} explicit feedback records`}>
            <div className="d-flex flex-wrap gap-3 mb-2">
              {Object.entries(d.preferences.groups).map(([g, n]) => (
                <Kpi key={g} label={g} value={n} hint="foods" />
              ))}
            </div>
            <p className="small mb-0 text-secondary">
              Average rating {num(d.preferences.average_rating, 2)}/5. Rank correlation between rating and purchase count:{' '}
              {num(d.preferences.spearman_rating_vs_purchases, 2)}; the two signals are kept separate. <Link to="/preferences">Details</Link>
            </p>
          </Card>
        </div>
        <div className="col-lg-6">
          <Card title="Health indicators (latest)" subtitle="Simulated measurements; status vs documented reference ranges, not a diagnosis">
            <table className="table table-sm mb-0">
              <thead><tr><th>Indicator</th><th className="num">Latest</th><th className="num">Change</th><th>Date</th><th>Status</th></tr></thead>
              <tbody>
                {d.health.map((h) => (
                  <tr key={h.indicator}>
                    <td>{humanize(h.indicator)}</td>
                    <td className="num">{num(h.latest_value)} {h.unit}</td>
                    <td className="num">{h.change == null ? '—' : `${h.change > 0 ? '+' : ''}${num(h.change)}`}</td>
                    <td>{h.latest_date}</td>
                    <td>{h.reference_source ? <StatusBadge status={h.latest_status} /> : <span className="small text-secondary">No reference range</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      </div>
    </>
  );
}
