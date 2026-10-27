import { AsyncBlock, Card, Disclaimer } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { humanize, inr } from '../utils/format';

export default function Evidence() {
  const dq = useApi('/analytics/data-quality/');
  const fi = useApi('/analytics/findings/');
  return (
    <>
      <h1 className="page-title">Data quality, evidence and limitations</h1>
      <p className="page-lead">Key findings computed from the data, the cleaning and import checks, and what the analysis can and cannot claim.</p>
      <AsyncBlock state={fi}>
        {(f) => (
          <Card title="Key findings" className="mb-3">
            <ol className="mb-2">
              {f.findings.map((x) => (
                <li key={x.title} className="mb-2"><strong>{x.title}.</strong> {x.detail}
                  <div className="small text-secondary mono">{x.evidence}</div></li>
              ))}
            </ol>
            <Disclaimer text={f.disclaimer} />
          </Card>
        )}
      </AsyncBlock>
      <AsyncBlock state={dq}>{(d) => <Quality d={d} />}</AsyncBlock>
    </>
  );
}

function Quality({ d }) {
  const live = d.live_checks;
  const imp = d.import_report;
  const clean = d.cleaning_report;
  return (
    <>
      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <Card title="Synthetic-data disclosures">
            <ul className="small mb-0">{d.disclosures.map((x) => <li key={x}>{x}</li>)}</ul>
          </Card>
        </div>
        <div className="col-lg-6">
          <Card title="Calculation assumptions">
            <ul className="small mb-0">{d.assumptions.map((x) => <li key={x}>{x}</li>)}</ul>
          </Card>
        </div>
      </div>
      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <Card title="Live database checks" subtitle={`Database engine: ${live.database}`}>
            <table className="table table-sm mb-2">
              <tbody>
                {Object.entries(live.row_counts).map(([k, v]) => <tr key={k}><td>{humanize(k)}</td><td className="num">{v}</td></tr>)}
                <tr><td>Orders whose item lines differ from subtotal</td><td className="num">{live.orders_where_item_lines_differ_from_subtotal}</td></tr>
                <tr><td>Orders without items (an unmatched item was rejected)</td><td className="num">{live.orders_without_items}</td></tr>
                <tr><td>Coverage</td><td className="num">{live.coverage.first_date} to {live.coverage.last_date} ({live.coverage.days_with_records} days with records)</td></tr>
                {Object.entries(live.nutrition_unknown_values).filter(([, v]) => v).map(([k, v]) => (
                  <tr key={k}><td>Foods with unknown {k.replace('_g', '')}</td><td className="num">{v}</td></tr>))}
              </tbody>
            </table>
            <div className="alert alert-info small mb-0">
              <strong>Join duplication check:</strong> order-level total {inr(live.join_duplication_check.correct_order_level_total, 2)};
              naive item-join total {inr(live.join_duplication_check.naive_item_join_total, 2)}. {live.join_duplication_check.explanation}
            </div>
          </Card>
        </div>
        <div className="col-lg-6">
          <Card title="Import into the database" subtitle={imp ? `Last run ${imp.run_at} (${imp.database})` : 'No import report found'}>
            {imp && (
              <>
                <table className="table table-sm mb-2">
                  <thead><tr><th>Reconciliation</th><th className="num">CSV</th><th className="num">Database</th><th>Match</th></tr></thead>
                  <tbody>
                    {Object.entries(imp.reconciliation).map(([k, v]) => (
                      <tr key={k}><td>{humanize(k)}</td><td className="num">{v.csv}</td><td className="num">{v.database}</td><td>{v.match ? '✓ yes' : '✗ no'}</td></tr>
                    ))}
                  </tbody>
                </table>
                <div className="small">Rows rejected at import: {imp.rejected.length}</div>
              </>
            )}
          </Card>
        </div>
      </div>
      {clean && (
        <Card title="Cleaning checks (raw → processed)" subtitle={`${clean.rejected_total} rows rejected; see data/processed/rejected_records.csv`} className="mb-3">
          <div className="table-responsive">
            <table className="table table-sm">
              <thead><tr><th>Table</th><th>Check / action</th><th>Result</th></tr></thead>
              <tbody>
                {clean.checks.map((c, i) => (
                  <tr key={i}><td>{c.table}</td><td>{c.check}</td>
                    <td className="small mono">{Object.entries(c).filter(([k]) => !['table', 'check'].includes(k))
                      .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(', ') || 'none' : v}`).join('; ')}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 className="h6">Row counts</h3>
          <div className="table-responsive">
            <table className="table table-sm mb-0">
              <thead><tr><th>Table</th><th className="num">Raw</th><th className="num">Clean</th><th>Columns with blanks</th></tr></thead>
              <tbody>
                {Object.entries(clean.tables).map(([k, v]) => (
                  <tr key={k}><td>{k}</td><td className="num">{v.raw_rows}</td><td className="num">{v.clean_rows}</td>
                    <td className="small">{Object.entries(v.missing_values).map(([c, n]) => `${c} (${n})`).join(', ') || 'none'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <Card title="Limitations">
        <ul className="small mb-0">
          <li>All data is simulated for one fictional person; patterns demonstrate the method, not real behaviour.</li>
          <li>Logged intake covers recorded meals only; unlogged snacks or drinks are missing, so intake is likely underestimated.</li>
          <li>Grocery purchases are not assumed to be eaten; pantry consumption is only counted when logged as a meal.</li>
          <li>Nutrient values are estimates without item-level verification; fibre is unknown for two dishes.</li>
          <li>Recommendations choose among dataset options only; real-time availability and current prices are not known.</li>
          <li>Health indicators are not linked causally to food choices; reference ranges label values, they do not diagnose.</li>
          <li>Ranking weights and meal shares are documented assumptions that the user can change.</li>
        </ul>
      </Card>
    </>
  );
}
