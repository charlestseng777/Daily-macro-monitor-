// Data access. Two modes, chosen at build time:
//  * API mode (default): talks to the FastAPI backend.
//  * Static mode (VITE_STATIC=1, used for GitHub Pages): reads files the
//    daily job exported. Series files carry each timeframe's start index and
//    statistics, so switching timeframe is a slice, not a calculation.
const BASE = import.meta.env.VITE_API_BASE_URL || '';
export const STATIC = import.meta.env.VITE_STATIC === '1';
const DATA = `${import.meta.env.BASE_URL}data`;

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${text.slice(0, 200)}`);
  }
  return res.json();
}

const seriesCache = new Map();
async function staticSeries(id, range) {
  if (!seriesCache.has(id)) seriesCache.set(id, getJSON(`${DATA}/series/${encodeURIComponent(id)}.json`));
  const s = await seriesCache.get(id);
  const r = s.ranges[range];
  return { ...s, range, points: s.points.slice(r.start_index), range_stats: r };
}

export const api = {
  dashboard: () => (STATIC ? getJSON(`${DATA}/dashboard.json`) : getJSON(`${BASE}/api/dashboard`)),
  series: (id, range) => (STATIC ? staticSeries(id, range) : getJSON(`${BASE}/api/series/${encodeURIComponent(id)}?range=${range}`)),
  seriesMany: (ids, range) => (STATIC
    ? Promise.all(ids.map((id) => staticSeries(id, range))).then((series) => ({ series }))
    : getJSON(`${BASE}/api/series?ids=${ids.map(encodeURIComponent).join(',')}&range=${range}`)),
  flashcardsDue: () => (STATIC ? Promise.reject(new Error('static')) : getJSON(`${BASE}/api/flashcards/due`)),
  review: (id, grade) =>
    fetch(`${BASE}/api/flashcards/${encodeURIComponent(id)}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grade }),
    }).then((r) => r.json()),
};
