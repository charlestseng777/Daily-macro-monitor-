// Where today's level sits in its trailing range (0-100). Extremes are
// flagged because they are the levels worth remembering.
export default function Percentile({ value, label = '1Y percentile' }) {
  if (value === null || value === undefined) return <span className="text-ink-3">—</span>;
  const extreme = value >= 90 || value <= 10;
  return (
    <span className="inline-flex items-center gap-2" title={`${label}: ${Math.round(value)}`}>
      <span className="relative h-1 w-12 rounded-full bg-line">
        <span
          className={`absolute top-1/2 h-2.5 w-[3px] -translate-y-1/2 rounded-full ${extreme ? 'bg-surprise' : 'bg-ink-2'}`}
          style={{ left: `calc(${value}% - 1.5px)` }}
        />
      </span>
      <span className={`num w-6 text-right text-xs ${extreme ? 'text-surprise' : 'text-ink-3'}`}>{Math.round(value)}</span>
    </span>
  );
}
