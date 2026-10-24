import Section from '../components/Section.jsx';
import Tooltip from '../components/Tooltip.jsx';
import { date, move } from '../lib/format.js';

const COL_LABEL = { rates: 'Rates', fx: 'FX', equities: 'Equities', credit: 'Credit', commodities: 'Commodities' };
const COL_NOTE = {
  rates: '10Y yield', fx: 'Currency vs USD', equities: 'Main index', credit: 'Spreads (up = wider)', commodities: 'Key commodity',
};
// Opacity by how unusual the move was; hue by direction.
const ALPHA = [0, 0.14, 0.28, 0.45];

function Cell({ c }) {
  if (!c.available) {
    return <td className="px-2 py-2"><div className="grid h-14 place-items-center rounded-lg border border-dashed border-line text-xs text-ink-3">n/a</div></td>;
  }
  const hue = c.direction === 'up' ? '57,135,229' : c.direction === 'down' ? '230,103,103' : '137,135,129';
  const strong = c.intensity >= 2;
  const arrow = c.direction === 'up' ? '▲' : c.direction === 'down' ? '▼' : '■';
  return (
    <td className="px-1.5 py-1.5">
      <Tooltip
        className="w-full"
        content={<><span className="text-ink">{c.name}</span><br />{c.short} {move(c.d1, c.unit)} · {c.z != null ? `${Math.abs(c.z).toFixed(1)}σ move` : ''}
          {c.proxy && <><br />Arrow shows spread direction; value is the {c.proxy} move.</>}
          {c.risk && <><br />Reads as risk-{c.risk}</>}</>}
      >
        <div
          className="flex h-14 w-full items-center justify-between rounded-lg px-3"
          style={{ background: `rgba(${hue},${ALPHA[c.intensity]})`, boxShadow: strong ? `inset 0 0 0 1px rgba(${hue},0.6)` : 'none' }}
        >
          <span className={`text-lg ${c.intensity ? '' : 'text-ink-3'}`} style={c.intensity ? { color: `rgb(${hue})` } : {}}>{arrow}</span>
          <span className={`num text-right text-sm ${c.intensity >= 1 ? 'text-ink' : 'text-ink-2'}`}>
            {move(c.value ?? c.d1, c.unit)}
            {c.proxy && <span className="block text-[10px] leading-none text-ink-3">{c.proxy}</span>}
            {c.lagged && <span className="block text-[10px] leading-none text-ink-3">{date(c.date)}</span>}
          </span>
        </div>
      </Tooltip>
    </td>
  );
}

export default function Heatmap({ heatmap }) {
  return (
    <Section id="heatmap" index={3} question="Which way did the world move?" title="Global cross-asset heatmap"
      aside={<span className="text-xs text-ink-3">▲▼ direction · shade = size vs normal · dated cells = previous print</span>}>
      <div className="card overflow-x-auto p-3">
        <table className="w-full min-w-[560px] border-separate border-spacing-0">
          <thead>
            <tr>
              <th className="w-32" />
              {heatmap.columns.map((c) => (
                <th key={c} className="px-2 pb-2 text-left">
                  <span className="table-head">{COL_LABEL[c]}</span>
                  <span className="block text-[10px] font-normal normal-case tracking-normal text-ink-3/80">{COL_NOTE[c]}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {heatmap.rows.map((r) => (
              <tr key={r.region}>
                <th className="pr-3 text-left text-sm font-medium text-ink">{r.name}</th>
                {r.cells.map((c) => <Cell key={c.column} c={c} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
