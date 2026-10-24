import Badge from '../components/Badge.jsx';
import { date } from '../lib/format.js';

const FACTOR_LABEL = {
  front_end: 'Front-end yields', long_end: 'Long-end yields', curve: 'Curve slope', usd: 'US dollar',
  equities: 'Equities', credit_spreads: 'Credit spreads', vol: 'Volatility', gold: 'Gold', oil: 'Oil',
  breakevens: 'Breakevens', copper: 'Copper',
};

export default function RegimeHero({ regime, meta }) {
  return (
    <section id="regime" className="scroll-mt-20">
      <p className="eyebrow">01 What happened overnight?</p>
      <div className="mt-3 grid gap-8 lg:grid-cols-[1fr_320px]">
        <div>
          <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink md:text-6xl">
            {regime.headline}
          </h1>
          <p className="mt-6 max-w-3xl text-xl leading-relaxed text-ink-2 md:text-[22px]">{regime.paragraph}</p>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Badge kind={regime.tone}>{regime.tone_label || 'Neutral'}</Badge>
            <Badge kind="neutral">Confidence: {regime.confidence || 'low'}</Badge>
            <span className="text-xs text-ink-3">
              Close of {date(meta.as_of, { weekday: 'long', day: 'numeric', month: 'long' })}
              {meta.llm?.used ? ' · prose styled by Claude, numbers checked against computed data' : ' · deterministic commentary'}
            </span>
          </div>
        </div>
        <aside className="card p-5">
          <p className="eyebrow">Cross-asset signature</p>
          <p className="mt-1 text-xs text-ink-3">Today's move in each factor, in units of its 20-day volatility.</p>
          <ul className="mt-4 space-y-2.5">
            {Object.entries(regime.factors || {})
              .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
              .slice(0, 8)
              .map(([k, v]) => {
                const w = Math.min(Math.abs(v) / 3, 1) * 50;
                const strong = Math.abs(v) >= 1;
                return (
                  <li key={k} className="grid grid-cols-[112px_1fr_40px] items-center gap-3 text-xs">
                    <span className={regime.drivers?.includes(k) ? 'text-ink' : 'text-ink-2'}>{FACTOR_LABEL[k] || k}</span>
                    <span className="relative h-2 rounded-full bg-line/60">
                      <span className="absolute left-1/2 top-[-3px] h-[14px] w-px bg-ink-3/50" />
                      <span
                        className={`absolute top-0 h-2 rounded-full ${strong ? (v > 0 ? 'bg-up' : 'bg-down') : 'bg-ink-3/60'}`}
                        style={v >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
                      />
                    </span>
                    <span className="num text-right text-ink-2">{v > 0 ? '+' : '−'}{Math.abs(v).toFixed(1)}σ</span>
                  </li>
                );
              })}
          </ul>
        </aside>
      </div>
    </section>
  );
}
