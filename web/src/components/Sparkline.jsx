// Minimal trend line from server-sampled points. Rendering only: points are
// mapped into the box; no statistics are computed here.
export default function Sparkline({ points, width = 96, height = 28, highlight = false, label }) {
  if (!points || points.length < 2) return <span className="inline-block" style={{ width, height }} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = points
    .map((v, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(height - 3 - ((v - min) / span) * (height - 6)).toFixed(1)}`)
    .join(' ');
  const lastY = height - 3 - ((points[points.length - 1] - min) / span) * (height - 6);
  return (
    <svg width={width} height={height} className="overflow-visible" role="img" aria-label={label || 'trend'}>
      <path d={d} fill="none" stroke={highlight ? '#fab219' : '#898781'} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={width} cy={lastY} r="2.25" fill={highlight ? '#fab219' : '#c3c2b7'} />
    </svg>
  );
}
