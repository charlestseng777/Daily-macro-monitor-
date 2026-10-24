import Section from '../components/Section.jsx';
import Move from '../components/Move.jsx';
import { date } from '../lib/format.js';

function Row({ m, rank }) {
  return (
    <li className="grid grid-cols-[20px_1fr_auto_auto] items-center gap-3 py-2.5">
      <span className="num text-xs text-ink-3">{rank}</span>
      <span className="min-w-0">
        <span className="block text-[15px] leading-snug text-ink">{m.name}</span>
        <span className="block text-xs text-ink-3">{m.asset_class} · {m.note}{m.lagged && <> · {date(m.date)} print</>}</span>
      </span>
      <span className="num text-right text-xs text-ink-3">{Math.abs(m.z).toFixed(1)}σ</span>
      <Move value={m.d1} unit={m.unit} always className="w-20 text-right text-[15px] font-medium" />
    </li>
  );
}

export default function Movers({ movers }) {
  return (
    <Section id="movers" index={2} question="What moved most?" title="Biggest overnight movers"
      aside={<span className="text-xs text-ink-3">Ranked by move ÷ 20-day vol</span>}>
      <div className="card grid divide-y divide-line md:grid-cols-2 md:divide-x md:divide-y-0">
        {[['Up', movers.up], ['Down', movers.down]].map(([label, list]) => (
          <div key={label} className="px-5 py-3">
            <p className="eyebrow pt-1">{label}</p>
            <ol className="divide-y divide-line/60">
              {list.length ? list.map((m, i) => <Row key={m.id} m={m} rank={i + 1} />) : <li className="py-3 text-sm text-ink-3">None</li>}
            </ol>
          </div>
        ))}
      </div>
    </Section>
  );
}
