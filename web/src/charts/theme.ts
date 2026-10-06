// One chart theme for every chart (spec 5.5). Colours mirror styles/tokens.css.

import * as echarts from 'echarts';
import { axisNum, axisPrice, clockHM, clockHMS } from '../lib/format';

export const C = {
  bg: '#0A0F1C',
  card: '#111A2E',
  border: '#1E293B',
  borderStrong: '#334155',
  text: '#E2E8F0',
  muted: '#94A3B8',
  dim: '#64748B',
  accent: '#6366F1',
  up: '#10B981',
  down: '#F43F5E',
  mid: '#38BDF8',
  oracle: '#F59E0B',
  level: '#FB923C',
  band: 'rgba(251,146,60,0.14)',
  spread: '#A855F7',
  warn: '#FBBF24',
  crosshair: '#475569',
  tooltipBg: '#0B1220',
  pink: '#F472B6',
};

// Per-agent overlay colours, assigned by agent order (fundamental first, then
// momentum), never by rank, so filtering never repaints an agent.
export const AGENT_PALETTE = [
  '#F472B6', '#A78BFA', '#34D399', '#FBBF24', '#60A5FA',
  '#F87171', '#2DD4BF', '#C084FC', '#FDE047', '#4ADE80',
];

export const STATE_COLORS: Record<string, string> = {
  BULL: C.up,
  BEAR: C.down,
  WATCH: C.warn,
  NEUTRAL: C.dim,
};

export const MONO = "'JetBrains Mono', ui-monospace, monospace";

echarts.registerTheme('finverse', {
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'Inter', system-ui, sans-serif", color: C.muted },
  animationThreshold: 1000, // animation off for series over 1000 points
});

const AXIS_LABEL = { color: C.dim, fontFamily: MONO, fontSize: 11 };
const SPLIT_LINE = { lineStyle: { color: C.border, type: 'dashed' as const } };

/** x axis = clock time, seconds since open in [0, duration]. Every time chart
 *  uses the same domain so connected zoom (by percent) lines up exactly. */
export function timeAxis(duration: number, extra: Record<string, unknown> = {}) {
  return {
    type: 'value' as const,
    min: 0,
    max: duration,
    interval: pickInterval(duration),
    axisLabel: { ...AXIS_LABEL, formatter: (v: number) => clockHM(v), hideOverlap: true },
    axisLine: { lineStyle: { color: C.border } },
    axisTick: { show: false },
    splitLine: SPLIT_LINE,
    axisPointer: {
      label: { formatter: (p: { value: number }) => clockHMS(p.value), fontFamily: MONO, backgroundColor: C.borderStrong },
    },
    ...extra,
  };
}

function pickInterval(duration: number): number {
  if (duration <= 1800) return 300; // 5 min
  if (duration <= 3 * 3600) return 1800; // 30 min
  return 3600; // 1 h
}

type Fmt = 'price' | 'num' | ((v: number) => string);

export function valueAxis(fmt: Fmt = 'num', extra: Record<string, unknown> = {}) {
  const formatter = fmt === 'price' ? axisPrice : fmt === 'num' ? axisNum : fmt;
  return {
    type: 'value' as const,
    scale: true,
    axisLabel: { ...AXIS_LABEL, formatter },
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: SPLIT_LINE,
    ...extra,
  };
}

export function categoryAxis(data: (string | number)[], extra: Record<string, unknown> = {}) {
  return {
    type: 'category' as const,
    data,
    axisLabel: { ...AXIS_LABEL },
    axisLine: { lineStyle: { color: C.border } },
    axisTick: { show: false },
    ...extra,
  };
}

export const TOOLTIP_BASE = {
  backgroundColor: C.tooltipBg,
  borderColor: C.borderStrong,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: C.text, fontFamily: MONO, fontSize: 12 },
  extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,.45); border-radius: 8px;',
};

export function axisTooltip(formatter: (params: any) => string, extra: Record<string, unknown> = {}) {
  return {
    ...TOOLTIP_BASE,
    trigger: 'axis' as const,
    axisPointer: { type: 'cross' as const, lineStyle: { color: C.crosshair, type: 'dashed' as const }, crossStyle: { color: C.crosshair } },
    formatter,
    ...extra,
  };
}

export function itemTooltip(formatter: (params: any) => string) {
  return { ...TOOLTIP_BASE, trigger: 'item' as const, formatter };
}

/** HTML for a tooltip: a title row then coloured-swatch rows. */
export function tipHtml(title: string, rows: { color?: string; label: string; value: string }[]): string {
  const body = rows
    .map(
      (r) =>
        `<div style="display:flex;justify-content:space-between;gap:16px;line-height:18px">` +
        `<span style="color:${C.muted}">${r.color ? `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${r.color};margin-right:6px"></span>` : ''}${r.label}</span>` +
        `<span>${r.value}</span></div>`,
    )
    .join('');
  return `<div style="font-weight:700;margin-bottom:4px">${title}</div>${body}`;
}

/** Inside (wheel / drag) zoom on the shared x axis. */
export function insideZoom() {
  return [{ type: 'inside' as const, xAxisIndex: 'all' as const, filterMode: 'none' as const, zoomOnMouseWheel: true, moveOnMouseMove: true }];
}

/** Inside zoom plus a slider under the chart (main chart only). */
export function sliderZoom() {
  return [
    ...insideZoom(),
    {
      type: 'slider' as const,
      xAxisIndex: 'all' as const,
      filterMode: 'none' as const,
      height: 22,
      bottom: 6,
      borderColor: C.border,
      backgroundColor: 'rgba(15,23,42,0.6)',
      fillerColor: 'rgba(99,102,241,0.18)',
      dataBackground: { lineStyle: { color: C.dim }, areaStyle: { color: 'rgba(100,116,139,0.15)' } },
      handleStyle: { color: C.accent, borderColor: C.accent },
      textStyle: { color: C.dim, fontFamily: MONO, fontSize: 10 },
      labelFormatter: (v: number) => clockHM(v),
    },
  ];
}

export function grid(extra: Record<string, unknown> = {}) {
  return { left: 64, right: 20, top: 16, bottom: 28, containLabel: false, ...extra };
}

/** Pairs [x, y] for a columnar series (skipping nulls). */
export function pairs(t: number[], v: (number | null | undefined)[]): [number, number | null][] {
  const out: [number, number | null][] = new Array(t.length);
  for (let i = 0; i < t.length; i++) out[i] = [t[i], v[i] ?? null];
  return out;
}

/** Step series [x, y] from change points, extended to `end`. */
export function stepPairs(t: number[], v: number[], end: number): [number, number][] {
  const out: [number, number][] = t.map((x, i) => [x, v[i]]);
  if (t.length && t[t.length - 1] < end) out.push([end, v[v.length - 1]]);
  return out;
}

/** Robust y-domain from percentiles with padding (spec 6.3.2 item 3). */
export function robustDomain(values: number[], lo = 0.005, hi = 0.995, pad = 0.15): [number, number] {
  const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return [0, 1];
  const q = (p: number) => v[Math.min(v.length - 1, Math.max(0, Math.round(p * (v.length - 1))))];
  const a = q(lo);
  const b = q(hi);
  const span = b - a || Math.abs(a) * 0.001 || 1;
  return [a - span * pad, b + span * pad];
}
