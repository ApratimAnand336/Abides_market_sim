// Formatting helpers (spec 7.2). All grouping is en-US.

const OPEN_S = 9 * 3600 + 30 * 60;

const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

export const DASH = '—';

const ok = (v: number | null | undefined): v is number =>
  v !== null && v !== undefined && Number.isFinite(v);

/** `$1,000.63` */
export function fmtPrice(v: number | null | undefined): string {
  return ok(v) ? usd.format(v) : DASH;
}

/** `29,138` */
export function fmtInt(v: number | null | undefined): string {
  return ok(v) ? int.format(v) : DASH;
}

/** Signed with two decimals: `+12.34` */
export function fmtSigned(v: number | null | undefined, digits = 2): string {
  if (!ok(v)) return DASH;
  const s = Math.abs(v).toFixed(digits);
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

/** `12.34%` (value already in percent) */
export function fmtPct(v: number | null | undefined, digits = 2): string {
  return ok(v) ? `${v.toFixed(digits)}%` : DASH;
}

/** Signed percent: `+0.07%` */
export function fmtPctSigned(v: number | null | undefined, digits = 2): string {
  return ok(v) ? `${fmtSigned(v, digits)}%` : DASH;
}

/** `+12.4 bps` */
export function fmtBps(v: number | null | undefined, digits = 1): string {
  return ok(v) ? `${fmtSigned(v, digits)} bps` : DASH;
}

/** Price delta with arrow: `▲ $0.66 (0.07%)` */
export function fmtPriceDelta(change: number, pct: number): string {
  const arrow = change > 0 ? '▲' : change < 0 ? '▼' : '■';
  return `${arrow} ${usd.format(Math.abs(change))} (${Math.abs(pct).toFixed(2)}%)`;
}

/** Signed dollars: `+$12.30` */
export function fmtUsdSigned(v: number | null | undefined): string {
  if (!ok(v)) return DASH;
  const s = usd.format(Math.abs(v));
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

/** Tiny floats (v̂, K): 3 significant figures, scientific below 1e-3. */
export function fmtSci(v: number | null | undefined): string {
  if (!ok(v)) return DASH;
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a < 1e-3 || a >= 1e6) return v.toExponential(2).replace('e', 'e').replace('+', '');
  return Number(v.toPrecision(3)).toString();
}

/** Generic number with fixed decimals. */
export function fmtNum(v: number | null | undefined, digits = 2): string {
  return ok(v) ? v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : DASH;
}

/** `6.5 h`, `35 s`, `4.2 min` */
export function fmtDuration(sec: number | null | undefined): string {
  if (!ok(sec)) return DASH;
  if (sec < 90) return `${Math.round(sec)} s`;
  if (sec < 5400) return `${(sec / 60).toFixed(1).replace(/\.0$/, '')} min`;
  return `${(sec / 3600).toFixed(1).replace(/\.0$/, '')} h`;
}

/** mm:ss elapsed counter: `00:18` */
export function fmtElapsed(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

// ── clock time ───────────────────────────────────────────────────────────

function hms(total: number, withSeconds: boolean): string {
  const t = Math.round(total);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const hh = String(h).padStart(2, '0');
  const mm = String(m).padStart(2, '0');
  return withSeconds ? `${hh}:${mm}:${String(s).padStart(2, '0')}` : `${hh}:${mm}`;
}

/** Seconds since open -> `HH:MM` (axes). */
export function clockHM(t: number): string {
  return hms(OPEN_S + t, false);
}

/** Seconds since open -> `HH:MM:SS` (tooltips, readouts). */
export function clockHMS(t: number): string {
  return hms(OPEN_S + t, true);
}

/** `HH:MM:SS` offset -> seconds; NaN when malformed. */
export function parseHMS(s: string): number {
  const m = /^(\d{2}):(\d{2}):(\d{2})$/.exec(s.trim());
  if (!m) return NaN;
  const [h, mi, se] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (mi > 59 || se > 59) return NaN;
  return h * 3600 + mi * 60 + se;
}

/** Session close `HH:MM:SS` -> session duration in seconds. */
export function sessionSeconds(endTime: string): number {
  return parseHMS(endTime) - OPEN_S;
}

/** Compact axis label for prices, never wider than 8 characters. */
export function axisPrice(v: number): string {
  return `$${v.toFixed(2)}`.slice(0, 9);
}

/** Compact axis label for generic values, never wider than 8 characters. */
export function axisNum(v: number): string {
  const a = Math.abs(v);
  if (v === 0) return '0';
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e4) return `${(v / 1e3).toFixed(0)}k`;
  if (a >= 100) return v.toFixed(0);
  if (a >= 1) return v.toFixed(2);
  if (a >= 1e-3) return v.toFixed(3);
  return v.toExponential(1);
}

/** Escape text placed into ECharts HTML tooltips. */
export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
}
