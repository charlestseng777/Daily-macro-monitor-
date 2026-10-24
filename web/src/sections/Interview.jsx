import { useState } from 'react';
import Section from '../components/Section.jsx';

// Active recall: think of your answer before revealing the model one.
export default function Interview({ questions }) {
  const [open, setOpen] = useState({});
  return (
    <Section id="interview" index={11} question="Could I answer this in an interview?" title="Interview mode"
      aside={<span className="text-xs text-ink-3">Answer out loud first, then reveal</span>}>
      <ol className="space-y-3">
        {questions.map((q, i) => (
          <li key={q.id} className="card px-5 py-4">
            <div className="flex items-start gap-4">
              <span className="num mt-0.5 text-sm text-ink-3">Q{i + 1}</span>
              <div className="flex-1">
                <p className="text-[11px] uppercase tracking-wider text-ink-3">{q.topic}</p>
                <p className="mt-1 text-lg leading-snug text-ink">{q.question}</p>
                {open[q.id] && <p className="mt-3 border-l-2 border-line pl-4 text-[15px] leading-relaxed text-ink-2">{q.answer}</p>}
              </div>
              <button type="button" onClick={() => setOpen((o) => ({ ...o, [q.id]: !o[q.id] }))}
                className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-xs text-ink-2 hover:bg-raised hover:text-ink">
                {open[q.id] ? 'Hide answer' : 'Reveal answer'}
              </button>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}
