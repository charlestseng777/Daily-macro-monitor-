import { move, tone } from '../lib/format.js';

// A signed move. Colour only when the move is unusual (|z| >= 1) or when
// `always` is set; otherwise ink, so colour keeps its meaning.
export default function Move({ value, unit, z, always = false, className = '' }) {
  const t = tone(value);
  const colour = always || (z !== undefined && z !== null && Math.abs(z) >= 1) ? `tone-${t}` : 'text-ink-2';
  return <span className={`num ${colour} ${className}`}>{move(value, unit)}</span>;
}
