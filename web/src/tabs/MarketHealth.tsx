import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { Activity, AlertTriangle, BarChart3, CheckCircle2, ListChecks, Ruler, Sigma, Table2, Waves } from 'lucide-react';
import type { SimPayload } from '../types/payload';
import { EChart } from '../charts/EChart';
import { C, TOOLTIP_BASE, categoryAxis, grid, tipHtml, valueAxis } from '../charts/theme';
import { fmtBps, fmtInt, fmtNum, fmtPct, fmtPrice, fmtSigned, fmtUsdSigned } from '../lib/format';
import { useQueryFlag } from '../lib/urlState';
import { Card, LegendItem, SectionHeader } from '../components/ui/Card';
import { KpiCard } from '../components/ui/KpiCard';
import { Toggle } from '../components/ui/controls';
import { PopulationCard } from '../components/health/PopulationCard';
import { PriceVsValue } from '../components/health/PriceVsValue';
import { cn } from '../lib/cn';

const toBps = (r: number) => r * 1e4;

export function MarketHealth({ payload }: { payload: SimPayload }) {
  const s = payload.stats;
  const r = s.returns_1m;
  const [histLog, setHistLog] = useQueryFlag('histLog', false);
  const [spreadLog, setSpreadLog] = useQueryFlag('spreadLog', false);

  // ── stylised facts ──────────────────────────────────────────────────────
  const facts = useMemo(() => {
    const clusterHits = r.acf_abs.slice(0, 5).filter((v) => v > r.acf_band).length;
    return [
      {
        name: 'Fat tails',
        pass: r.excess_kurtosis > 0,
        value: `excess kurtosis ${fmtNum(r.excess_kurtosis, 2)}`,
        threshold: '> 0',
        why: 'Real returns have more extreme moves than a normal distribution.',
      },
      {
        name: 'No linear return autocorrelation',
        pass: Math.abs(r.acf[0] ?? 0) < r.acf_band,
        value: `|ACF lag 1| ${fmtNum(Math.abs(r.acf[0] ?? 0), 3)}`,
        threshold: `< ${fmtNum(r.acf_band, 3)} (95% band)`,
        why: 'Past returns should not predict the next return in an efficient market.',
      },
      {
        name: 'Volatility clustering',
        pass: clusterHits >= 3,
        value: `${clusterHits} of 5 lags of |r| above band`,
        threshold: '≥ 3 of lags 1–5',
        why: 'Large moves tend to follow large moves.',
      },
      {
        name: 'Prices track fundamentals',
        pass: s.tracking.corr > 0.9,
        value: `corr(mid, oracle) ${fmtNum(s.tracking.corr, 3)}`,
        threshold: '> 0.90',
        why: 'The traded price should follow the (hidden) fundamental value.',
      },
    ];
  }, [r, s.tracking.corr]);

  // ── return distribution ─────────────────────────────────────────────────
  const histOption = useMemo<EChartsOption>(() => {
    const e = r.hist.edges.map(toBps);
    const counts = r.hist.counts;
    const width = e.length > 1 ? e[1] - e[0] : 1;
    return {
      grid: grid({ left: 52, bottom: 40, right: 16 }),
      xAxis: valueAxis((v: number) => `${fmtSigned(v, 1)}`, {
        min: e[0],
        max: e[e.length - 1],
        scale: false,
        name: '1-min log return (bps)',
        nameLocation: 'middle',
        nameGap: 26,
        nameTextStyle: { color: C.dim, fontSize: 11 },
      }),
      yAxis: histLog
        ? valueAxis((v: number) => fmtInt(v), { type: 'log', min: 1, scale: false })
        : valueAxis((v: number) => fmtInt(v), { min: 0, scale: false, minInterval: 1 }),
      tooltip: {
        ...TOOLTIP_BASE,
        trigger: 'item',
        formatter: (p: any) =>
          p.seriesName === 'Normal'
            ? tipHtml('Normal fit', [{ label: 'expected', value: fmtNum(p.value[1], 1) }])
            : tipHtml(`${fmtBps(p.value[0])} … ${fmtBps(p.value[0] + width)}`, [{ label: 'count', value: fmtInt(p.value[1]) }]),
      },
      series: [
        {
          type: 'custom',
          name: 'Returns',
          encode: { x: 0, y: 1 },
          data: counts.map((c, i) => [e[i], histLog && c === 0 ? null : c]),
          renderItem: (_: unknown, api: any) => {
            const v = api.value(1);
            if (v === null || Number.isNaN(v)) return null;
            const x0 = api.value(0);
            const [l, top] = api.coord([x0, v]);
            const [rr] = api.coord([x0 + width, v]);
            const base = api.coord([x0, histLog ? 1 : 0])[1];
            return {
              type: 'rect',
              shape: { x: l + 1, y: top, width: Math.max(1, rr - l - 2), height: Math.max(0, base - top), r: [2, 2, 0, 0] },
              style: { fill: 'rgba(56,189,248,0.75)' },
            };
          },
        } as any,
        {
          type: 'line',
          name: 'Normal',
          data: r.normal.x.map((x, i) => [toBps(x), histLog ? Math.max(r.normal.y[i], 1e-3) : r.normal.y[i]]),
          showSymbol: false,
          lineStyle: { color: C.warn, width: 1.5, type: 'dashed' },
          z: 3,
        },
      ],
    };
  }, [r, histLog]);

  // ── spread distribution ─────────────────────────────────────────────────
  const spreadOption = useMemo<EChartsOption>(() => {
    const labels = s.spread_ticks.ticks.map((t, i) => (i === s.spread_ticks.ticks.length - 1 ? `≥${t}¢` : `${t}¢`));
    const pct = s.spread_ticks.share.map((x) => x * 100);
    return {
      grid: grid({ left: 52, bottom: 28, right: 16, top: 24 }),
      xAxis: categoryAxis(labels),
      yAxis: spreadLog
        ? valueAxis((v: number) => `${v}%`, { type: 'log', min: 0.01, scale: false })
        : valueAxis((v: number) => `${v}%`, { min: 0, scale: false }),
      tooltip: { ...TOOLTIP_BASE, trigger: 'item', formatter: (p: any) => tipHtml(`spread ${p.name}`, [{ label: 'share of quotes', value: fmtPct(p.value, 2) }]) },
      series: [
        {
          type: 'bar',
          data: pct.map((v) => (spreadLog && v === 0 ? null : v)),
          barMaxWidth: 36,
          itemStyle: { color: C.spread, borderRadius: [4, 4, 0, 0] },
          label: {
            show: true,
            position: 'top',
            color: C.muted,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            formatter: (p: any) => (p.value >= 10 ? `${p.value.toFixed(0)}%` : p.value >= 0.1 ? `${p.value.toFixed(1)}%` : p.value > 0 ? '<0.1%' : ''),
          },
        },
      ],
    };
  }, [s.spread_ticks, spreadLog]);

  // ── autocorrelation ─────────────────────────────────────────────────────
  const acfOption = useMemo<EChartsOption>(() => {
    const lags = r.acf.map((_, i) => String(i + 1));
    const band = r.acf_band;
    const bandLine = (y: number) => ({ yAxis: y, lineStyle: { color: C.muted, type: 'dashed' as const }, label: { show: false } });
    return {
      grid: grid({ left: 52, bottom: 40, right: 16 }),
      xAxis: categoryAxis(lags, { name: 'lag (minutes)', nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: C.dim, fontSize: 11 } }),
      yAxis: valueAxis((v: number) => v.toFixed(2)),
      tooltip: {
        ...TOOLTIP_BASE,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (ps: any) =>
          tipHtml(`lag ${ps[0].name} min`, [
            ...ps.map((p: any) => ({ label: p.seriesName, value: fmtNum(p.value, 3), color: p.color })),
            { label: '95% band', value: `±${fmtNum(band, 3)}` },
          ]),
      },
      series: [
        {
          type: 'bar',
          name: 'returns r',
          data: r.acf,
          barGap: '10%',
          itemStyle: { color: C.mid, borderRadius: 2 },
          markLine: { silent: true, symbol: ['none', 'none'], data: [bandLine(band), bandLine(-band)] },
        },
        { type: 'bar', name: '|returns|', data: r.acf_abs, itemStyle: { color: C.level, borderRadius: 2 } },
      ],
    };
  }, [r]);

  const passCount = facts.filter((f) => f.pass).length;

  const summary: [string, string, string][] = [
    ['Open', fmtPrice(s.open), 'First mid-price of the session (09:30)'],
    ['Close', fmtPrice(s.close), 'Last mid-price of the session'],
    ['Change', `${fmtUsdSigned(s.change)} (${fmtSigned(s.change_pct, 3)}%)`, 'Close minus open'],
    ['Low / High', `${fmtPrice(s.low)} / ${fmtPrice(s.high)}`, 'Session range of the mid-price'],
    ['Trades executed', fmtInt(s.trades), 'Executions recorded by the exchange'],
    ['Volume', `${fmtInt(s.volume_shares)} shares`, 'Total shares traded'],
    ['Price points', fmtInt(payload.market.totals.price_points), 'Two-sided order-book quote updates'],
    ['Spread mean / median', `${fmtNum(s.spread.mean * 100, 2)}¢ / ${fmtNum(s.spread.median * 100, 1)}¢`, 'Best ask minus best bid'],
    ['Spread p95 / max', `${fmtNum(s.spread.p95 * 100, 1)}¢ / ${fmtNum(s.spread.max * 100, 0)}¢`, 'Tail of the spread distribution'],
    ['1-min returns (n)', fmtInt(r.n), 'Number of 1-minute log returns'],
    ['1-min return mean', fmtBps(toBps(r.mean), 2), 'Average 1-minute log return'],
    ['1-min return std', fmtBps(toBps(r.std), 2).replace('+', ''), 'Standard deviation of 1-minute log returns'],
    ['1-min skewness', fmtNum(r.skew, 3), 'Asymmetry of 1-minute returns (0 = symmetric)'],
    ['1-min excess kurtosis', fmtNum(r.excess_kurtosis, 3), 'Tail heaviness vs normal (0 = normal)'],
    ['Tick return std (tick-level, reference)', fmtBps(toBps(s.returns_tick.std), 3).replace('+', ''), 'Quote-to-quote; dominated by zero changes'],
    ['Tick excess kurtosis (tick-level, reference)', fmtNum(s.returns_tick.excess_kurtosis, 1), 'Microstructure noise inflates this; not a fat-tail measure'],
    ['Tracking error RMS', fmtPrice(s.tracking.rms), 'Root-mean-square of mid minus oracle fundamental'],
    ['Tracking mean |error|', fmtPrice(s.tracking.mean_abs), 'Average absolute gap between mid and oracle'],
    ['Correlation (mid, oracle)', fmtNum(s.tracking.corr, 4), 'How closely the price follows the fundamental'],
  ];

  return (
    <div className="flex flex-col gap-6">
      <PopulationCard rows={payload.population} />
      <PriceVsValue payload={payload} />

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard label="Excess kurtosis (1-min)" value={fmtNum(r.excess_kurtosis, 2)} caption="Fat tails if > 0; normal = 0" icon={Sigma} iconClass="text-spread" />
        <KpiCard label="Skewness (1-min)" value={fmtSigned(r.skew, 3)} caption="0 = symmetric returns" icon={Activity} />
        <KpiCard label="Return std (1-min)" value={`${fmtNum(toBps(r.std), 2)} bps`} caption={`over ${fmtInt(r.n)} one-minute returns`} icon={Waves} iconClass="text-mid" />
        <KpiCard label="RMS tracking error" value={fmtPrice(s.tracking.rms)} caption="Mid vs oracle fundamental" icon={Ruler} iconClass="text-oracle" />
      </div>

      <Card>
        <SectionHeader icon={ListChecks} title="Stylised facts" caption={`${passCount} of ${facts.length} real-market properties reproduced`} iconClass="text-up" />
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {facts.map((f) => (
            <li key={f.name} className={cn('flex gap-3 rounded-[10px] border p-3.5', f.pass ? 'border-up/30 bg-up/5' : 'border-warn/40 bg-warn/5')}>
              {f.pass ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-up" aria-hidden /> : <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warn" aria-hidden />}
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 text-[13px] font-semibold text-text">
                  {f.name}
                  <span className={cn('rounded-[8px] px-1.5 py-0.5 font-mono text-[10px] font-bold', f.pass ? 'bg-up/15 text-emerald-300' : 'bg-warn/15 text-amber-200')}>
                    {f.pass ? 'PASS' : 'WARN'}
                  </span>
                </p>
                <p className="mt-0.5 font-mono text-[12px] text-text">
                  {f.value} <span className="text-dim">· threshold {f.threshold}</span>
                </p>
                <p className="mt-0.5 text-[12px] text-muted">{f.why}</p>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <SectionHeader
            icon={BarChart3}
            title="Return distribution (1-min log returns)"
            caption={`${r.hist.counts.filter((c) => c > 0).length} non-empty bins · ±4σ`}
            right={<Toggle checked={histLog} onChange={setHistLog} label="Log y-axis" />}
          />
          <div className="mb-2 flex gap-4">
            <LegendItem color="rgba(56,189,248,0.9)" label="observed" />
            <LegendItem color={C.warn} label="normal with same mean and std" dashed />
          </div>
          {r.n < 3 ? (
            <p className="py-10 text-center text-[13px] text-muted">Not enough 1-minute returns in this session.</p>
          ) : (
            <EChart option={histOption} height={280} ariaLabel="Histogram of one-minute log returns with a normal curve overlaid" />
          )}
        </Card>
        <Card>
          <SectionHeader icon={Ruler} title="Spread distribution" caption="Share of quote updates by spread (cents)" right={<Toggle checked={spreadLog} onChange={setSpreadLog} label="Log y-axis" />} iconClass="text-spread" />
          <EChart option={spreadOption} height={300} ariaLabel="Distribution of the bid-ask spread in ticks" />
        </Card>
      </div>

      <Card>
        <SectionHeader icon={Waves} title="Autocorrelation" caption="1-min returns vs absolute returns, lags 1–20; dashed = 95% band (±1.96/√n)" iconClass="text-mid" />
        <div className="mb-2 flex gap-4">
          <LegendItem color={C.mid} label="returns r (should stay inside the band)" />
          <LegendItem color={C.level} label="|returns| (above the band = volatility clustering)" />
        </div>
        <EChart option={acfOption} height={260} ariaLabel="Autocorrelation of one-minute returns and absolute returns for lags 1 to 20" />
      </Card>

      <Card>
        <SectionHeader icon={Table2} title="Market summary statistics" />
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <caption className="sr-only">Market summary statistics</caption>
            <thead>
              <tr className="border-b border-border text-left">
                <th className="micro px-3 py-2 font-semibold">Metric</th>
                <th className="micro px-3 py-2 text-right font-semibold">Simulated value</th>
                <th className="micro px-3 py-2 font-semibold">Description</th>
              </tr>
            </thead>
            <tbody>
              {summary.map(([m, v, d]) => (
                <tr key={m} className="border-b border-border/60">
                  <td className="px-3 py-2 text-text">{m}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-text">{v}</td>
                  <td className="px-3 py-2 text-muted">{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
