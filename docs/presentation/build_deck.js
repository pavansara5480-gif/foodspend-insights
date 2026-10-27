// Lays out docs/FoodSpend_Insights.pptx from deck_data.json (written by docs/build_presentation.py).
// Every number on the slides comes from that JSON; nothing is typed in by hand.
const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');
const { applyTheme } = require('./apply_theme.js');

const D = JSON.parse(fs.readFileSync(path.join(__dirname, 'deck_data.json'), 'utf8'));
const OUT = path.join(__dirname, '..', 'FoodSpend_Insights.pptx');
const IMG = (f) => path.join(__dirname, 'images', f);

const THEME = {
  name: 'FoodSpend Forest',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '1B2B22', lt1: 'FFFFFF', dk2: '1F4D3A', lt2: 'EEF3EE',
    accent1: '2E7D5B', accent2: 'E07A3F', accent3: '3E6FB0', accent4: 'C9A227', accent5: '8E5A9B', accent6: '7E8A83',
    hlink: '3E6FB0', folHlink: '8E5A9B',
  },
};
const HEX = THEME.colors;
const inr = (v) => (v == null ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`);
const inr2 = (v) => (v == null ? '—' : `₹${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const n1 = (v) => (v == null ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 1 }));
const signed = (v, d = 1) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`;

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5 in
pres.title = 'FoodSpend Insights: Personalized Nutrition Analytics';
pres.author = 'FoodSpend Insights team';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------------------------------------------------------------- layouts
const footer = [
  { text: { text: 'FoodSpend Insights · synthetic data · not medical advice',
    options: { x: 0.6, y: 7.0, w: 8, h: 0.3, fontSize: 10, color: C.text2, isTextBox: true } } },
];
pres.defineSlideMaster({
  title: 'TITLE_DARK', background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.8, y: 2.2, w: 11.7, h: 1.6, fontSize: 44, bold: true, color: C.background1, valign: 'bottom', align: 'left' }, text: '' } },
    { placeholder: { options: { name: 'body', type: 'body', x: 0.8, y: 4.0, w: 11.7, h: 1.6, fontSize: 18, color: C.background2, valign: 'top' }, text: '' } },
  ],
});
pres.defineSlideMaster({
  title: 'CONTENT', background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 32, bold: true, color: C.text2, valign: 'middle' }, text: '' } },
    ...footer,
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.text2 },
});

// ---------------------------------------------------------------- helpers
let objCount = 0;
const oid = (p) => `${p}-${++objCount}`;
function card(slide, x, y, w, h, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill }, objectName: oid('card') });
}
function text(slide, t, opts) {
  slide.addText(t, { isTextBox: true, margin: 0, color: C.text1, fontSize: 14, valign: 'top', objectName: oid('text'), ...opts });
}
function stat(slide, x, y, w, value, label, color = C.accent1) {
  card(slide, x, y, w, 1.55);
  text(slide, value, { x: x + 0.25, y: y + 0.2, w: w - 0.5, h: 0.7, fontSize: 30, bold: true, color, fontFace: THEME.headFontFace });
  text(slide, label, { x: x + 0.25, y: y + 0.9, w: w - 0.5, h: 0.55, fontSize: 12, color: C.text2 });
}
function badge(slide, x, y, label) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: oid('badge') });
  text(slide, label, { x, y, w: 0.5, h: 0.5, fontSize: 14, bold: true, color: C.background1, align: 'center', valign: 'middle' });
}
const chartText = { catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', legendFontFace: '+mn-lt', dataLabelFontFace: '+mn-lt',
  titleFontFace: '+mn-lt', catAxisLabelColor: '52514E', valAxisLabelColor: '52514E', catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
  legendFontSize: 11, dataLabelFontSize: 11, titleFontSize: 14, titleColor: HEX.dk1, valGridLine: { color: 'E1E0D9', size: 0.75 },
  catGridLine: { style: 'none' } };
function content(title, section) {
  const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: section });
  s.addText(title, { placeholder: 'title' });
  return s;
}
function bullets(slide, items, opts) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
    { isTextBox: true, margin: 0, fontSize: 14, color: C.text1, valign: 'top', objectName: oid('list'), ...opts });
}
const tableHead = (cells) => cells.map((c) => ({ text: c, options: { bold: true, color: C.background1, fill: { color: C.text2 } } }));

// ---------------------------------------------------------------- 1 title
pres.addSection({ title: 'Introduction' });
let s = pres.addSlide({ masterName: 'TITLE_DARK', sectionTitle: 'Introduction' });
s.addText('FoodSpend Insights', { placeholder: 'title' });
s.addText([
  { text: 'What should I eat next, and why? Personalised nutrition analytics from 365 days of food history.', options: { breakLine: true } },
  { text: `Synthetic dataset · ${D.period[0]} to ${D.period[1]} · decision support, not medical advice`, options: { fontSize: 14 } },
], { placeholder: 'body' });

// ---------------------------------------------------------------- 2 answer up front
const best = D.rec_any.best;
const bestDel = D.rec_delivery.best;
s = content('The answer: a high-protein home lunch at ₹85', 'Introduction');
card(s, 0.6, 1.45, 6.4, 5.2, C.background2);
text(s, 'RECOMMENDED LUNCH · PROTEIN GOAL · ₹350 BUDGET', { x: 0.9, y: 1.7, w: 5.8, h: 0.35, fontSize: 11, bold: true, color: C.accent2 });
text(s, best.name, { x: 0.9, y: 2.1, w: 5.8, h: 0.9, fontSize: 26, bold: true, color: C.text2, fontFace: THEME.headFontFace });
bullets(s, [
  `${n1(best.protein)} g protein vs a ${n1(D.rec_any.context.meal_target)} g lunch target (35% of ${n1(D.rec_any.context.daily_target)} g/day)`,
  `${n1(best.kcal)} kcal, within the ${D.rec_any.context.kcal_allowance} kcal lunch allowance`,
  `${inr(best.cost)} estimated cost, leaving ${inr(350 - best.cost)} of the budget`,
  `Liked in explicit feedback; confidence ${best.confidence}`,
  `Best delivery-only option: ${bestDel.name}, ${inr(bestDel.cost)}, ${n1(bestDel.protein)} g protein`,
], { x: 0.9, y: 3.1, w: 5.8, h: 3.3 });
stat(s, 7.4, 1.45, 2.55, inr(D.spending.total), 'spent on food in 365 days (synthetic)');
stat(s, 10.15, 1.45, 2.55, `${n1(D.nutrition.avg.protein_g)} g`, `logged protein per day vs ${n1(D.nutrition.goals[0].target)} g target`, C.accent2);
stat(s, 7.4, 3.2, 2.55, `${D.rec_any.evaluated}`, 'meal combinations scored for this lunch');
stat(s, 10.15, 3.2, 2.55, `${D.rec_any.excluded.length}`, 'foods excluded by disliked / avoid feedback', C.accent2);
text(s, 'Scores combine goal progress, explicit ratings and cost with published weights; all values recalculate when the budget, goal or food choices change.',
  { x: 7.4, y: 5.05, w: 5.3, h: 1.4, fontSize: 14, color: C.text2, italic: true });

// ---------------------------------------------------------------- 3 problem & dataset design
pres.addSection({ title: 'Data' });
s = content('Four linked synthetic datasets cover one year', 'Data');
const q = D.quality.clean;
const ds = [
  ['A', 'Orders & consumption', `${q.orders} orders, ${q.order_items} items. Purchases, home meals, consumption status and portion eaten`],
  ['B', 'Preferences & feedback', `${q.food_feedback} ratings (1–5) with liked / acceptable / disliked / avoid labels`],
  ['C', 'Health & goals', `${q.health_measurements} measurements (weight, waist, BP, glucose); 3 goals with cited references`],
  ['D', 'Nutrition & meal options', `${q.foods} foods with per-serving or per-100 g nutrients; ${q.meal_options} priced meal options`],
];
ds.forEach(([k, t, d], i) => {
  const x = 0.6 + i * 3.08;
  card(s, x, 1.5, 2.88, 3.3);
  badge(s, x + 0.25, 1.75, k);
  text(s, t, { x: x + 0.25, y: 2.4, w: 2.4, h: 0.7, fontSize: 18, bold: true, color: C.text2 });
  text(s, d, { x: x + 0.25, y: 3.15, w: 2.4, h: 1.5, fontSize: 13 });
});
bullets(s, [
  'Stable IDs link every table: orders → items → foods → nutrition; feedback → food (and order); measurements → person.',
  'Generated by a seeded script (reproducible): weekday delivery lunches, home dinners, grocery runs, a 3-week travel gap.',
  'Purchase frequency is driven by convenience, not by the hidden ratings, so buying and liking can diverge.',
  'Clearly labelled synthetic; nutrients approximate IFCT 2017 / USDA values; targets cite ICMR-NIN 2020, DGA, WHO, IOM.',
], { x: 0.6, y: 5.1, w: 12.1, h: 1.8 });

// ---------------------------------------------------------------- 4 architecture
s = content('Architecture: one set of formulas from CSV to dashboard', 'Data');
const steps = [
  ['Generate', 'Seeded synthetic CSVs with planted quality issues'],
  ['Clean', 'Validate, standardise, reject with reasons'],
  ['MySQL', 'Constrained schema, idempotent import'],
  ['Django API', 'DRF views over foodspend_core formulas'],
  ['React', 'Plotly dashboard and simulators'],
];
steps.forEach(([t, d], i) => {
  const x = 0.6 + i * 2.48;
  card(s, x, 1.7, 2.18, 2.0, i === 3 ? C.accent1 : C.background2);
  text(s, t, { x: x + 0.2, y: 1.9, w: 1.8, h: 0.5, fontSize: 18, bold: true, color: i === 3 ? C.background1 : C.text2 });
  text(s, d, { x: x + 0.2, y: 2.5, w: 1.8, h: 1.1, fontSize: 13, color: i === 3 ? C.background1 : C.text1 });
  if (i < steps.length - 1) {
    s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.2, y: 2.55, w: 0.26, h: 0.3, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: oid('arrow') });
  }
});
card(s, 0.6, 4.1, 12.1, 2.55);
text(s, 'Why it holds together', { x: 0.9, y: 4.3, w: 6, h: 0.4, fontSize: 18, bold: true, color: C.text2 });
bullets(s, [
  'foodspend_core (pure Python) holds every formula; the API and the Jupyter notebooks import the same functions.',
  '48 SQL-vs-pandas checks and 35 backend tests compare database results with independent calculations.',
  'The browser never sends prices or nutrients: scenarios send food IDs and servings, and the server recalculates.',
  'Stack: React 18 + Vite + Bootstrap + Plotly · Django 6 + DRF · MySQL 8 · pandas, NumPy, Matplotlib, Jupyter.',
], { x: 0.9, y: 4.8, w: 11.5, h: 1.8 });

// ---------------------------------------------------------------- 5 cleaning
s = content('Cleaning caught every planted problem without guessing', 'Data');
const checkRows = D.quality.checks.filter((c) => ['exact duplicate rows removed', 'serving units standardised',
  'blank food_id resolved by exact normalised-name match', 'quantity must be > 0', 'unknown food (orphan food_id)',
  'final_total recomputed from components (subtotal - discount + tax + delivery + other)', 'rating missing or outside 1-5',
  'physiologically implausible value or unknown indicator', 'foods with unknown nutrient values (kept as NULL, not zero)',
  'sum(item line totals) equals order items_subtotal (no double counting)'].includes(c.check));
const fmt = (c) => Object.entries(c).filter(([k]) => !['table', 'check', 'order_ids', 'rule', 'feedback_ids'].includes(k))
  .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${Array.isArray(v) ? v.join(', ') : v}`).join('; ');
s.addTable([tableHead(['Table', 'Check / action', 'Result']),
  ...checkRows.map((c) => [c.table, c.check.replace(' (subtotal - discount + tax + delivery + other)', ''), fmt(c)])], {
  x: 0.6, y: 1.45, w: 8.3, colW: [1.95, 3.6, 2.75], fontSize: 11, color: C.text1, border: { type: 'solid', pt: 0.5, color: 'D5DDD7' },
  rowH: 0.3, valign: 'middle', objectName: oid('table') });
stat(s, 9.3, 1.45, 3.4, `${D.quality.rejected}`, 'rows rejected and logged with the rule that rejected them', C.accent2);
stat(s, 9.3, 3.2, 3.4, `${D.quality.coverage.days_with_records} / 365`, 'days with at least one record (travel gap in March)');
text(s, 'Rules: a blank food ID is filled only by an exact normalised-name match; unknown nutrients stay NULL; purchases are never assumed eaten.',
  { x: 9.3, y: 4.95, w: 3.4, h: 1.7, fontSize: 13, color: C.text2, italic: true });

// ---------------------------------------------------------------- 6 spending
pres.addSection({ title: 'Analysis' });
const sp = D.spending;
const fees = sp.components.tax + sp.components.delivery_fees + sp.components.other_charges;
s = content(`Delivery drives ${Math.round(sp.by_type.delivery_order / sp.total * 100)}% of ${inr(sp.total)} annual food spending`, 'Analysis');
s.addChart(pres.charts.BAR, [
  { name: 'Delivery orders', labels: D.monthly.labels, values: D.monthly.delivery },
  { name: 'Cafe purchases', labels: D.monthly.labels, values: D.monthly.cafe },
  { name: 'Grocery purchases', labels: D.monthly.labels, values: D.monthly.grocery },
], { x: 0.6, y: 1.4, w: 8.4, h: 5.3, barDir: 'col', barGrouping: 'stacked', chartColors: [HEX.accent1, HEX.accent2, HEX.accent4],
  showTitle: true, title: 'Monthly spending by transaction type (₹)', showLegend: true, legendPos: 'b', valAxisLabelFormatCode: '₹#,##0',
  ...chartText, objectName: oid('chart') });
stat(s, 9.4, 1.45, 3.3, inr(sp.avg_month), 'average per month across 365 days');
stat(s, 9.4, 3.15, 3.3, inr(fees), `tax, delivery and platform charges (${(fees / sp.total * 100).toFixed(1)}%)`, C.accent2);
text(s, `Spending = sum of order final totals (subtotal − discount + tax + fees) over ${sp.transactions} transactions; discounts saved ${inr(sp.components.discounts)}. Home-meal ingredient estimates are excluded. March dips with the travel gap.`,
  { x: 9.4, y: 4.9, w: 3.3, h: 1.8, fontSize: 13, color: C.text2 });

// ---------------------------------------------------------------- 7 nutrition
const g = Object.fromEntries(D.nutrition.goals.map((x) => [x.goal_key, x]));
s = content('Logged protein and fibre sit below documented targets', 'Analysis');
s.addChart(pres.charts.BAR, [{ name: '% of daily target', labels: ['Calories (maximum)', 'Fibre (minimum)', 'Protein (minimum)'],
  values: [g.calories.pct_of_target, g.fiber.pct_of_target, g.protein.pct_of_target] }], {
  x: 0.6, y: 1.4, w: 6.6, h: 4.2, barDir: 'bar', chartColors: [HEX.accent1],
  showTitle: true, title: 'Average logged intake as % of documented daily target', showLegend: false, showValue: true,
  dataLabelPosition: 'outEnd', dataLabelFormatCode: '0"%"', valAxisMaxVal: 120, valAxisMinVal: 0, ...chartText, objectName: oid('chart') });
s.addTable([tableHead(['Measure', 'Logged avg', 'Target', 'Status']),
  ...D.nutrition.goals.map((x) => [x.nutrient.split('_')[0].replace('fiber', 'fibre'), n1(x.average_logged), `${n1(x.target)} ${x.unit}`, x.status]),
  ...D.nutrition.energy.map((e) => [e.indicator.replace('_energy_pct', ' % of energy'), `${n1(e.value)}%`, e.indicator.startsWith('fat') ? '≤ 30%' : '45–65%', e.status]),
], { x: 7.6, y: 1.5, w: 5.1, colW: [1.5, 1.1, 1.3, 1.2], fontSize: 12, color: C.text1, border: { type: 'solid', pt: 0.5, color: 'D5DDD7' }, objectName: oid('table') });
bullets(s, [
  `Based on ${D.nutrition.days_logged} logged days (${D.nutrition.coverage}% of the year); unlogged food is missing, so intake is likely underestimated.`,
  `Fibre is unknown for 2 dishes (${D.nutrition.unknown_fiber_items} meal items): reported as unknown, not zero.`,
  'Status labels are used only where a cited target exists; a value above a minimum is not scored as “better”.',
], { x: 0.6, y: 5.8, w: 12.1, h: 1.1, fontSize: 13 });

// ---------------------------------------------------------------- 8 preferences
const P = D.preferences;
const noodle = D.findings.find((f) => f.title.startsWith('Frequent purchases'));
s = content('Buying a food often does not mean liking it', 'Analysis');
s.addChart(pres.charts.SCATTER, [
  { name: 'Purchases', values: P.points.map((p) => p.x) },
  { name: 'Mean rating', values: P.points.map((p) => p.y) },
], { x: 0.6, y: 1.4, w: 7.4, h: 5.3, chartColors: [HEX.accent1], lineSize: 0, lineDataSymbolSize: 9, showTitle: true,
  title: 'Each food: purchase transactions (x) vs mean explicit rating (y)', showLegend: false, valAxisMinVal: 1, valAxisMaxVal: 5,
  showValAxisTitle: true, valAxisTitle: 'Mean rating (1–5)', showCatAxisTitle: true, catAxisTitle: 'Purchases in 365 days',
  valAxisTitleFontSize: 11, catAxisTitleFontSize: 11, ...chartText, objectName: oid('chart') });
stat(s, 8.4, 1.45, 4.3, `${P.spearman}`, `rank correlation (Spearman) between rating and purchases across ${P.rated} rated foods`);
card(s, 8.4, 3.2, 4.3, 2.2);
text(s, 'Example', { x: 8.65, y: 3.4, w: 3.8, h: 0.35, fontSize: 12, bold: true, color: C.accent2 });
text(s, noodle ? noodle.detail.split('. Spearman')[0] + '.' : '', { x: 8.65, y: 3.8, w: 3.8, h: 1.5, fontSize: 13 });
text(s, `${P.records} explicit feedback records. Recommendations use ratings only; disliked or avoided foods are excluded, and purchase counts are shown beside ratings but never used as evidence of liking.`,
  { x: 8.4, y: 5.6, w: 4.3, h: 1.2, fontSize: 12, color: C.text2 });

// ---------------------------------------------------------------- 9 health
s = content('Health indicators: trends reported, causes not claimed', 'Analysis');
const label = (i) => ({ bmi: 'BMI (derived)', weight: 'Weight', waist_circumference: 'Waist', systolic_bp: 'Systolic BP',
  diastolic_bp: 'Diastolic BP', fasting_glucose: 'Fasting glucose' }[i] || i);
s.addTable([tableHead(['Indicator', 'First', 'Latest', 'Change', 'Readings', 'Reference', 'Latest status']),
  ...D.health.map((h) => [label(h.indicator), `${n1(h.first_value)} ${h.unit}`, `${n1(h.latest_value)} ${h.unit}`,
    h.change == null ? '—' : signed(h.change), `${h.measurements}`,
    h.reference_upper == null && h.reference_lower == null ? 'none' : `${h.reference_lower ?? ''}${h.reference_lower != null ? '–' : '≤ '}${h.reference_upper}`,
    h.reference_upper == null && h.reference_lower == null ? 'not assessed' : h.latest_status]),
], { x: 0.6, y: 1.45, w: 8.6, colW: [1.7, 1.25, 1.25, 0.9, 0.95, 1.15, 1.4], fontSize: 12, color: C.text1,
  border: { type: 'solid', pt: 0.5, color: 'D5DDD7' }, rowH: 0.4, objectName: oid('table') });
card(s, 9.6, 1.45, 3.1, 5.2);
text(s, 'How to read this', { x: 9.85, y: 1.65, w: 2.6, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, [
  'All values are simulated.',
  'Weight weekly, waist and BP monthly, glucose quarterly; March has no readings.',
  'Status compares the latest value with a cited range (WHO, ADA, ACC/AHA, IDF). It is not a diagnosis.',
  'Changes co-occur with diet patterns but are not attributed to any food.',
], { x: 9.85, y: 2.15, w: 2.65, h: 4.4, fontSize: 13 });

// ---------------------------------------------------------------- 10 method
pres.addSection({ title: 'Recommendation' });
s = content('A transparent score ranks every feasible meal', 'Recommendation');
const method = [
  ['1', 'Set the target', 'Daily goal × meal share (lunch 35%); recent 30-day intake for context'],
  ['2', 'Build candidates', 'Each main at allowed servings, alone or + one side / previously bought pantry food'],
  ['3', 'Apply constraints', 'Cost ≤ budget · listed for the meal · latest label not disliked / avoid'],
  ['4', 'Score', '0.5 goal + 0.3 preference + 0.2 cost (user-adjustable)'],
  ['5', 'Explain', 'Reasons, alternatives, trade-offs, confidence, ±15% serving range'],
];
method.forEach(([k, t, d], i) => {
  const y = 1.45 + i * 1.05;
  badge(s, 0.6, y + 0.1, k);
  text(s, t, { x: 1.3, y: y + 0.05, w: 3.0, h: 0.6, fontSize: 17, bold: true, color: C.text2, valign: 'middle' });
  text(s, d, { x: 4.3, y: y + 0.05, w: 3.9, h: 0.75, fontSize: 13, valign: 'middle' });
});
card(s, 8.6, 1.45, 4.1, 5.2);
text(s, 'Score components', { x: 8.85, y: 1.65, w: 3.6, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, [
  'Goal = 0.7 × min(nutrient ÷ meal target, 1) + 0.3 × calorie fit',
  'Calorie fit = 1 at 60–100% of the meal allowance, lower outside',
  'Preference = (rating − 1) ÷ 4, with rating shrunk toward the person’s average: (n·mean + 2·avg) ÷ (n + 2)',
  'Cost = 1 − cost ÷ budget',
  'Ties: higher preference, then lower cost',
  'No machine learning',
], { x: 8.85, y: 2.15, w: 3.6, h: 4.4, fontSize: 13 });

// ---------------------------------------------------------------- 11 recommendation & alternatives
s = content('Recommended lunch and four alternatives', 'Recommendation');
const rows = [{ ...best, type: 'Recommended' }, ...D.rec_any.alternatives];
s.addTable([tableHead(['Option', 'Meal', 'Cost', 'Protein (g)', 'kcal', 'Score']),
  ...rows.map((r, i) => [{ text: r.type, options: { bold: i === 0 } }, { text: r.name, options: { bold: i === 0 } },
    inr2(r.cost), n1(r.protein), n1(r.kcal), r.score.toFixed(3)])],
{ x: 0.6, y: 1.45, w: 12.1, colW: [2.9, 4.8, 1.1, 1.2, 1.0, 1.1], fontSize: 13, color: C.text1, rowH: 0.42,
  border: { type: 'solid', pt: 0.5, color: 'D5DDD7' }, objectName: oid('table') });
card(s, 0.6, 4.3, 5.9, 2.4);
text(s, 'Trade-offs', { x: 0.85, y: 4.45, w: 5.4, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, [
  'The larger serving adds protein but also calories and cost, and scores slightly lower.',
  'Adding a pantry food adds little cost; the dal thali swap trades protein for a lower price.',
  `Excluded by feedback: ${D.rec_any.excluded.join(', ')}.`,
], { x: 0.85, y: 4.9, w: 5.4, h: 1.75, fontSize: 13 });
card(s, 6.8, 4.3, 5.9, 2.4);
text(s, 'Delivery-only lunch (₹350 budget)', { x: 7.05, y: 4.45, w: 5.4, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, [
  `${bestDel.name}: ${inr2(bestDel.cost)}, ${n1(bestDel.protein)} g protein, ${n1(bestDel.kcal)} kcal.`,
  ...D.rec_delivery.alternatives.slice(0, 2).map((a) => `${a.type}: ${a.name} (${inr(a.cost)}, ${n1(a.protein)} g).`),
], { x: 7.05, y: 4.9, w: 5.4, h: 1.75, fontSize: 13 });

// ---------------------------------------------------------------- 12 what-if
s = content('What-if: each change shifts protein and cost', 'Recommendation');
s.addChart(pres.charts.BAR, [{ name: 'Protein change (g)', labels: D.scenarios.map((x) => x.name), values: D.scenarios.map((x) => x.protein_diff) }], {
  x: 0.6, y: 1.4, w: 6.6, h: 4.6, barDir: 'bar', chartColors: [HEX.accent1], showTitle: true,
  title: 'Protein change vs baseline: Paneer Butter Masala + 2 roti (g)', showLegend: false, showValue: true,
  dataLabelPosition: 'outEnd', dataLabelFormatCode: '+0.0;−0.0;0', catAxisLabelPos: 'low', ...chartText, objectName: oid('chart') });
s.addTable([tableHead(['Scenario', 'Cost change', 'kcal change', 'Within ₹350']),
  ...D.scenarios.map((x) => [x.name, `${x.cost_diff >= 0 ? '+' : '−'}₹${Math.abs(x.cost_diff).toFixed(2)}`, signed(x.kcal_diff, 0), x.within_budget ? 'Yes' : 'No'])],
{ x: 7.6, y: 1.5, w: 5.1, colW: [2.2, 1.1, 1.0, 0.8], fontSize: 12, color: C.text1, border: { type: 'solid', pt: 0.5, color: 'D5DDD7' }, objectName: oid('table') });
bullets(s, [
  'Doubling the dish doubles protein but exceeds the budget.',
  'Adding eggs from the pantry is the cheapest protein gain.',
  'All values are recalculated server-side from reference data for every change.',
], { x: 7.6, y: 4.2, w: 5.1, h: 2.5, fontSize: 13 });

// ---------------------------------------------------------------- 13 budget
s = content('A bigger budget does not buy a better delivery lunch here', 'Recommendation');
s.addTable([tableHead(['Budget', 'Feasible combinations', 'Top-ranked option', 'Cost', 'Remaining', 'Used', 'Protein']),
  ...D.budgets.map((b) => [inr(b.budget), `${b.feasible}`, b.top || 'none', inr2(b.cost), inr2(b.remaining), b.util == null ? '—' : `${n1(b.util)}%`, `${n1(b.protein)} g`])],
{ x: 0.6, y: 1.45, w: 12.1, colW: [1.1, 1.9, 4.0, 1.2, 1.3, 1.0, 1.6], fontSize: 13, color: C.text1, rowH: 0.42,
  border: { type: 'solid', pt: 0.5, color: 'D5DDD7' }, objectName: oid('table') });
stat(s, 0.6, 4.2, 3.8, inr(D.budgets[0].budget), 'already covers the top delivery option once pantry eggs are allowed');
card(s, 4.8, 4.2, 7.9, 2.45);
bullets(s, [
  'Raising the budget adds options but the same lunch keeps winning: more spending is not treated as healthier.',
  'Budget utilisation and remaining budget are shown for every option; zero budgets are handled without division errors.',
  'Prices are the latest in the synthetic history, not current market prices.',
], { x: 5.05, y: 4.45, w: 7.4, h: 2.1, fontSize: 14 });

// ---------------------------------------------------------------- 14 dashboard
pres.addSection({ title: 'Dashboard' });
s = content('The dashboard answers the question interactively', 'Dashboard');
s.addImage({ path: IMG('dashboard.png'), x: 0.6, y: 1.4, w: 8.6, h: 4.91, altText: 'Dashboard page: KPIs, monthly spending and suggested next meal', objectName: oid('img') });
s.addImage({ path: IMG('recommend.png'), x: 9.5, y: 1.4, w: 3.2, h: 2.01, altText: 'Next-meal page: recommendation, reasons and confidence', objectName: oid('img') });
bullets(s, [
  'Nine pages: dashboard, food history, nutrition, preferences, health, next meal, what-if, budget, data & evidence.',
  'Every control (date range, goal, target, budget, source, weights, servings) triggers a server recalculation.',
  'Charts carry titles, units and reference lines; status labels always pair an icon with text.',
], { x: 9.5, y: 3.65, w: 3.2, h: 3.2, fontSize: 13 });

// ---------------------------------------------------------------- 15 findings
pres.addSection({ title: 'Conclusions' });
s = content('Key findings', 'Conclusions');
D.findings.slice(0, 6).forEach((f, i) => {
  const col = i % 2;
  const row = Math.floor(i / 2);
  const x = 0.6 + col * 6.15;
  const y = 1.45 + row * 1.8;
  card(s, x, y, 5.95, 1.65);
  text(s, f.title, { x: x + 0.25, y: y + 0.15, w: 5.45, h: 0.4, fontSize: 15, bold: true, color: C.text2 });
  text(s, f.detail.replace(/ Spearman correlation.*$/, ''), { x: x + 0.25, y: y + 0.55, w: 5.45, h: 1.05, fontSize: 12 });
});

// ---------------------------------------------------------------- 16 limitations & next steps
s = content('Limitations and what we would improve', 'Conclusions');
card(s, 0.6, 1.45, 5.95, 5.2);
text(s, 'Limitations', { x: 0.85, y: 1.65, w: 5.4, h: 0.4, fontSize: 18, bold: true, color: C.text2 });
bullets(s, [
  'Synthetic data for one fictional person; nutrients are unverified estimates.',
  'Intake covers logged meals only; grocery consumption is unknown.',
  'Historical prices; no real-time availability or delivery times.',
  'Meal shares, weights and ±15% uncertainty are assumptions.',
  'Health trends are associations; nothing here is medical advice.',
], { x: 0.85, y: 2.15, w: 5.45, h: 4.4 });
card(s, 6.75, 1.45, 5.95, 5.2, C.text2);
text(s, 'Next improvements', { x: 7.0, y: 1.65, w: 5.4, h: 0.4, fontSize: 18, bold: true, color: C.background1 });
s.addText([
  'Load verified nutrients from IFCT / USDA FoodData Central by food code',
  'Day-level planning: optimise all remaining meals against several goals',
  'Log consumption of pantry stock to close the purchase-vs-eaten gap',
  'Add authentication and per-user goals before sharing beyond localhost',
  'Code-split the Plotly bundle for faster first load',
].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1, paraSpaceAfter: 6 } })),
{ isTextBox: true, margin: 0, x: 7.0, y: 2.15, w: 5.45, h: 4.4, fontSize: 14, color: C.background1, valign: 'top', objectName: oid('list') });

// ---------------------------------------------------------------- write
pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, THEME))
  .then(() => console.log('wrote', OUT));
