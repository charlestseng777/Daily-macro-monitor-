// Every homepage section is framed as the question it answers.
export default function Section({ id, index, question, title, aside, children, className = '' }) {
  return (
    <section id={id} className={`scroll-mt-20 ${className}`}>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
        <div>
          <p className="eyebrow">
            {index != null && <span className="mr-2 text-ink-3/70 num">{String(index).padStart(2, '0')}</span>}
            {question}
          </p>
          <h2 className="mt-1 font-display text-xl font-semibold tracking-tight text-ink">{title}</h2>
        </div>
        {aside && <div className="min-w-0">{aside}</div>}
      </header>
      {children}
    </section>
  );
}
