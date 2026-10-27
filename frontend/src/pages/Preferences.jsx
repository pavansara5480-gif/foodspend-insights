import { useState } from 'react';
import Plot from '../components/Plot';
import { AsyncBlock, Card, Kpi, LabelBadge } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { num } from '../utils/format';
import { MUTED, SERIES } from '../utils/palette';

export default function Preferences() {
  const state = useApi('/preferences/summary/');
  return (
    <>
      <h1 className="page-title">Food preferences</h1>
      <p className="page-lead">
        Explicit ratings (1–5) and labels from feedback. Purchase counts are shown beside them but are a separate
        signal: buying a food often does not prove liking it.
      </p>
      <AsyncBlock state={state}>{(d) => <Body d={d} reload={state.reload} />}</AsyncBlock>
    </>
  );
}

function Body({ d, reload }) {
  const rated = d.foods.filter((f) => f.n_ratings > 0).sort((a, b) => a.mean_rating - b.mean_rating);
  const groupOrder = ['Positive', 'Neutral', 'Negative', 'Negative (avoid)', 'No feedback'];
  return (
    <>
      <div className="row g-3 mb-3">
        <div className="col-6 col-md-3"><Kpi label="Feedback records" value={d.summary.feedback_records} /></div>
        <div className="col-6 col-md-3"><Kpi label="Foods rated" value={`${d.summary.foods_rated} / ${d.foods.length}`} /></div>
        <div className="col-6 col-md-3"><Kpi label="Average rating" value={`${num(d.summary.average_rating, 2)} / 5`} /></div>
        <div className="col-6 col-md-3"><Kpi label="Rating vs purchases (Spearman)" value={num(d.summary.spearman_rating_vs_purchases, 2)}
          hint="Rank correlation; not causal" /></div>
      </div>
      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <Card>
            <Plot title="Average rating by food (1–5)" subtitle="Foods with at least one explicit rating; hover for number of ratings"
              height={Math.max(360, rated.length * 18)}
              data={[{ type: 'bar', orientation: 'h', y: rated.map((f) => f.food_name), x: rated.map((f) => f.mean_rating),
                customdata: rated.map((f) => [f.n_ratings, f.latest_label]), marker: { color: SERIES[0] },
                hovertemplate: '%{y}<br>Mean %{x:.2f} from %{customdata[0]} rating(s)<br>Latest label: %{customdata[1]}<extra></extra>' }]}
              layout={{ margin: { l: 8, r: 16, t: 8, b: 40 }, xaxis: { range: [0, 5], title: { text: 'Mean rating' } } }} />
          </Card>
        </div>
        <div className="col-lg-6">
          <Card>
            <Plot title="Purchase frequency vs explicit rating" subtitle="Each dot is a food; position on one axis says nothing about the other"
              height={420}
              data={[{ type: 'scatter', mode: 'markers', x: rated.map((f) => f.purchase_events), y: rated.map((f) => f.mean_rating),
                text: rated.map((f) => f.food_name), marker: { size: 10, color: SERIES[0], line: { color: '#fcfcfb', width: 2 } },
                hovertemplate: '%{text}<br>%{x} purchases · mean rating %{y:.2f}<extra></extra>' }]}
              layout={{ xaxis: { title: { text: 'Purchase transactions (365 days)' } }, yaxis: { title: { text: 'Mean rating' }, range: [1, 5.2] },
                shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 3, y1: 3, line: { color: MUTED, dash: 'dot', width: 1 } }] }} />
            <FeedbackForm foods={d.foods} onSaved={reload} />
          </Card>
        </div>
      </div>
      <Card title="Preference table" subtitle={d.groups}>
        <div className="table-responsive">
          <table className="table table-sm table-hover">
            <thead><tr><th>Food</th><th>Category</th><th>Group</th><th>Latest label</th><th className="num">Ratings</th>
              <th className="num">Mean</th><th className="num">1★</th><th className="num">2★</th><th className="num">3★</th><th className="num">4★</th><th className="num">5★</th>
              <th className="num">Purchases</th><th className="num">Logged eaten</th></tr></thead>
            <tbody>
              {[...d.foods].sort((a, b) => groupOrder.indexOf(a.preference_group) - groupOrder.indexOf(b.preference_group)
                || (b.mean_rating || 0) - (a.mean_rating || 0)).map((f) => (
                <tr key={f.food_id}>
                  <td>{f.food_name}</td><td className="small">{f.category}</td><td className="small">{f.preference_group}</td>
                  <td><LabelBadge label={f.latest_label} /></td><td className="num">{f.n_ratings}</td><td className="num">{num(f.mean_rating, 2)}</td>
                  {[1, 2, 3, 4, 5].map((r) => <td key={r} className="num">{f[`rating_${r}`]}</td>)}
                  <td className="num">{f.purchase_events}</td><td className="num">{f.logged_eaten_events}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function FeedbackForm({ foods, onSaved }) {
  const [form, setForm] = useState({ food: foods[0]?.food_id, rating: 4, preference_label: 'liked', comment: '' });
  const [msg, setMsg] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    setMsg(null);
    try {
      await api.post('/feedback/', { ...form, rating: Number(form.rating) });
      setMsg({ ok: true, text: 'Feedback saved. Recommendations now use it.' });
      onSaved();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <form className="border-top pt-3 mt-2" onSubmit={submit}>
      <h3 className="h6">Record feedback</h3>
      <div className="row g-2">
        <div className="col-sm-6"><select className="form-select form-select-sm" aria-label="Food" value={form.food} onChange={set('food')}>
          {[...foods].sort((a, b) => a.food_name.localeCompare(b.food_name)).map((f) => <option key={f.food_id} value={f.food_id}>{f.food_name}</option>)}
        </select></div>
        <div className="col-3 col-sm-2"><select className="form-select form-select-sm" aria-label="Rating" value={form.rating} onChange={set('rating')}>
          {[5, 4, 3, 2, 1].map((r) => <option key={r} value={r}>{r}★</option>)}
        </select></div>
        <div className="col-9 col-sm-4"><select className="form-select form-select-sm" aria-label="Label" value={form.preference_label} onChange={set('preference_label')}>
          {['liked', 'acceptable', 'disliked', 'avoid'].map((l) => <option key={l} value={l}>{l}</option>)}
        </select></div>
        <div className="col-sm-9"><input className="form-control form-control-sm" placeholder="Comment (optional)" aria-label="Comment"
          maxLength={255} value={form.comment} onChange={set('comment')} /></div>
        <div className="col-sm-3 d-grid"><button className="btn btn-sm btn-primary" type="submit">Save</button></div>
      </div>
      {msg && <div className={`small mt-2 ${msg.ok ? 'text-success' : 'text-danger'}`} role="status">{msg.text}</div>}
    </form>
  );
}
