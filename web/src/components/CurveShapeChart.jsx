import { useState } from 'react';
import { SERIES_COLOURS } from './TimeSeriesChart.jsx';

// Yield curve by tenor: today against one week, one month and one year ago.
// Tenors are categories, so this is a small SVG chart with its own hover.
const SNAPS = [
  { key: 'today', label: 'Today' },
  { key: 'w1', label: '1W ago' },
  { key: 'm1', label: '1M ago' },
  { key: 'y1', label: '1Y ago' },
];

export default function CurveShapeChart({ points, width = 520, height = 220 }) {
  const [hover, setHover] = useState(null);
  if (!points?.length) return null;
  const vals = points.flatMap((p) => SNAPS.map((s) => p[s.key]).filter((v) => v != null));
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const pad = (max - min) * 0.12 || 0.1;
  const lo = min - pad;
  const hi = max + pad;
  const L = 44, R = 12, T = 12, B = 28;
  const x = (i) => L + (i * (width - L - R)) / Math.max(points.length - 1, 1);
  const y = (v) => T + ((hi - v) / (hi - lo)) * (height - T - B);
  const ticks = [lo + (hi - lo) * 0.15, (lo + hi) / 2, hi - (hi - lo) * 0.15];

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-4 text-xs text-ink-2">
        {SNAPS.map((s, i) => (
          <span key={s.key} className="inline-flex items-center gap-2">
            <span className="h-0.5 w-4 rounded-full" style={{ background: SERIES_COLOURS[i], opacity: i === 0 ? 1 : 0.7 }} />
            {s.label}
          </span>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={width - R} y1={y(t)} y2={y(t)} stroke="#202125" />
            <text x={L - 8} y={y(t) + 4} textAnchor="end" fontSize="10" fill="#898781" className="num">{t.toFixed(2)}%</text>
          </g>
        ))}
        {SNAPS.map((s, si) => {
          const pts = points.map((p, i) => (p[s.key] == null ? null : [x(i), y(p[s.key])])).filter(Boolean);
          if (pts.length < 2) return null;
          return (
            <path key={s.key} d={pts.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ')} fill="none"
              stroke={SERIES_COLOURS[si]} strokeWidth={si === 0 ? 2.5 : 1.5} strokeOpacity={si === 0 ? 1 : 0.7}
              strokeDasharray={si === 3 ? '4 4' : undefined} />
          );
        })}
        {points.map((p, i) => (
          <g key={p.tenor} onMouseEnter={() => setHover(i)}>
            <rect x={x(i) - 24} y={T} width="48" height={height - T - B} fill="transparent" />
            {hover === i && <line x1={x(i)} x2={x(i)} y1={T} y2={height - B} stroke="#5a5a58" />}
            <circle cx={x(i)} cy={y(p.today)} r="4" fill={SERIES_COLOURS[0]} stroke="#141518" strokeWidth="2" />
            <text x={x(i)} y={height - 8} textAnchor="middle" fontSize="11" fill="#898781">{p.tenor}</text>
          </g>
        ))}
      </svg>
      <div className="min-h-[20px] text-xs text-ink-2 num">
        {hover != null && (
          <span>
            <span className="text-ink">{points[hover].tenor}</span>
            {SNAPS.map((s) => points[hover][s.key] != null && (
              <span key={s.key} className="ml-3">{s.label} {points[hover][s.key].toFixed(3)}%</span>
            ))}
          </span>
        )}
      </div>
    </div>
  );
}
