import Section from '../components/Section.jsx';
import Badge from '../components/Badge.jsx';
import { LevelTable } from './Numbers.jsx';
import { signed } from '../lib/format.js';

const DRIVER = { inflation: 'Inflation expectations', real: 'Real yields', both: 'Both', offsetting: 'Offsetting', none: 'No real move', unknown: 'n/a' };
const REGION = { US: 'United States', UK: 'United Kingdom', DE: 'Germany' };

export default function Inflation({ inflation }) {
  const daily = inflation.attribution.filter((a) => a.horizon === 'd1');
  const weekly = Object.fromEntries(inflation.attribution.filter((a) => a.horizon === 'w1').map((a) => [a.region, a]));
  return (
    <Section id="inflation" index={8} question="Real yields or inflation expectations?" title="Inflation & real rates">
      {inflation.headline && <p className="mb-4 max-w-3xl text-lg leading-relaxed text-ink-2">{inflation.headline}</p>}
      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <div className="card min-w-0 overflow-x-auto px-5 py-4">
          <p className="eyebrow mb-1">Breakevens, real yields and inflation swaps</p>
          <LevelTable rows={inflation.rows} />
          {inflation.forwards?.map((f) => (
            <p key={f.id} className="mt-3 text-xs text-ink-3">
              {f.label}: <span className="num text-ink">{f.last?.toFixed(2)}%</span>
              <span className="num"> ({signed(f.d1, 0, 'bp')} 1D, {signed(f.m1, 0, 'bp')} 1M)</span>. The long-run anchoring gauge.
            </p>
          ))}
        </div>
        <div className="card min-w-0 overflow-x-auto px-5 py-4">
          <p className="eyebrow mb-3">10Y nominal move decomposed</p>
          <ul className="space-y-4">
            {daily.map((a) => {
              const total = Math.abs(a.d_real ?? 0) + Math.abs(a.d_be ?? 0) || 1;
              return (
                <li key={a.region}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-ink">{REGION[a.region]}</span>
                    <Badge kind={a.driver === 'inflation' ? 'inflation' : a.driver === 'real' ? 'dovish' : 'neutral'}>{DRIVER[a.driver]}</Badge>
                  </div>
                  {a.d_real != null && (
                    <>
                      <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-line">
                        <span className="bg-up" style={{ width: `${(Math.abs(a.d_real) / total) * 100}%` }} />
                        <span className="ml-[2px] bg-surprise" style={{ width: `${(Math.abs(a.d_be) / total) * 100}%` }} />
                      </div>
                      <p className="num mt-1.5 text-xs text-ink-3">
                        Nominal {signed(a.d_nominal, 1, 'bp')} = <span className="text-up">real {signed(a.d_real, 1, 'bp')}</span> + <span className="text-surprise">breakeven {signed(a.d_be, 1, 'bp')}</span>
                        {weekly[a.region]?.driver && <> · week: {DRIVER[weekly[a.region].driver].toLowerCase()}</>}
                      </p>
                    </>
                  )}
                </li>
              );
            })}
            {!daily.length && <li className="text-sm text-ink-3">Breakeven data unavailable.</li>}
          </ul>
        </div>
      </div>
    </Section>
  );
}
