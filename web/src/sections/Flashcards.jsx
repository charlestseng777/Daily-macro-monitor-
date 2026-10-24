import { useEffect, useState } from 'react';
import Section from '../components/Section.jsx';
import { api } from '../lib/api.js';

// Spaced repetition: scheduling (SM-2) runs on the server; this deck shows
// what is due and posts the grade.
const GRADES = [
  { g: 0, label: 'Again', hint: 'Forgot' },
  { g: 3, label: 'Hard', hint: 'Slow recall' },
  { g: 4, label: 'Good', hint: 'Recalled' },
  { g: 5, label: 'Easy', hint: 'Instant' },
];

export default function Flashcards({ fallback }) {
  const [cards, setCards] = useState(null);
  const [stats, setStats] = useState(null);
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [done, setDone] = useState(0);

  useEffect(() => {
    api.flashcardsDue()
      .then((d) => { setCards(d.cards.length ? d.cards : []); setStats(d.stats); })
      .catch(() => setCards(fallback.map((c) => ({ ...c, offline: true }))));
  }, []);

  const card = cards?.[i];
  const grade = async (g) => {
    if (card && !card.offline) await api.review(card.id, g).catch(() => {});
    setFlipped(false);
    setDone((d) => d + 1);
    setI((x) => x + 1);
  };

  return (
    <Section id="flashcards" index={12} question="Will I remember this next week?" title="Flashcards"
      aside={stats && <span className="num text-xs text-ink-3">{stats.due} due · {stats.total} in deck · {stats.mature} mature</span>}>
      <div className="card p-6">
        {!cards && <div className="h-40 animate-pulse rounded-xl bg-raised/40" />}
        {cards && !card && (
          <div className="py-10 text-center">
            <p className="text-lg text-ink">{done ? `Done: ${done} reviewed.` : 'Nothing due.'}</p>
            <p className="mt-1 text-sm text-ink-3">New cards arrive with each morning's data; reviewed cards come back on a growing interval.</p>
          </div>
        )}
        {card && (
          <div>
            <div className="flex items-center justify-between text-xs text-ink-3">
              <span className="uppercase tracking-wider">{card.topic}</span>
              <span className="num">{i + 1} / {cards.length}</span>
            </div>
            <button type="button" onClick={() => setFlipped((f) => !f)}
              className="mt-4 block min-h-[150px] w-full rounded-xl border border-line bg-page/60 px-6 py-8 text-left transition-colors hover:border-ink-3/40">
              <p className="font-display text-2xl leading-snug text-ink">{card.front}</p>
              {flipped ? (
                <p className="mt-5 border-t border-line pt-5 text-lg leading-relaxed text-ink-2">{card.back}</p>
              ) : (
                <p className="mt-5 text-sm text-ink-3">Recall the answer, then click to reveal.</p>
              )}
            </button>
            {flipped && (
              <div className="mt-4 grid grid-cols-4 gap-2">
                {GRADES.map((x) => (
                  <button key={x.g} type="button" onClick={() => grade(x.g)}
                    className="rounded-lg border border-line px-3 py-2 text-sm text-ink hover:bg-raised">
                    {x.label}<span className="block text-[11px] text-ink-3">{x.hint}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}
