export const RANGES = ['1W', '1M', '3M', '6M', 'YTD', '1Y', '5Y', 'MAX'];

export default function RangeSelector({ value, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-page p-0.5" role="group" aria-label="Timeframe">
      {RANGES.map((r) => (
        <button key={r} type="button" className="btn-seg" aria-pressed={value === r} onClick={() => onChange(r)}>
          {r === 'MAX' ? 'Max' : r}
        </button>
      ))}
    </div>
  );
}
