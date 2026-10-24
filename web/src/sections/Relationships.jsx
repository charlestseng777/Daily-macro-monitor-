import Section from '../components/Section.jsx';
import Badge from '../components/Badge.jsx';

const STATUS = { held: 'Relationship held', broke: 'Relationship broke', signal: 'Signal' };

export default function Relationships({ relationships }) {
  return (
    <Section id="relationships" index={10} question="How do the moves connect?" title="Market relationships"
      aside={<span className="text-xs text-ink-3">Amber = textbook link broke today, worth explaining</span>}>
      <div className="card divide-y divide-line">
        {relationships.length === 0 && <p className="p-5 text-sm text-ink-3">No relationship had both legs move enough to be meaningful today.</p>}
        {relationships.map((r) => (
          <details key={r.id} className="group px-5 py-4">
            <summary className="flex items-start gap-3 sm:gap-4">
              <span className="mt-1 hidden w-28 shrink-0 text-[11px] uppercase tracking-wider text-ink-3 sm:block">{r.topic}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[17px] leading-snug text-ink">{r.statement}</span>
                <span className="num mt-1 block text-xs text-ink-3">{r.evidence}</span>
              </span>
              <Badge kind={r.status}>{STATUS[r.status]}</Badge>
              <span className="mt-1 text-ink-3 transition-transform group-open:rotate-90">›</span>
            </summary>
            <p className="mt-3 sm:ml-32 max-w-3xl text-sm leading-relaxed text-ink-2">{r.lesson}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}
