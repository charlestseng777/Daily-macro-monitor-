import Section from '../components/Section.jsx';
import Move from '../components/Move.jsx';
import Percentile from '../components/Percentile.jsx';
import Sparkline from '../components/Sparkline.jsx';

const GROUP = { core: '10Y core spreads', front: '2Y spreads: policy divergence', periphery: 'Peripheral Europe vs Bunds' };

export default function RelativeValue({ spreads }) {
  return (
    <Section id="rv" index={6} question="Where is the relative value?" title="Cross-country spreads"
      aside={<span className="text-xs text-ink-3">Signal = z-score vs 3M mean</span>}>
      <div className="card overflow-x-auto px-5 py-3">
        <table className="w-full min-w-[700px] text-sm">
          <thead>
            <tr className="table-head">
              <th className="py-2 text-left font-medium">Spread</th>
              <th className="py-2 text-right font-medium">Current</th>
              <th className="py-2 text-right font-medium">1D</th>
              <th className="py-2 text-right font-medium">1M</th>
              <th className="py-2 pl-4 text-left font-medium">1M pctile</th>
              <th className="py-2 text-left font-medium">1Y pctile</th>
              <th className="py-2 text-left font-medium">Signal</th>
              <th className="py-2 text-right font-medium">3M</th>
            </tr>
          </thead>
          {Object.entries(GROUP).map(([g, label]) => {
            const list = spreads.filter((s) => s.group === g);
            if (!list.length) return null;
            return (
              <tbody key={g} className="divide-y divide-line/60">
                <tr><td colSpan={8} className="pb-1 pt-4 eyebrow">{label}</td></tr>
                {list.map((s) => (
                  <tr key={s.id}>
                    <td className="py-2.5 text-ink">{s.label}</td>
                    <td className="num py-2.5 text-right font-medium text-ink">{Math.round(s.last)}bp</td>
                    <td className="py-2.5 text-right"><Move value={s.d1} unit="bp" z={s.z_d1} /></td>
                    <td className="py-2.5 text-right"><Move value={s.m1} unit="bp" /></td>
                    <td className="py-2.5 pl-4"><Percentile value={s.pct_1m} label="1M percentile" /></td>
                    <td className="py-2.5"><Percentile value={s.pct_1y} /></td>
                    <td className={`py-2.5 text-xs ${s.signal === 'in range' ? 'text-ink-3' : 'text-surprise'}`}>
                      {s.signal}{s.z_3m != null && <span className="num text-ink-3"> ({s.z_3m > 0 ? '+' : ''}{s.z_3m.toFixed(1)}z)</span>}
                    </td>
                    <td className="py-2.5 text-right"><Sparkline points={s.spark} width={72} height={22} /></td>
                  </tr>
                ))}
              </tbody>
            );
          })}
        </table>
      </div>
    </Section>
  );
}
