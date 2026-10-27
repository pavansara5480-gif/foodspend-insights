export const inr = (v, digits = 0) =>
  v === null || v === undefined
    ? '—'
    : `${v < 0 ? '−' : ''}₹${Math.abs(Number(v)).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;

export const num = (v, digits = 1) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : Number(v).toLocaleString('en-IN', { maximumFractionDigits: digits });

export const pct = (v, digits = 1) => (v === null || v === undefined ? '—' : `${num(v, digits)}%`);

export const signed = (v, digits = 1, unit = '') =>
  v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${num(v, digits)}${unit}`;

export const NUTRIENTS = [
  { key: 'calories_kcal', label: 'Calories', unit: 'kcal' },
  { key: 'protein_g', label: 'Protein', unit: 'g' },
  { key: 'carbs_g', label: 'Carbohydrates', unit: 'g' },
  { key: 'fat_g', label: 'Fat', unit: 'g' },
  { key: 'fiber_g', label: 'Fibre', unit: 'g' },
];

export const nutrientLabel = (key) => NUTRIENTS.find((n) => n.key === key)?.label || key;
export const nutrientUnit = (key) => NUTRIENTS.find((n) => n.key === key)?.unit || '';

export const humanize = (s) => (s === 'bmi' ? 'BMI' : s ? s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '—');

export const GOALS = [
  { key: 'protein', label: 'Increase protein' },
  { key: 'fiber', label: 'Increase fibre' },
  { key: 'calories', label: 'Keep energy within requirement' },
];
export const MEALS = ['breakfast', 'lunch', 'snack', 'dinner'];
export const SOURCES = [
  { key: 'any', label: 'Any source' },
  { key: 'delivery', label: 'Delivery only' },
  { key: 'home', label: 'Home-cooked only' },
];
