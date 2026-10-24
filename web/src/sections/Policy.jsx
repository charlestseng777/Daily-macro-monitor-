import Section from '../components/Section.jsx';
import Badge from '../components/Badge.jsx';
import Move from '../components/Move.jsx';
import Sparkline from '../components/Sparkline.jsx';
import Tooltip from '../components/Tooltip.jsx';
import { date, signed } from '../lib/format.js';

function Horizon({ label, bp }) {
  const w = Math.min(Math.abs(bp ?? 0) / 100, 1) * 50;
  return (
    <div className="grid grid-cols-[34px_1fr_56px] items-center gap-2 text-xs">
      <span className="text-ink-3">{label}</span>
      <span className="relative h-1.5 rounded-full bg-line/70">
        <span className="absolute left-1/2 top-[-3px] h-3 w-px bg-ink-3/50" />
        <span className={`absolute top-0 h-1.5 rounded-full ${bp < 0 ? 'bg-up' : 'bg-down'}`}
          style={bp >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }} />
      </span>
      <span className="num text-right text-ink">{signed(bp, 0, 'bp')}</span>
    </div>
  );
}

function PathBars({ path }) {
  if (!path?.length) return null;
  const max = Math.max(25, ...path.map((p) => Math.abs(p.cumulative_bp)));
  return (
    <div className="flex h-16 items-center gap-1" aria-label="Implied path by meeting">
      {path.slice(0, 8).map((p) => {
        const h = (Math.abs(p.cumulative_bp) / max) * 30;
        return (
          <Tooltip key={p.date} className="flex-1" content={<span className="num">{date(p.date, { day: 'numeric', month: 'short', year: '2-digit' })}: {p.policy_implied?.toFixed(2)}% ({signed(p.cumulative_bp, 0, 'bp')} cumulative, {signed(p.change_bp, 0, 'bp')} at meeting)</span>}>
            <div className="relative h-16 w-full">
              <span className="absolute left-0 right-0 top-1/2 h-px bg-line" />
              <span className={`absolute left-[15%] right-[15%] rounded-[3px] ${p.cumulative_bp < 0 ? 'bg-up/80' : 'bg-down/80'}`}
                style={p.cumulative_bp < 0 ? { top: '50%', height: `${h}px` } : { bottom: '50%', height: `${h}px` }} />
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}

function BankCard({ b }) {
  const s = b.summary || {};
  return (
    <div className="card flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{b.name}</p>
          <p className="mt-1 font-display text-4xl font-semibold tracking-tight text-ink num">{b.policy_rate?.toFixed(2)}%</p>
          <p className="text-xs text-ink-3">Policy rate</p>
        </div>
        <Tooltip content={<>Method: {b.method_label}{b.quality === 'low' && '. Government bills trade with a term and credit basis to OIS, so treat this as indicative.'}</>}>
          <Badge kind={b.quality === 'demo' ? 'demo' : b.quality === 'low' ? 'low' : 'neutral'}>
            {b.quality === 'low' ? 'Proxy' : b.quality === 'demo' ? 'Demo' : b.quality === 'none' ? 'No pricing' : 'OIS'}
          </Badge>
        </Tooltip>
      </div>
      {s.next_meeting ? (
        <>
          <div className="mt-5 rounded-xl bg-raised/60 px-4 py-3">
            <p className="text-xs text-ink-3">Next meeting · {date(s.next_meeting, { day: 'numeric', month: 'short' })}</p>
            <p className="mt-0.5 text-[15px] text-ink">
              {s.next_move === 'hold' ? 'Hold priced' : <><span className="num">{s.next_prob_pct}%</span> chance of a 25bp {s.next_move}</>}
              <span className="num ml-2 text-ink-3">({signed(s.next_change_bp, 1, 'bp')})</span>
            </p>
          </div>
          <div className="mt-4 space-y-2">
            <Horizon label="3M" bp={s.priced_3m_bp} />
            <Horizon label="6M" bp={s.priced_6m_bp} />
            <Horizon label="12M" bp={s.priced_12m_bp} />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div>
              <p className="text-ink-3">Terminal</p>
              <p className="num text-base text-ink">{s.terminal_rate?.toFixed(2)}%</p>
              <p className="text-ink-3">by {date(s.terminal_date, { month: 'short', year: 'numeric' })}</p>
            </div>
            <div>
              <p className="text-ink-3">12M pricing, 1D change</p>
              <p className="text-base"><Move value={b.priced_12m_chg_bp} unit="bp" always /></p>
              <Sparkline points={b.pricing_history} width={110} height={20} />
            </div>
          </div>
          <div className="mt-4">
            <p className="mb-1 text-[11px] text-ink-3">Implied path, cumulative by meeting</p>
            <PathBars path={b.path} />
          </div>
        </>
      ) : (
        <p className="mt-6 text-sm text-ink-3">No market pricing available ({b.method_label}).</p>
      )}
      {b.provisional_meetings?.length > 0 && (
        <p className="mt-3 text-[11px] text-ink-3">Some meeting dates are provisional; verify against the <a className="underline hover:text-ink" href={b.calendar_url} target="_blank" rel="noreferrer">official calendar</a>.</p>
      )}
    </div>
  );
}

export default function Policy({ policy }) {
  return (
    <Section id="policy" index={7} question="What are central banks expected to do?" title="Policy expectations"
      aside={<span className="text-xs text-ink-3">Blue = cuts priced · red = hikes priced</span>}>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {policy.map((b) => <BankCard key={b.id} b={b} />)}
      </div>
    </Section>
  );
}
