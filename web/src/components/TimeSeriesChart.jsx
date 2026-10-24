import { useEffect, useRef, useState } from 'react';
import { ColorType, CrosshairMode, LineSeries, createChart } from 'lightweight-charts';
import { api } from '../lib/api.js';
import { date, move } from '../lib/format.js';
import RangeSelector from './RangeSelector.jsx';

// Categorical slots for the dark surface, in validated order (never cycled).
export const SERIES_COLOURS = ['#3987e5', '#d95926', '#199e70', '#c98500'];

function formatter(unit) {
  if (unit === 'bp') return (v) => `${v.toFixed(0)}bp`;
  if (unit === '%') return (v) => `${v.toFixed(2)}%`;
  return (v) => (Math.abs(v) >= 1000 ? v.toLocaleString('en-GB', { maximumFractionDigits: 0 }) : v.toFixed(Math.abs(v) >= 10 ? 2 : 4));
}

/**
 * Interactive time-series chart: drag to pan, wheel/pinch to zoom, crosshair
 * tooltip, timeframe selector. All series on one chart share one unit and one
 * axis; mixed units are never overlaid.
 */
export default function TimeSeriesChart({ ids, height = 320, defaultRange = '1Y', title }) {
  const box = useRef(null);
  const chartRef = useRef(null);
  const [range, setRange] = useState(defaultRange);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    let live = true;
    setError(null);
    api.seriesMany(ids, range).then((d) => live && setData(d.series)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [ids.join(','), range]);

  useEffect(() => {
    if (!box.current || !data) return undefined;
    const chart = createChart(box.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#898781',
        fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif',
        fontSize: 11,
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: '#202125' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderColor: '#26272b', rightOffset: 2, fixLeftEdge: true, fixRightEdge: true },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { color: '#5a5a58', labelBackgroundColor: '#26272b' },
        horzLine: { color: '#5a5a58', labelBackgroundColor: '#26272b' },
      },
      handleScroll: true,
      handleScale: true,
    });
    chartRef.current = chart;
    const unit = data[0]?.unit === 'bp' ? 'bp' : data[0]?.unit === '%' ? '%' : '';
    const handles = data.map((s, i) => {
      const line = chart.addSeries(LineSeries, {
        color: SERIES_COLOURS[i % SERIES_COLOURS.length],
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: '#141518',
        crosshairMarkerBorderWidth: 2,
        priceFormat: { type: 'custom', formatter: formatter(unit), minMove: 0.0001 },
      });
      line.setData(s.points.map((p) => ({ time: p.t, value: p.v })));
      return line;
    });
    chart.timeScale().fitContent();
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) { setHover(null); return; }
      setHover({
        time: param.time,
        values: handles.map((h) => param.seriesData.get(h)?.value),
      });
    });
    return () => { chart.remove(); chartRef.current = null; };
  }, [data]);

  const unit = data?.[0]?.unit === 'bp' ? 'bp' : data?.[0]?.unit === '%' ? '%' : '';
  const fmt = formatter(unit);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
          {title && <span className="text-sm font-medium text-ink">{title}</span>}
          {data?.map((s, i) => (
            <span key={s.id} className="inline-flex items-center gap-2 text-xs text-ink-2">
              <span className="h-0.5 w-4 rounded-full" style={{ background: SERIES_COLOURS[i] }} />
              {s.label}
              <span className="num text-ink">
                {hover ? (hover.values[i] !== undefined ? fmt(hover.values[i]) : '—') : fmt(s.points.at(-1)?.v ?? 0)}
              </span>
              {!hover && s.range_stats?.change != null && (
                <span className="num text-ink-3">{move(s.range_stats.change, s.move_unit)} over {range}</span>
              )}
            </span>
          ))}
          {hover && <span className="num text-xs text-ink-3">{date(hover.time, { day: 'numeric', month: 'short', year: 'numeric' })}</span>}
        </div>
        <RangeSelector value={range} onChange={setRange} />
      </div>
      <div className="relative" style={{ height }}>
        {error && <p className="absolute inset-0 grid place-items-center text-sm text-ink-3">Could not load series: {error}</p>}
        {!data && !error && <div className="absolute inset-0 animate-pulse rounded-xl bg-raised/40" />}
        <div ref={box} className="h-full w-full" />
      </div>
      <p className="mt-2 text-[11px] text-ink-3">Drag to pan · scroll or pinch to zoom · double-click an axis to reset</p>
    </div>
  );
}
