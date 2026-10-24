const STYLES = {
  hawkish: 'border-surprise/40 text-surprise',
  dovish: 'border-up/40 text-up',
  risk_on: 'border-riskon/40 text-riskon',
  risk_off: 'border-riskoff/50 text-[#ef7b7b]',
  inflation: 'border-surprise/40 text-surprise',
  neutral: 'border-line text-ink-2',
  held: 'border-line text-ink-2',
  broke: 'border-surprise/50 text-surprise',
  signal: 'border-line text-ink-3',
  demo: 'border-surprise/60 text-surprise bg-surprise/10',
  low: 'border-line text-ink-3',
};

export default function Badge({ kind = 'neutral', children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${STYLES[kind] || STYLES.neutral} ${className}`}>
      {children}
    </span>
  );
}
