// Reusable series builders for the clock-time (value) x axis.

import type { NewsRecord } from '../types/payload';
import { C } from './theme';

export interface Candle {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  volume: number;
  trades: number;
}

/** Aggregate 1-minute candles into k-minute candles: o = first, h = max,
 *  l = min, c = last, volume and trades summed. The only client-side maths
 *  the spec allows. */
export function aggregateCandles(c1: { t: number[]; o: number[]; h: number[]; l: number[]; c: number[]; volume: number[]; trades: number[] }, k: number): Candle[] {
  const out: Candle[] = [];
  for (let i = 0; i < c1.t.length; i += k) {
    const j = Math.min(c1.t.length, i + k);
    let h = -Infinity;
    let l = Infinity;
    let volume = 0;
    let trades = 0;
    for (let x = i; x < j; x++) {
      h = Math.max(h, c1.h[x]);
      l = Math.min(l, c1.l[x]);
      volume += c1.volume[x];
      trades += c1.trades[x];
    }
    out.push({ t: c1.t[i], o: c1.o[i], h, l, c: c1.c[j - 1], volume, trades });
  }
  return out;
}

/** Candlesticks as a custom series (works on the shared value x axis). */
export function candleSeries(candles: Candle[], intervalS: number): any {
  return {
    type: 'custom' as const,
    name: 'Candles',
    clip: true,
    encode: { x: 0, y: [1, 2, 3, 4] },
    data: candles.map((c) => [c.t, c.o, c.c, c.l, c.h]),
    renderItem: (_: unknown, api: any) => {
      const x = api.value(0);
      const o = api.value(1);
      const cl = api.value(2);
      const lo = api.value(3);
      const hi = api.value(4);
      const left = api.coord([x, o])[0];
      const right = api.coord([x + intervalS, o])[0];
      const cx = (left + right) / 2;
      const w = Math.max(1, (right - left) * 0.68);
      const yO = api.coord([x, o])[1];
      const yC = api.coord([x, cl])[1];
      const yH = api.coord([x, hi])[1];
      const yL = api.coord([x, lo])[1];
      const color = cl >= o ? C.up : C.down;
      return {
        type: 'group',
        children: [
          { type: 'line', shape: { x1: cx, y1: yH, x2: cx, y2: yL }, style: { stroke: color, lineWidth: 1 } },
          {
            type: 'rect',
            shape: { x: cx - w / 2, y: Math.min(yO, yC), width: w, height: Math.max(1, Math.abs(yO - yC)) },
            style: { fill: color },
          },
        ],
      };
    },
    z: 3,
  };
}

/** Bars spanning [t, t + interval) on the value axis (volume etc.). */
export function intervalBarSeries(name: string, t: number[], v: number[], intervalS: number, colorAt: (i: number) => string): any {
  return {
    type: 'custom' as const,
    name,
    clip: true,
    encode: { x: 0, y: 1 },
    data: t.map((x, i) => [x, v[i], i]),
    renderItem: (_: unknown, api: any) => {
      const x = api.value(0);
      const y = api.value(1);
      const i = api.value(2);
      const [left, top] = api.coord([x, y]);
      const [right, base] = api.coord([x + intervalS, 0]);
      const gap = Math.min(2, (right - left) * 0.2); // 2px surface gap between bars
      return {
        type: 'rect',
        shape: { x: left + gap / 2, y: top, width: Math.max(1, right - left - gap), height: Math.max(0, base - top), r: [2, 2, 0, 0] },
        style: { fill: colorAt(i) },
      };
    },
  };
}

/** Filled band between two series (bid/ask, ±2σ) as one polygon. */
export function bandSeries(name: string, t: number[], lo: number[], hi: number[], fill: string): any {
  return {
    type: 'custom' as const,
    name,
    silent: true,
    clip: true,
    z: 1,
    data: [[t[0] ?? 0, lo[0] ?? 0]],
    encode: { x: 0, y: 1 },
    renderItem: (_: unknown, api: any) => {
      const pts: number[][] = [];
      for (let i = 0; i < t.length; i++) pts.push(api.coord([t[i], hi[i]]));
      for (let i = t.length - 1; i >= 0; i--) pts.push(api.coord([t[i], lo[i]]));
      return { type: 'polygon', shape: { points: pts }, style: { fill } };
    },
  };
}

/** Vertical dashed news lines with a sentiment flag label. */
export function newsMarkLine(news: NewsRecord[]): any {
  return {
    silent: true,
    symbol: ['none', 'none'],
    animation: false,
    data: news.map((n) => ({
      xAxis: n.t,
      lineStyle: { color: n.sentiment >= 0 ? C.up : C.down, type: 'dashed' as const, width: 1.5 },
      label: {
        show: true,
        position: 'insideEndTop' as const,
        formatter: `${n.sentiment >= 0 ? '▲ +' : '▼ −'}${Math.abs(n.sentiment).toFixed(2)}`,
        color: n.sentiment >= 0 ? C.up : C.down,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
        fontWeight: 700 as const,
        backgroundColor: 'rgba(10,15,28,0.85)',
        padding: [2, 4],
        borderRadius: 4,
      },
    })),
  };
}

/** Index of the last element of a sorted array <= x (or -1). */
export function bisectRight(arr: number[], x: number): number {
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo - 1;
}

/** News items within `window` seconds of t (for tooltips). */
export function newsNear(news: NewsRecord[], t: number, window: number): NewsRecord[] {
  return news.filter((n) => Math.abs(n.t - t) <= window);
}

// ── Off-scale overlays (spec v1.1 D1) ──────────────────────────────────────

export interface OffScaleMarker {
  t: number; // time of the run's largest excursion
  v: number; // its true (off-scale) value
  edge: 'top' | 'bottom';
  label: string; // series / agent label for the tooltip
  color: string;
}

/** Break an overlay line where it leaves the y-domain instead of clipping it
 *  (clipping draws vertical streaks along the plot edge). Off-scale points
 *  become null (use with connectNulls: false); each contiguous off-scale run
 *  gets one marker at the axis edge, placed at the run's largest excursion. */
export function clipToDomain(
  t: number[],
  v: (number | null)[],
  domain: [number, number],
  label = '',
  color = C.muted,
): { data: [number, number | null][]; markers: OffScaleMarker[] } {
  const data: [number, number | null][] = new Array(t.length);
  const markers: OffScaleMarker[] = [];
  let run: OffScaleMarker | null = null;
  for (let i = 0; i < t.length; i++) {
    const x = v[i];
    const edge = x === null || x === undefined ? null : x > domain[1] ? 'top' : x < domain[0] ? 'bottom' : null;
    if (edge === null) {
      data[i] = [t[i], x ?? null];
      run = null;
      continue;
    }
    data[i] = [t[i], null];
    const dist = edge === 'top' ? x! - domain[1] : domain[0] - x!;
    if (run && run.edge === edge) {
      const runDist = edge === 'top' ? run.v - domain[1] : domain[0] - run.v;
      if (dist > runDist) {
        run.t = t[i];
        run.v = x!;
      }
    } else {
      run = { t: t[i], v: x!, edge, label, color };
      markers.push(run);
    }
  }
  return { data, markers };
}

/** Scatter series drawing off-scale markers at the axis edge: a triangle
 *  pointing up at the top, down at the bottom. */
export function offScaleMarkerSeries(markers: OffScaleMarker[], domain: [number, number], name = 'off-scale'): any {
  return {
    type: 'scatter' as const,
    name,
    silent: true,
    clip: false,
    z: 6,
    symbolSize: 9,
    data: markers.map((m) => ({
      value: [m.t, m.edge === 'top' ? domain[1] : domain[0]],
      symbol: 'triangle',
      symbolRotate: m.edge === 'top' ? 0 : 180,
      symbolOffset: [0, m.edge === 'top' ? 5 : -5], // keep the triangle inside the plot
      itemStyle: { color: m.color, borderColor: C.card, borderWidth: 1 },
    })),
  };
}

/** Markers within `window` seconds of t, for an axis tooltip. */
export function markersNear(markers: OffScaleMarker[], t: number, window: number): OffScaleMarker[] {
  return markers.filter((m) => Math.abs(m.t - t) <= window);
}
