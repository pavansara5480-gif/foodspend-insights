import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import { AXIS, GRID, INK } from '../utils/palette';

const axis = { gridcolor: GRID, linecolor: AXIS, zerolinecolor: AXIS, tickfont: { color: INK.muted, size: 11 },
  title: { font: { color: INK.secondary, size: 12 } }, automargin: true };

const BASE_LAYOUT = {
  font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: INK.secondary, size: 12 },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  margin: { l: 56, r: 16, t: 8, b: 48 },
  xaxis: axis,
  yaxis: axis,
  legend: { orientation: 'h', y: -0.22, font: { color: INK.secondary } },
  hoverlabel: { bgcolor: '#ffffff', bordercolor: AXIS, font: { color: INK.primary } },
  barcornerradius: 4,
  bargap: 0.25,
};

function merge(layout) {
  return {
    ...BASE_LAYOUT,
    ...layout,
    xaxis: { ...axis, ...(layout.xaxis || {}), title: { ...axis.title, ...(layout.xaxis?.title || {}) } },
    yaxis: { ...axis, ...(layout.yaxis || {}), title: { ...axis.title, ...(layout.yaxis?.title || {}) } },
  };
}

/** Plotly chart. `title` is rendered as HTML above the plot; `label` describes it for screen readers. */
export default function Plot({ data, layout = {}, height = 320, title, subtitle, label }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    Plotly.react(ref.current, data, { ...merge(layout), height }, { responsive: true, displayModeBar: false });
  }, [data, layout, height]);
  useEffect(() => {
    const el = ref.current;
    return () => el && Plotly.purge(el);
  }, []);
  return (
    <figure className="chart mb-0">
      {title && <figcaption className="chart-title">{title}</figcaption>}
      {subtitle && <div className="chart-subtitle">{subtitle}</div>}
      <div ref={ref} role="img" aria-label={label || title} />
    </figure>
  );
}
