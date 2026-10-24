import { useEffect, useState } from 'react';
import { api } from './lib/api.js';
import { date } from './lib/format.js';
import RegimeHero from './sections/RegimeHero.jsx';
import Movers from './sections/Movers.jsx';
import Heatmap from './sections/Heatmap.jsx';
import Numbers from './sections/Numbers.jsx';
import Curves from './sections/Curves.jsx';
import RelativeValue from './sections/RelativeValue.jsx';
import Policy from './sections/Policy.jsx';
import Inflation from './sections/Inflation.jsx';
import Regions from './sections/Regions.jsx';
import Relationships from './sections/Relationships.jsx';
import Interview from './sections/Interview.jsx';
import Flashcards from './sections/Flashcards.jsx';
import Drilldowns from './sections/Drilldowns.jsx';

const NAV = [
  ['regime', 'Regime'], ['movers', 'Movers'], ['numbers', 'Levels'], ['curves', 'Curves'], ['rv', 'Spreads'],
  ['policy', 'Policy'], ['inflation', 'Inflation'], ['why', 'Why'], ['relationships', 'Links'],
  ['interview', 'Interview'], ['flashcards', 'Cards'], ['drilldown', 'Detail'],
];

function Header({ meta }) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-page/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-page items-center gap-6 px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <svg width="20" height="20" viewBox="0 0 32 32" aria-hidden="true"><path d="M6 22 L12 14 L17 18 L26 8" stroke="#fab219" strokeWidth="3.2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span className="font-display text-[15px] font-semibold tracking-tight">Macro Morning</span>
        </div>
        <nav className="hidden flex-1 items-center gap-1 overflow-x-auto lg:flex" aria-label="Sections">
          {NAV.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="rounded-md px-2.5 py-1 text-[13px] text-ink-3 hover:bg-raised hover:text-ink">{label}</a>
          ))}
        </nav>
        {meta && (
          <div className="ml-auto flex items-center gap-3 text-xs text-ink-3">
            {meta.mode === 'demo' && <span className="rounded-full border border-surprise/60 bg-surprise/10 px-2.5 py-0.5 font-semibold text-surprise">DEMO DATA</span>}
            <span className="num">As of {date(meta.as_of, { day: 'numeric', month: 'short', year: 'numeric' })}</span>
          </div>
        )}
      </div>
    </header>
  );
}

function DataNotes({ meta }) {
  const failed = Object.keys(meta.failed_sources || {});
  return (
    <footer className="mx-auto max-w-page px-4 sm:px-6 pb-16 pt-4 text-xs leading-relaxed text-ink-3">
      <p>
        Generated {new Date(meta.generated_at).toLocaleString('en-GB')} in {meta.build_ms}ms. Every figure is computed by the
        backend from stored history. Commentary is {meta.llm?.used ? 'drafted from those figures and restyled by Claude under a numbers-must-match check' : 'generated deterministically from those figures'}.
        Not investment advice.
      </p>
      {meta.stale?.length > 0 && <p className="mt-1">Stale (last print over 3 days old): {meta.stale.join(', ')}.</p>}
      {failed.length > 0 && <p className="mt-1">Unavailable today: {failed.join(', ')}.</p>}
    </footer>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <>
        <Header />
        <main className="mx-auto max-w-2xl px-4 sm:px-6 py-24">
          <h1 className="font-display text-3xl font-semibold">No snapshot available</h1>
          <p className="mt-3 text-ink-2">The API answered: <span className="num text-ink-3">{error}</span></p>
          <p className="mt-6 text-sm text-ink-3">Start the backend with <code className="text-ink">python -m macrodash serve</code> after a pipeline run (<code className="text-ink">python -m macrodash run</code>, or <code className="text-ink">run --demo</code> for labelled synthetic data).</p>
        </main>
      </>
    );
  }
  if (!data) {
    return (
      <>
        <Header />
        <main className="mx-auto max-w-page space-y-6 px-4 sm:px-6 py-12">
          <div className="h-16 w-2/3 animate-pulse rounded-xl bg-surface" />
          <div className="h-24 w-full animate-pulse rounded-xl bg-surface" />
          <div className="grid gap-4 md:grid-cols-2"><div className="h-72 animate-pulse rounded-2xl bg-surface" /><div className="h-72 animate-pulse rounded-2xl bg-surface" /></div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header meta={data.meta} />
      {data.meta.mode === 'demo' && (
        <div className="border-b border-surprise/30 bg-surprise/10 px-4 sm:px-6 py-2 text-center text-xs text-surprise">
          Demo mode: synthetic data from the built-in generator, for development only. Run the live pipeline for real markets.
        </div>
      )}
      <main className="mx-auto max-w-page space-y-16 px-4 sm:px-6 pb-8 pt-10">
        <RegimeHero regime={data.regime} meta={data.meta} />
        <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1fr_1.15fr] [&>*]:min-w-0">
          <Movers movers={data.movers} />
          <Heatmap heatmap={data.heatmap} />
        </div>
        <Numbers numbers={data.numbers} />
        <Curves curves={data.curves} />
        <RelativeValue spreads={data.spreads} />
        <Policy policy={data.policy} />
        <Inflation inflation={data.inflation} />
        <Regions regions={data.regions} />
        <Relationships relationships={data.relationships} />
        <Interview questions={data.interview} />
        <Flashcards fallback={data.flashcards} />
        <Drilldowns data={data} />
      </main>
      <DataNotes meta={data.meta} />
    </>
  );
}
