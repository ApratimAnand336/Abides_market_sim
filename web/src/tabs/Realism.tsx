// Realism tab (spec v1.3 Part 9): this run graded against the provisional
// large-cap bands, the 20-seed lab baseline when it exists, and diagnostics.
// Grades are words (PASS / WARN / FAIL) with a symbol, never colour alone.

import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { useQuery } from '@tanstack/react-query';
import { FlaskConical, Gauge, Microscope } from 'lucide-react';
import type { Band, Grade, LabAgg, LabGrade, LabSummary, SimPayload } from '../types/payload';
import { api, ApiError } from '../lib/api';
import { EChart } from '../charts/EChart';
import { C, TOOLTIP_BASE, categoryAxis, grid, tipHtml, valueAxis } from '../charts/theme';
import { fmtNum } from '../lib/format';
import { Card, SectionHeader } from '../components/ui/Card';
import { Tooltip } from '../components/ui/Tooltip';
import { cn } from '../lib/cn';

const GRADE_STYLE: Record<string, string> = {
  PASS: 'border-up/40 bg-up/10 text-emerald-300',
  WARN: 'border-warn/40 bg-warn/10 text-amber-200',
  FAIL: 'border-down/40 bg-down/10 text-rose-300',
  INCOMPLETE: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
};
const GRADE_ICON: Record<string, string> = { PASS: '✓', WARN: '!', FAIL: '✕', INCOMPLETE: '…' };

export function GradeChip({ grade }: { grade: Grade | 'INCOMPLETE' | 'N/A' | null | undefined }) {
  if (!grade || grade === 'N/A') {
    return <span className="font-mono text-[11px] text-dim">n/a</span>;
  }
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-[8px] border px-2 py-0.5 font-mono text-[11px] font-bold', GRADE_STYLE[grade])}>
      <span aria-hidden>{GRADE_ICON[grade]}</span>
      {grade}
    </span>
  );
}

type Metrics = SimPayload['realism']['metrics'];
const num = (m: Metrics, k: string): number | null => {
  const v = m[k];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
};

function digitsFor(v: number): number {
  const a = Math.abs(v);
  return a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
}
function fmtVal(v: number | null | undefined, unit: string): string {
  if (v == null || !Number.isFinite(v)) return '—';
  const s = fmtNum(v, digitsFor(v));
  if (unit === '$') return `$${s}`;
  if (unit === '%') return `${s}%`;
  if (unit === '×') return `${s}×`;
  return unit ? `${s} ${unit}` : s;
}

/** The value text of one band for a dict of metric values (G5, G8 have two). */
function bandValue(b: Band, get: (k: string) => number | null): string {
  if (b.rule === 'clustering') return `CS ${fmtVal(get('cs'), '')} · PS ${fmtVal(get('ps'), '')}`;
  // spec v1.4.1: G8 is in bps of the mid; the band carries its metric keys and unit
  if (b.rule === 'spread') {
    const [mk, pk] = b.metrics ?? ['spread_med_bps', 'spread_p95_bps'];
    return `median ${fmtVal(get(mk), '')} · p95 ${fmtVal(get(pk), '')} ${b.unit}`;
  }
  const v = get(b.key);
  if (b.id === 'G10' && v == null) return 'none (no lag qualifies)';
  return fmtVal(b.transform === 'abs' && v != null ? Math.abs(v) : v, b.unit);
}

export function Realism({ payload }: { payload: SimPayload }) {
  const { bands, metrics, grades } = payload.realism;
  const runBands = bands.filter((b) => b.scope === 'run');
  const lab = useQuery<LabSummary, ApiError>({
    queryKey: ['lab-summary'],
    queryFn: api.labSummary,
    retry: false,
    staleTime: 5 * 60_000,
  });

  return (
    <div className="space-y-6">
      <ThisRun bands={runBands} metrics={metrics} grades={grades} duration={payload.meta.session.duration_s} />
      {lab.data && <LabBaseline bands={bands} summary={lab.data} />}
      <Diagnostics metrics={metrics} />
    </div>
  );
}

function ThisRun({ bands, metrics, grades, duration }: { bands: Band[]; metrics: Metrics; grades: Record<string, Grade | null>; duration: number }) {
  const counts = { PASS: 0, WARN: 0, FAIL: 0 } as Record<string, number>;
  Object.values(grades).forEach((g) => g && (counts[g] += 1));
  return (
    <Card>
      <SectionHeader
        icon={Gauge}
        title="This run"
        caption={`${counts.PASS} pass · ${counts.WARN} warn · ${counts.FAIL} fail`}
      />
      <p className="mb-4 text-[13px] text-muted">
        Single run — the 20-seed lab report is the authoritative grade. Bands are provisional, taken from a liquid large-cap stock that
        moves about 1–2% a day (owner decision D-R2-1, 2026-10-11).
        {duration < 23400 && ' This session is shorter than a full day, so the day-level metrics are noisier or missing.'}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="micro px-3 py-2 font-semibold">#</th>
              <th className="micro px-3 py-2 font-semibold">Metric</th>
              <th className="micro px-3 py-2 text-right font-semibold">This run</th>
              <th className="micro px-3 py-2 font-semibold">Band</th>
              <th className="micro px-3 py-2 font-semibold">Grade</th>
            </tr>
          </thead>
          <tbody>
            {bands.map((b) => (
              <tr key={b.id} className="border-b border-border/60 last:border-0">
                <td className="px-3 py-2 font-mono text-dim">{b.id}</td>
                <td className="px-3 py-2 text-text">
                  <Tooltip text={b.note}>
                    <span tabIndex={0} className="cursor-help border-b border-dotted border-dim">
                      {b.label}
                    </span>
                  </Tooltip>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">{bandValue(b, (k) => num(metrics, k))}</td>
                <td className="px-3 py-2 font-mono text-[12px] text-muted">{b.text}</td>
                <td className="px-3 py-2">
                  <GradeChip grade={grades[b.id]} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function aggText(a: LabAgg | undefined, unit: string): string {
  if (!a || a.median == null) return '—';
  return `${fmtVal(a.median, unit)} [${fmtVal(a.p10, '')}–${fmtVal(a.p90, '')}]`;
}

function LabBaseline({ bands, summary }: { bands: Band[]; summary: LabSummary }) {
  const cfg = summary.configs['C-DEF'];
  if (!cfg) return null;
  const sc = cfg.scorecard;
  const rows = bands.filter((b) => b.scope === 'run' || b.id === 'G2');
  const labText = (b: Band, g: LabGrade | undefined): string => {
    if (!g) return '—';
    if (b.id === 'G2') {
      const v = (g.stats as { value: number | null; n_seeds: number }).value;
      return `${fmtVal(v, '%')} (std over ${(g.stats as { n_seeds: number }).n_seeds} seeds)`;
    }
    const st = g.stats as Record<string, LabAgg>;
    if (b.rule === 'clustering') return `CS ${aggText(st.cs, '')} · PS ${aggText(st.ps, '')}`;
    if (b.rule === 'spread') {
      const [mk, pk] = b.metrics ?? ['spread_med_bps', 'spread_p95_bps'];
      return `median ${aggText(st[mk], '')} · p95 ${aggText(st[pk], '')} ${b.unit}`;
    }
    return aggText(st[b.key], b.unit);
  };
  const imp = summary.impact;
  return (
    <Card>
      <SectionHeader
        icon={FlaskConical}
        title="Lab baseline (20 seeds)"
        caption={`C-DEF · ${cfg.n_runs} runs · ${cfg.dates.join(', ')} · ${cfg.engine_versions.join(', ')}`}
      />
      <p className="mb-4 text-[13px] text-muted">
        The default market (97 value agents, 20 + 12 of our agents, full day) over {summary.seeds.length} seeds: median [p10–p90]. The grade
        is that of the median; pass share is how many seeds pass on their own.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="micro px-3 py-2 font-semibold">#</th>
              <th className="micro px-3 py-2 font-semibold">Metric</th>
              <th className="micro px-3 py-2 text-right font-semibold">Median [p10–p90]</th>
              <th className="micro px-3 py-2 font-semibold">Grade</th>
              <th className="micro px-3 py-2 text-right font-semibold">Pass share</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => {
              const g = sc[b.id];
              return (
                <tr key={b.id} className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2 font-mono text-dim">{b.id}</td>
                  <td className="px-3 py-2 text-text">{b.label}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">{labText(b, g)}</td>
                  <td className="px-3 py-2">
                    <GradeChip grade={g?.grade ?? null} />
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-muted">{g?.pass_share == null ? '—' : `${Math.round(100 * g.pass_share)}%`}</td>
                </tr>
              );
            })}
            {imp && (
              <>
                <tr className="border-b border-border/60">
                  <td className="px-3 py-2 font-mono text-dim">G12</td>
                  <td className="px-3 py-2 text-text">Impact exponent β</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">
                    {fmtVal(imp.G12.value, '')}
                    {imp.G12.ci && ` (90% CI ${fmtNum(imp.G12.ci[0], 2)}–${fmtNum(imp.G12.ci[1], 2)})`}
                  </td>
                  <td className="px-3 py-2">
                    <GradeChip grade={imp.G12.grade} />
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-muted">—</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-mono text-dim">G13</td>
                  <td className="px-3 py-2 text-text">Impact recovery I_perm / I_peak (1% order)</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">{fmtVal(imp.G13.value, '')}</td>
                  <td className="px-3 py-2">
                    <GradeChip grade={imp.G13.grade} />
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-muted">—</td>
                </tr>
              </>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Diagnostics({ metrics }: { metrics: Metrics }) {
  const ac = (metrics.ac_1_5 as number[] | undefined) ?? [];
  const acAbs = (metrics.acf_abs as number[] | undefined) ?? [];
  const band = num(metrics, 'ac_band');

  const option = useMemo<EChartsOption>(() => {
    const bandLine = (y: number) => ({ yAxis: y, lineStyle: { color: C.muted, type: 'dashed' as const }, label: { show: false } });
    return {
      grid: grid({ left: 48, bottom: 40, right: 16, top: 16 }),
      xAxis: categoryAxis(acAbs.map((_, i) => String(i + 1)), {
        name: 'lag (minutes)',
        nameLocation: 'middle',
        nameGap: 26,
        nameTextStyle: { color: C.dim, fontSize: 11 },
      }),
      yAxis: valueAxis((v: number) => v.toFixed(2)),
      tooltip: {
        ...TOOLTIP_BASE,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (ps: any) =>
          tipHtml(`lag ${ps[0].name} min`, [
            { label: 'acf of |r|', value: fmtNum(ps[0].value, 3), color: C.level },
            ...(band ? [{ label: '±2/√n band', value: `±${fmtNum(band, 3)}` }] : []),
          ]),
      },
      series: [
        {
          type: 'bar',
          name: 'acf |r|',
          data: acAbs,
          itemStyle: { color: C.level, borderRadius: 2 },
          markLine: band ? { silent: true, symbol: ['none', 'none'], data: [bandLine(band), bandLine(-band)] } : undefined,
        },
      ],
    };
  }, [acAbs, band]);

  const rows: [string, string, string][] = [
    ['Price / value volatility ratio', fmtVal(num(metrics, 'vol_ratio_price_value'), ''), 'Std of 1-min price returns / std of 1-min true-value changes. Below 1: the price is smoother than the value it follows.'],
    ['Variance ratio VR(5)', fmtVal(num(metrics, 'vr5'), ''), 'Var of 5-min returns / (5 × var of 1-min returns). 1 = random walk; above 1 = the price trails a target.'],
    ['Variance ratio VR(30)', fmtVal(num(metrics, 'vr30'), ''), 'The same over 30 minutes.'],
    ['Intraday U-shape (u_ratio)', fmtVal(num(metrics, 'u_ratio'), ''), 'Volume in the first and last half hour vs the middle of the day (full days only). Real markets: well above 1.'],
    ['corr(mid, true value)', fmtVal(num(metrics, 'corr_mid_value'), ''), 'Pearson correlation of the price and the true value on a 1 s grid.'],
    ['Trend share', fmtVal(num(metrics, 'trend_share'), ''), 'Share of 30-minute windows that move more than twice the day\'s median 30-minute move.'],
  ];

  return (
    <Card>
      <SectionHeader icon={Microscope} title="Diagnostics" caption="reported, not graded" />
      <div className="grid gap-6 xl:grid-cols-2">
        <div>
          <table className="w-full text-[13px]">
            <tbody>
              {rows.map(([k, v, why]) => (
                <tr key={k} className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2 text-text">
                    <Tooltip text={why}>
                      <span tabIndex={0} className="cursor-help border-b border-dotted border-dim">
                        {k}
                      </span>
                    </Tooltip>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">{v}</td>
                </tr>
              ))}
              <tr>
                <td className="px-3 py-2 text-text">Return autocorrelation, lags 1–5</td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">
                  {ac.length ? ac.map((x) => fmtNum(x, 2)).join(', ') : '—'}
                  {band != null && <span className="text-muted"> (band ±{fmtNum(band, 3)})</span>}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div>
          <p className="mb-2 font-mono text-[11px] text-muted">Autocorrelation of |1-min returns|, lags 1–30 (volatility clustering)</p>
          {acAbs.length ? (
            <EChart option={option} height={220} ariaLabel="Autocorrelation of absolute 1-minute returns, lags 1 to 30" />
          ) : (
            <p className="text-[13px] text-dim">Not enough 1-minute returns in this session.</p>
          )}
        </div>
      </div>
    </Card>
  );
}
