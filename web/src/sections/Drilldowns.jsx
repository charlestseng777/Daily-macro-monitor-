import { useState } from 'react';
import Section from '../components/Section.jsx';
import TimeSeriesChart from '../components/TimeSeriesChart.jsx';
import CurveShapeChart from '../components/CurveShapeChart.jsx';
import Badge from '../components/Badge.jsx';
import { LevelTable } from './Numbers.jsx';
import { date, signed } from '../lib/format.js';

const REGION = { US: 'United States', UK: 'United Kingdom', DE: 'Germany', JP: 'Japan' };

// A level table whose rows choose the chart's series. Panels whose series
// share a unit allow comparing up to four on one axis.
function SeriesPanel({ rows, compare = false, initial }) {
  const [sel, setSel] = useState(initial || rows.slice(0, compare ? 2 : 1).map((r) => r.id));
  const toggle = (id) => {
    if (!compare) { setSel([id]); return; }
    setSel((s) => (s.includes(id) ? (s.length > 1 ? s.filter((x) => x !== id) : s) : [...s, id].slice(-4)));
  };
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1.1fr] [&>*]:min-w-0">
      <div className="overflow-x-auto">
        <p className="mb-1 text-xs text-ink-3">{compare ? 'Click rows to compare up to four series.' : 'Click a row to chart it.'}</p>
        <LevelTable rows={rows} showYtd onSelect={toggle} />
        <p className="mt-2 text-[11px] text-ink-3">Charted: {sel.join(', ')}</p>
      </div>
      <TimeSeriesChart ids={sel} />
    </div>
  );
}

function CurvesPanel({ shapes, curves }) {
  const [region, setRegion] = useState('US');
  const ids = curves.filter((c) => c.region === region).map((c) => c.id);
  return (
    <div>
      <div className="mb-4 inline-flex rounded-lg border border-line bg-page p-0.5">
        {Object.keys(shapes).map((r) => (
          <button key={r} type="button" className="btn-seg" aria-pressed={region === r} onClick={() => setRegion(r)}>{REGION[r]}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 [&>*]:min-w-0">
        <div><p className="mb-2 text-sm text-ink">Curve shape</p><CurveShapeChart points={shapes[region]?.points} /></div>
        {ids.length > 0 && <TimeSeriesChart key={region} ids={ids} title="Slopes" />}
      </div>
    </div>
  );
}

function OisPanel({ policy }) {
  const [bank, setBank] = useState(policy[0]?.id);
  const b = policy.find((p) => p.id === bank);
  return (
    <div>
      <div className="mb-4 inline-flex rounded-lg border border-line bg-page p-0.5">
        {policy.map((p) => (
          <button key={p.id} type="button" className="btn-seg" aria-pressed={bank === p.id} onClick={() => setBank(p.id)}>{p.short}</button>
        ))}
      </div>
      {b && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 [&>*]:min-w-0">
          <div className="overflow-x-auto">
            <p className="mb-2 text-sm text-ink">{b.name}: meeting-by-meeting <Badge kind={b.quality === 'low' ? 'low' : 'neutral'}>{b.method_label}</Badge></p>
            <table className="w-full text-sm">
              <thead><tr className="table-head">
                <th className="py-2 text-left font-medium">Meeting</th><th className="py-2 text-right font-medium">Implied rate</th>
                <th className="py-2 text-right font-medium">At meeting</th><th className="py-2 text-right font-medium">Cumulative</th>
              </tr></thead>
              <tbody className="divide-y divide-line/60">
                {b.path.map((m) => (
                  <tr key={m.date}>
                    <td className="py-2 text-ink">{date(m.date, { day: 'numeric', month: 'short', year: 'numeric' })}{b.provisional_meetings?.includes(m.date) && <span className="ml-2 text-[10px] uppercase text-ink-3">prov.</span>}</td>
                    <td className="num py-2 text-right text-ink">{m.policy_implied?.toFixed(3)}%</td>
                    <td className="num py-2 text-right text-ink-2">{signed(m.change_bp, 1, 'bp')}</td>
                    <td className="num py-2 text-right text-ink-2">{signed(m.cumulative_bp, 1, 'bp')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <TimeSeriesChart key={b.id} ids={[`PRICING_${b.id}_12M`]} title="12M pricing history" defaultRange="6M" />
        </div>
      )}
    </div>
  );
}

function Calendar({ events }) {
  if (!events?.length) return <p className="text-sm text-ink-3">No scheduled events found. Set FRED_API_KEY to add US data releases.</p>;
  return (
    <table className="w-full text-sm">
      <tbody className="divide-y divide-line/60">
        {events.map((e, i) => (
          <tr key={i}>
            <td className="num w-32 py-2 text-ink-2">{date(e.date, { weekday: 'short', day: 'numeric', month: 'short' })}</td>
            <td className="w-12 py-2 text-xs text-ink-3">{e.region}</td>
            <td className="py-2 text-ink">{e.event}{e.provisional && <span className="ml-2 text-[10px] uppercase text-ink-3">provisional</span>}</td>
            <td className="py-2 text-right text-xs text-ink-3">{e.type === 'central_bank' ? 'Central bank' : 'Data'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Speeches({ items }) {
  if (!items?.length) return <p className="text-sm text-ink-3">No speeches loaded. Feeds are fetched during the live morning run.</p>;
  return (
    <ul className="divide-y divide-line/60">
      {items.map((s, i) => (
        <li key={i} className="flex items-baseline gap-4 py-2.5">
          <span className="w-10 text-xs text-ink-3">{s.bank}</span>
          <a href={s.url} target="_blank" rel="noreferrer" className="flex-1 text-ink hover:underline">{s.title}</a>
          <span className="num text-xs text-ink-3">{date(s.date)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Drilldowns({ data }) {
  const p = data.panels;
  const panels = [
    ['bonds', 'Government bonds', () => <SeriesPanel rows={p.bonds.rows} compare initial={['US10Y', 'UK10Y', 'DE10Y']} />],
    ['curves', 'Yield curves', () => <CurvesPanel shapes={data.curve_shapes} curves={data.curves} />],
    ['ois', 'OIS curves & policy paths', () => <OisPanel policy={data.policy} />],
    ['inflation', 'Inflation', () => <SeriesPanel rows={p.inflation.rows} compare initial={['US10YBE', 'US10YREAL']} />],
    ['spreads', 'Cross-country spreads', () => <TimeSeriesChart ids={['US10_DE10', 'UK10_DE10', 'IT10_DE10']} />],
    ['fx', 'FX', () => <SeriesPanel rows={p.fx.rows} />],
    ['credit', 'Credit', () => <SeriesPanel rows={p.credit.rows.filter((r) => r.unit === 'bp')} compare />],
    ['equities', 'Equities', () => <SeriesPanel rows={p.equities.rows} />],
    ['commodities', 'Commodities', () => <SeriesPanel rows={p.commodities.rows} />],
    ['calendar', 'Economic calendar', () => <Calendar events={data.calendar} />],
    ['speeches', 'Central bank speeches', () => <Speeches items={data.speeches} />],
  ];
  const [open, setOpen] = useState({});
  return (
    <Section id="drilldown" index={13} question="Want the detail?" title="Drill-down panels">
      <div className="card divide-y divide-line">
        {panels.map(([key, title, render]) => (
          <div key={key}>
            <button type="button" onClick={() => setOpen((o) => ({ ...o, [key]: !o[key] }))}
              className="flex w-full items-center justify-between px-5 py-4 text-left hover:bg-raised/40" aria-expanded={!!open[key]}>
              <span className="text-[15px] text-ink">{title}</span>
              <span className={`text-ink-3 transition-transform ${open[key] ? 'rotate-90' : ''}`}>›</span>
            </button>
            {open[key] && <div className="px-5 pb-6 pt-1">{render()}</div>}
          </div>
        ))}
      </div>
    </Section>
  );
}
