import Section from '../components/Section.jsx';
import Move from '../components/Move.jsx';
import Percentile from '../components/Percentile.jsx';
import Sparkline from '../components/Sparkline.jsx';
import { levelFor } from '../lib/format.js';

export function LevelTable({ rows, showYtd = false, onSelect }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="table-head">
          <th className="py-2 text-left font-medium">Instrument</th>
          <th className="py-2 text-right font-medium">Level</th>
          <th className="py-2 text-right font-medium">1D</th>
          <th className="py-2 text-right font-medium">1W</th>
          <th className="py-2 text-right font-medium">1M</th>
          {showYtd && <th className="py-2 text-right font-medium">YTD</th>}
          <th className="py-2 pl-4 text-left font-medium">1Y pctile</th>
          <th className="py-2 text-right font-medium">3M</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line/60">
        {rows.map((r) => (
          <tr key={r.id} className={onSelect ? 'cursor-pointer hover:bg-raised/50' : ''} onClick={onSelect ? () => onSelect(r.id) : undefined}>
            <td className="py-2.5 pr-2">
              <span className="text-ink">{r.short || r.name}</span>
              {r.stale && <span className="ml-2 text-[10px] uppercase text-surprise" title={`Last print ${r.date}`}>stale</span>}
            </td>
            <td className="num py-2.5 text-right font-medium text-ink">{levelFor(r)}</td>
            <td className="py-2.5 text-right"><Move value={r.d1} unit={r.unit} z={r.z_d1} /></td>
            <td className="py-2.5 text-right"><Move value={r.w1} unit={r.unit} /></td>
            <td className="py-2.5 text-right"><Move value={r.m1} unit={r.unit} /></td>
            {showYtd && <td className="py-2.5 text-right"><Move value={r.ytd} unit={r.unit} /></td>}
            <td className="py-2.5 pl-4"><Percentile value={r.pct_1y} /></td>
            <td className="py-2.5 pl-3 text-right"><Sparkline points={r.spark} width={72} height={22} highlight={r.pct_1y >= 90 || r.pct_1y <= 10} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Numbers({ numbers }) {
  return (
    <Section id="numbers" index={4} question="Which levels should I know cold?" title="Numbers to remember"
      aside={<span className="text-xs text-ink-3">1D in colour only when the move exceeds 1σ · amber = 1Y extreme</span>}>
      <div className="grid gap-4 xl:grid-cols-2">
        {numbers.map((g) => (
          <div key={g.region} className="card min-w-0 overflow-x-auto px-5 py-4">
            <p className="eyebrow mb-1">{g.name}</p>
            {g.rows.length ? <LevelTable rows={g.rows} /> : <p className="py-4 text-sm text-ink-3">No data.</p>}
          </div>
        ))}
      </div>
    </Section>
  );
}
