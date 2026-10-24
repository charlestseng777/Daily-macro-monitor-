import Section from '../components/Section.jsx';

export default function Regions({ regions }) {
  return (
    <Section id="why" index={9} question="Why did it happen?" title="Region by region">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {regions.map((r) => (
          <article key={r.id} className="card p-5">
            <p className="eyebrow">{r.name}</p>
            <p className="mt-3 text-[15px] leading-relaxed text-ink-2">{r.text}</p>
          </article>
        ))}
      </div>
    </Section>
  );
}
