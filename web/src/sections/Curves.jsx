import Section from '../components/Section.jsx';
import Badge from '../components/Badge.jsx';
import Move from '../components/Move.jsx';
import Percentile from '../components/Percentile.jsx';
import Sparkline from '../components/Sparkline.jsx';
import Tooltip from '../components/Tooltip.jsx';

const REGION = { US: 'United States', UK: 'United Kingdom', DE: 'Germany', JP: 'Japan' };
const SHAPE_KIND = {
  bear_steepener: 'hawkish', bear_flattener: 'hawkish', bull_steepener: 'dovish', bull_flattener: 'dovish',
};

export default function Curves({ curves }) {
  const groups = Object.keys(REGION).map((r) => [r, curves.filter((c) => c.region === r)]).filter(([, l]) => l.length);
  return (
    <Section id="curves" index={5} question="What did the curves do?" title="Yield curves"
      aside={<span className="text-xs text-ink-3">Slopes in bp · shape = today's move</span>}>
      <div className="card overflow-x-auto px-5 py-3">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="table-head">
              <th className="py-2 text-left font-medium">Curve</th>
              <th className="py-2 text-right font-medium">Slope</th>
              <th className="py-2 text-right font-medium">1D</th>
              <th className="py-2 text-right font-medium">1W</th>
              <th className="py-2 pl-4 text-left font-medium">Today's shape</th>
              <th className="py-2 text-left font-medium">Week's shape</th>
              <th className="py-2 text-left font-medium">Hist. pctile</th>
              <th className="py-2 text-right font-medium">3M</th>
            </tr>
          </thead>
          {groups.map(([region, list]) => (
            <tbody key={region} className="divide-y divide-line/60">
              <tr><td colSpan={8} className="pb-1 pt-4 eyebrow">{REGION[region]}</td></tr>
              {list.map((c) => (
                <tr key={c.id}>
                  <td className="py-2.5 text-ink">{c.label}</td>
                  <td className={`num py-2.5 text-right font-medium ${c.inverted ? 'text-surprise' : 'text-ink'}`}>
                    {Math.round(c.last)}bp{c.inverted && <span className="ml-1 text-[10px] uppercase">inv</span>}
                  </td>
                  <td className="py-2.5 text-right"><Move value={c.d1} unit="bp" z={c.z_d1} /></td>
                  <td className="py-2.5 text-right"><Move value={c.w1} unit="bp" /></td>
                  <td className="py-2.5 pl-4">
                    <Tooltip content={<>{c.shape_d1_explain}<br /><span className="num">Front {c.front_d1 > 0 ? '+' : ''}{c.front_d1?.toFixed(1)}bp · back {c.back_d1 > 0 ? '+' : ''}{c.back_d1?.toFixed(1)}bp</span></>}>
                      <Badge kind={SHAPE_KIND[c.shape_d1] || 'neutral'}>{c.shape_d1_label}</Badge>
                    </Tooltip>
                  </td>
                  <td className="py-2.5 text-xs text-ink-2">{c.shape_w1_label}</td>
                  <td className="py-2.5"><Percentile value={c.pct_all} label="Historical percentile" /></td>
                  <td className="py-2.5 text-right"><Sparkline points={c.spark} width={72} height={22} /></td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </Section>
  );
}
