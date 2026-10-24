// Thin fetch wrappers. All numbers arrive computed; the client only formats.
const BASE = import.meta.env.VITE_API_BASE_URL || '';

async function getJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${text.slice(0, 200)}`);
  }
  return res.json();
}

export const api = {
  dashboard: () => getJSON('/api/dashboard'),
  series: (id, range) => getJSON(`/api/series/${encodeURIComponent(id)}?range=${range}`),
  seriesMany: (ids, range) => getJSON(`/api/series?ids=${ids.map(encodeURIComponent).join(',')}&range=${range}`),
  flashcardsDue: () => getJSON('/api/flashcards/due'),
  review: (id, grade) =>
    fetch(`${BASE}/api/flashcards/${encodeURIComponent(id)}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grade }),
    }).then((r) => r.json()),
};
