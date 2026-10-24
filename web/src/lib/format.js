// Presentation only: sign, rounding and units for numbers the API computed.

const MINUS = '−';

export function signed(x, digits = 0, unit = '') {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  const r = Number(x).toFixed(digits);
  if (Number(r) === 0) return `0${unit}`;
  return (x > 0 ? '+' : MINUS) + Math.abs(Number(r)).toFixed(digits) + unit;
}

export function move(x, unit) {
  if (unit === 'bp') return signed(x, 0, 'bp');
  if (unit === '%') return signed(x, Math.abs(x) >= 10 ? 1 : 2, '%');
  return signed(x, 1, '');
}

export function level(x, unit, kind) {
  if (x === null || x === undefined) return '—';
  if (unit === 'bp' || kind === 'bp') return `${Math.round(x)}bp`;
  if (kind === 'yield' || kind === 'rate' || unit === 'pct') return `${Number(x).toFixed(x < 10 && Math.abs(x) < 2 ? 3 : 2)}%`;
  const a = Math.abs(x);
  const d = a >= 1000 ? 0 : a >= 100 ? 2 : a >= 10 ? 2 : 4;
  return Number(x).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
}

// Yields / spreads are stored in percent; credit OAS shown in bp.
export function levelFor(row) {
  if (!row || row.last === null || row.last === undefined) return '—';
  if (row.unit === 'bp') {
    return row.asset_class === 'credit' ? `${Math.round(row.last * 100)}bp` : `${Number(row.last).toFixed(2)}%`;
  }
  return level(row.last, row.unit);
}

export function pctile(p) {
  if (p === null || p === undefined) return '—';
  return `${Math.round(p)}`;
}

export function tone(x, threshold = 0) {
  if (x === null || x === undefined || Math.abs(x) <= threshold) return 'flat';
  return x > 0 ? 'up' : 'down';
}

export function date(iso, opts = { day: 'numeric', month: 'short' }) {
  if (!iso) return '';
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-GB', opts);
}

export const REGION_FLAG = { US: 'US', UK: 'UK', EA: 'EA', DE: 'DE', JP: 'JP', CN: 'CN', GLOBAL: 'GL', FR: 'FR', IT: 'IT', ES: 'ES' };
