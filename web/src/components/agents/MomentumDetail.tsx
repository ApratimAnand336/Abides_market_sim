import { useMemo, type ReactNode } from 'react';
import type { EChartsOption } from 'echarts';
import { Activity, Banknote, Gauge, Layers, LineChart, Rocket, ShieldCheck, Workflow } from 'lucide-react';
import type { MomentumAgent, SimPayload } from '../../types/payload';
import { EChart } from '../../charts/EChart';
import { C, STATE_COLORS, axisTooltip, categoryAxis, grid, insideZoom, pairs, timeAxis, tipHtml, valueAxis } from '../../charts/theme';
import { bandSeries, bisectRight } from '../../charts/series';
import { clockHMS, fmtInt, fmtNum, fmtPct, fmtPrice, fmtSci, fmtSigned } from '../../lib/format';
import { MOMENTUM_PARAMS } from '../../config/agentParams';
import { currentState } from '../../lib/agents';
import { useQueryFlag } from '../../lib/urlState';
import { Card, LegendItem, SectionHeader } from '../ui/Card';
import { KpiCard } from '../ui/KpiCard';
import { VsHoldKpi } from './VsHoldKpi';
import { Select, Toggle } from '../ui/controls';
import { StateBadge } from '../ui/Badge';
import { EmptyState } from '../ui/feedback';
import { PersonalityProfile } from './PersonalityProfile';
import { CashInventory } from './CashInventory';

const GROUP = 'agents';
const STATES_TOP_DOWN = ['BULL', 'NEUTRAL', 'WATCH', 'BEAR'];
const REASON_SYMBOL: Record<string, { symbol: string; label: string; color: string; size: number }> = {
  BREAKOUT: { symbol: 'triangle', label: '▲ breakout', color: '#34D399', size: 10 },
  REENTRY: { symbol: 'diamond', label: '◆ re-entry', color: '#60A5FA', size: 10 },
  FADE: { symbol: 'emptyCircle', label: '○ fade', color: '#FBBF24', size: 9 },
  STOP: { symbol: 'rect', label: '■ stop', color: '#F43F5E', size: 9 },
  TIMEOUT: { symbol: 'circle', label: '· timeout', color: '#94A3B8', size: 5 },
};
const SHADE: Record<string, string> = { BULL: 'rgba(16,185,129,0.08)', BEAR: 'rgba(244,63,94,0.08)', WATCH: 'rgba(251,191,36,0.06)' };

/** State intervals [start, end, state] from the transitions; NEUTRAL from warm-up. */
function stateIntervals(a: MomentumAgent, duration: number): [number, number, string][] {
  if (a.warmup_end_t === null) return [];
  const out: [number, number, string][] = [];
  let t0 = a.warmup_end_t;
  let s = 'NEUTRAL';
  for (const tr of a.states) {
    out.push([t0, tr.t, s]);
    t0 = tr.t;
    s = tr.to;
  }
  out.push([t0, duration, s]);
  return out;
}

export function MomentumDetail({
  payload,
  agent,
  color,
  onSelect,
}: {
  payload: SimPayload;
  agent: MomentumAgent;
  color: string;
  onSelect: (id: number) => void;
}) {
  const duration = payload.meta.session.duration_s;
  const kf = agent.kf;
  const [shade, setShade] = useQueryFlag('regimes', true);
  const intervals = useMemo(() => stateIntervals(agent, duration), [agent, duration]);
  const state = currentState(agent);
  const lastC = agent.caution.C.length ? agent.caution.C[agent.caution.C.length - 1] : null;

  const stateAt = (t: number) => {
    for (const [a, b, s] of intervals) if (t >= a && t <= b) return s;
    return agent.warmup_end_t !== null && t < agent.warmup_end_t ? 'warming up' : '—';
  };

  const levelOption = useMemo<EChartsOption>(() => {
    const markArea = shade
      ? {
          silent: true,
          data: intervals.filter(([, , s]) => SHADE[s]).map(([a, b, s]) => [{ xAxis: a, itemStyle: { color: SHADE[s] } }, { xAxis: b }]),
        }
      : undefined;
    const lo = Math.min(...kf.band_lo, ...kf.mid);
    const hi = Math.max(...kf.band_hi, ...kf.mid);
    const pad = (hi - lo || 0.5) * 0.08;
    return {
      grid: grid({ top: 16, bottom: 26 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis('price', { min: lo - pad, max: hi + pad, scale: false }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(kf.t, t);
        if (i < 0) return tipHtml(clockHMS(t), [{ label: 'State', value: stateAt(t) }]);
        return tipHtml(clockHMS(kf.t[i]), [
          { label: 'Mid', value: fmtPrice(kf.mid[i]), color: C.mid },
          { label: 'Level l̂', value: fmtPrice(kf.level[i]), color: C.level },
          { label: '±2σ', value: `${fmtPrice(kf.band_lo[i])} – ${fmtPrice(kf.band_hi[i])}` },
          { label: 'State', value: stateAt(kf.t[i]) },
        ]);
      }),
      series: [
        bandSeries('±2σ band', kf.t, kf.band_lo, kf.band_hi, C.band),
        {
          type: 'line',
          name: 'Mid',
          data: pairs(kf.t, kf.mid),
          showSymbol: false,
          lineStyle: { color: C.mid, width: 1.5 },
          markArea,
          markLine:
            agent.warmup_end_t !== null
              ? {
                  silent: true,
                  symbol: ['none', 'none'],
                  data: [{ xAxis: agent.warmup_end_t }],
                  lineStyle: { color: C.muted, type: 'dotted', width: 1.5 },
                  label: { formatter: 'warm-up done', color: C.muted, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, position: 'insideEndTop' },
                }
              : undefined,
        },
        { type: 'line', name: 'Level', data: pairs(kf.t, kf.level), showSymbol: false, lineStyle: { color: C.level, width: 2 } },
      ],
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kf, duration, shade, intervals, agent.warmup_end_t]);

  const tOption = useMemo<EChartsOption>(() => {
    const { theta_in: ti, theta_out: to } = agent.thresholds;
    const absT = kf.T.map(Math.abs).sort((a, b) => a - b);
    const p99 = absT.length ? absT[Math.floor(0.99 * (absT.length - 1))] : 0;
    const ymax = Math.max(p99, ti * 1.3);
    const line = (y: number, c: string, type: 'dashed' | 'dotted') => ({
      yAxis: y,
      lineStyle: { color: c, type, width: 1 },
      label: { formatter: fmtSigned(y), color: c, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, position: 'insideEndTop' as const },
    });
    return {
      grid: grid({ top: 10, bottom: 22 }),
      xAxis: timeAxis(duration, { axisLabel: { show: false } }),
      yAxis: valueAxis((v: number) => fmtSigned(v, 1), { min: -ymax, max: ymax, scale: false, splitNumber: 2, axisLabel: { color: C.dim, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, formatter: (v: number) => fmtSigned(v, 1) } }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(kf.t, t);
        if (i < 0) return '';
        return tipHtml(clockHMS(kf.t[i]), [
          { label: 'Trend strength T', value: fmtSigned(kf.T[i]), color: C.mid },
          { label: 'θ_in / θ_out', value: `±${ti.toFixed(2)} / ±${to.toFixed(2)}` },
          { label: 'v̂ (log-ret/s)', value: fmtSci(kf.v_hat[i]) },
        ]);
      }),
      series: [
        {
          type: 'line',
          name: 'T',
          data: pairs(kf.t, kf.T),
          showSymbol: false,
          lineStyle: { color: C.mid, width: 1.25 },
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            data: [line(ti, C.up, 'dashed'), line(-ti, C.down, 'dashed'), line(to, C.warn, 'dotted'), line(-to, C.warn, 'dotted')],
          },
        },
      ],
    };
  }, [kf, agent.thresholds, duration]);

  const cOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ top: 10, bottom: 22 }),
      xAxis: timeAxis(duration, { axisLabel: { show: false } }),
      yAxis: valueAxis((v: number) => v.toFixed(1), { min: 0, max: 1, scale: false, splitNumber: 2 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(agent.caution.t, t);
        return i < 0 ? '' : tipHtml(clockHMS(agent.caution.t[i]), [{ label: 'Caution C', value: fmtNum(agent.caution.C[i], 3), color: C.up }]);
      }),
      series: [
        { type: 'line', name: 'C', data: pairs(agent.caution.t, agent.caution.C), showSymbol: false, lineStyle: { color: C.up, width: 1.25 }, areaStyle: { color: 'rgba(16,185,129,0.14)' } },
      ],
    }),
    [agent.caution, duration],
  );

  const stateOption = useMemo<EChartsOption>(() => {
    const steps: [number, string][] = [];
    for (const [a, , s] of intervals) steps.push([a, s]);
    if (intervals.length) steps.push([duration, intervals[intervals.length - 1][2]]);
    const near = (t: number) => agent.states.filter((s) => Math.abs(s.t - t) <= Math.max(15, duration / 300));
    return {
      grid: grid({ top: 10, bottom: 26 }),
      xAxis: timeAxis(duration),
      yAxis: categoryAxis([...STATES_TOP_DOWN].reverse(), { boundaryGap: true, axisLine: { show: false } }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        if (t === undefined) return '';
        const rows: { label: string; value: string; color?: string }[] = [{ label: 'State', value: stateAt(t), color: STATE_COLORS[stateAt(t)] }];
        for (const s of near(t)) {
          rows.push({ label: `${REASON_SYMBOL[s.reason]?.label ?? s.reason}`, value: `${s.from ?? '—'} → ${s.to}`, color: REASON_SYMBOL[s.reason]?.color });
          if (s.L !== null) rows.push({ label: '  L', value: fmtPrice(s.L), color: undefined });
          if (s.extreme !== null) rows.push({ label: '  peak / trough', value: fmtPrice(s.extreme), color: undefined });
        }
        return tipHtml(clockHMS(t), rows);
      }, { axisPointer: { type: 'line', lineStyle: { color: C.crosshair, type: 'dashed' } } }),
      series: [
        { type: 'line', name: 'State', step: 'end', data: steps, showSymbol: false, lineStyle: { color: C.pink, width: 1.75 } },
        ...Object.entries(REASON_SYMBOL).map(([reason, s]) => ({
          type: 'scatter' as const,
          name: reason,
          symbol: s.symbol,
          symbolSize: s.size,
          itemStyle: { color: s.color, borderColor: C.card, borderWidth: 1 },
          data: agent.states.filter((x) => x.reason === reason).map((x) => [x.t, x.to]),
          z: 4,
        })),
      ],
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervals, agent.states, duration]);

  const ds = agent.decisions.series;
  const convOption = useMemo<EChartsOption>(() => {
    const lines: [string, keyof typeof ds, string, number][] = [
      ['a (conviction)', 'a', C.text, 2],
      ['s (trend)', 's', '#60A5FA', 1],
      ['m (clarity)', 'm', '#A78BFA', 1],
      ['g (vol scaling)', 'g', '#FBBF24', 1],
    ];
    return {
      grid: grid({ top: 10, bottom: 22, left: 44 }),
      xAxis: timeAxis(duration, {}, true),
      yAxis: valueAxis((v: number) => v.toFixed(1), { min: 0, max: 1, scale: false, splitNumber: 2 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(ds.t, t);
        if (i < 0) return '';
        return tipHtml(clockHMS(ds.t[i]), lines.map(([label, k, c]) => ({ label, value: fmtNum((ds[k] as number[])[i], 3), color: c })));
      }),
      series: lines.map(([name, k, c, w]) => ({ type: 'line' as const, name, data: pairs(ds.t, ds[k] as number[]), showSymbol: false, lineStyle: { color: c, width: w } })),
    };
  }, [ds, duration]);

  const expOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ top: 10, bottom: 22, left: 44 }),
      xAxis: timeAxis(duration, {}, true),
      yAxis: valueAxis((v: number) => `${(v * 100).toFixed(0)}%`, { min: 0, max: 1, scale: false, splitNumber: 2 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(ds.t, t);
        if (i < 0) return '';
        return tipHtml(clockHMS(ds.t[i]), [
          { label: 'Target exposure', value: fmtPct(ds.e_target[i] * 100, 1), color: C.level },
          { label: 'Actual exposure', value: fmtPct(ds.exposure[i] * 100, 1), color: C.accent },
        ]);
      }),
      series: [
        { type: 'line', name: 'e_target', step: 'end', data: pairs(ds.t, ds.e_target), showSymbol: false, lineStyle: { color: C.level, width: 1.5 } },
        { type: 'line', name: 'exposure', step: 'end', data: pairs(ds.t, ds.exposure), showSymbol: false, lineStyle: { color: C.accent, width: 1.5 } },
      ],
    }),
    [ds, duration],
  );

  const counts = agent.decisions.counts;
  const countRows: [string, number, string][] = [
    ['Order placed', counts.order, C.up],
    ['Dead-band (change too small)', counts.dead_band, C.dim],
    ['Anti-chase (price over-extended)', counts.anti_chase, C.warn],
    ['No cash', counts.no_cash, C.down],
    ['No shares', counts.no_shares, '#A78BFA'],
  ];
  const totalDecisions = countRows.reduce((s, [, n]) => s + n, 0);

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-wrap items-center justify-between gap-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-violet-500/40 bg-violet-500/15 text-violet-300">
            <Rocket className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="flex flex-wrap items-center gap-2 text-[16px] font-bold text-text">
              Momentum EKF Agents
              <span className="flex items-center gap-1.5 font-mono text-[13px] font-semibold text-muted">
                <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
                {agent.name}
              </span>
              {state === 'WARMING UP' ? (
                <span className="rounded-[8px] border border-border px-2 py-0.5 font-mono text-[11px] text-muted">STATE: WARMING UP</span>
              ) : (
                <StateBadge state={state} prefix="STATE: " />
              )}
            </h3>
            <p className="text-[12px] text-muted">Long-only trend follower · Damped-trend Kalman filter (l̂, v̂) · Caution modulator · Pyramiding ratchet</p>
          </div>
        </div>
        <Select
          label="Momentum agent"
          value={agent.id}
          options={payload.agents.momentum.map((a) => ({ value: a.id, label: a.name }))}
          onChange={onSelect}
          className="w-56"
        />
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
        <VsHoldKpi agent={agent} />
        <KpiCard label="Cash reserves" value={fmtPrice(agent.final.cash)} caption={`started with ${fmtPrice(agent.start.cash)}`} icon={Banknote} iconClass="text-up" />
        <KpiCard label="Shares" value={fmtInt(agent.final.shares)} caption={`Active equity exposure ${fmtPct(agent.final.exposure_pct, 1)}`} icon={Layers} />
        <KpiCard label="State transitions" value={fmtInt(agent.states.length)} caption={`${fmtInt(agent.final.n_orders)} orders · ${fmtInt(agent.final.n_fills)} fills`} icon={Workflow} iconClass="text-pink-400" />
        <KpiCard
          label="Caution confidence C"
          value={lastC === null ? '—' : fmtPct(lastC * 100, 1)}
          caption="Confidence from recent prediction accuracy (0.5 = neutral)"
          icon={ShieldCheck}
          iconClass="text-up"
        />
      </div>

      <PersonalityProfile params={MOMENTUM_PARAMS} values={agent.hyperparams} ranges={payload.hyperparam_ranges.momentum} columns={4} />

      {kf.t.length === 0 ? (
        <EmptyState
          title={agent.warmup_end_t === null ? 'Still warming up when the session ended' : 'No filter updates after warm-up'}
          body={`The agent needs ${agent.hyperparams.N_w ?? 'its warm-up'} observations before its filter starts; this session was too short for it to trade.`}
        />
      ) : (
        <>
          <Card>
            <SectionHeader
              icon={LineChart}
              title={<>Filter level <span className="normal-case">(l̂)</span> vs market price</>}
              caption={`${fmtInt(kf.t.length)} filter updates`}
              right={<Toggle checked={shade} onChange={setShade} label="Shade regimes" />}
            />
            <div className="mb-2 flex flex-wrap items-center gap-4">
              <LegendItem color={C.mid} label="Market mid" />
              <LegendItem color={C.level} label="Trend level exp(l̂)" />
              <span className="flex items-center gap-1.5 font-mono text-[11px] text-muted">
                <span aria-hidden className="inline-block h-2.5 w-4 rounded-sm" style={{ background: 'rgba(251,146,60,0.35)' }} />
                ±2σ band
              </span>
              {shade && (
                <>
                  <span className="font-mono text-[11px] text-emerald-300">▲ BULL</span>
                  <span className="font-mono text-[11px] text-rose-300">▼ BEAR</span>
                  <span className="font-mono text-[11px] text-amber-200">◐ WATCH</span>
                </>
              )}
            </div>
            <EChart option={levelOption} height={300} group={GROUP} ariaLabel={`${agent.name} trend level against the market mid with uncertainty band`} />
          </Card>

          <Card>
            <SectionHeader icon={Activity} title="Internal decision layers & state dynamics" caption="Panels share the time axis; zoom or hover any of them" iconClass="text-pink-400" />
            <div className="flex flex-col gap-1">
              <PanelLabel>Trend strength T · enter beyond ±θ_in (dashed), stay beyond ±θ_out (dotted)</PanelLabel>
              <EChart option={tOption} height={160} group={GROUP} ariaLabel={`${agent.name} trend strength with entry and stay thresholds`} />
              <PanelLabel>Caution confidence C</PanelLabel>
              <EChart option={cOption} height={160} group={GROUP} ariaLabel={`${agent.name} caution confidence`} />
              <PanelLabel>
                State machine ·{' '}
                {Object.values(REASON_SYMBOL).map((s) => (
                  <span key={s.label} className="mr-2" style={{ color: s.color }}>
                    {s.label}
                  </span>
                ))}
              </PanelLabel>
              <EChart option={stateOption} height={160} group={GROUP} ariaLabel={`${agent.name} state over time with transition markers`} />
            </div>
          </Card>

          <Card>
            <SectionHeader icon={Gauge} title="Decision diagnostics" caption="Why the agent did or did not trade" iconClass="text-warn" />
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <div>
                <PanelLabel>Outcome of {fmtInt(totalDecisions)} decision cycles</PanelLabel>
                <div className="mt-2 flex h-6 w-full overflow-hidden rounded-[6px] bg-bg" role="img" aria-label="Share of decision outcomes">
                  {countRows.map(([label, n, c]) =>
                    n > 0 ? <div key={label} title={`${label}: ${n}`} style={{ width: `${(n / Math.max(1, totalDecisions)) * 100}%`, background: c, borderRight: `2px solid ${C.card}` }} /> : null,
                  )}
                </div>
                <ul className="mt-3 flex flex-col gap-1.5">
                  {countRows.map(([label, n, c]) => (
                    <li key={label} className="flex items-center justify-between gap-3 font-mono text-[12px]">
                      <span className="flex items-center gap-2 text-muted">
                        <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />
                        {label}
                      </span>
                      <span className="text-text">
                        {fmtInt(n)} <span className="text-dim">({totalDecisions ? ((n / totalDecisions) * 100).toFixed(1) : '0.0'}%)</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <PanelLabel>Conviction a = C · s · m · g</PanelLabel>
                  <div className="flex flex-wrap gap-3">
                    <LegendItem color={C.text} label="a" />
                    <LegendItem color="#60A5FA" label="s trend" />
                    <LegendItem color="#A78BFA" label="m clarity" />
                    <LegendItem color="#FBBF24" label="g vol" />
                  </div>
                </div>
                <EChart option={convOption} height={140} group={GROUP} ariaLabel={`${agent.name} conviction and its components`} />
                <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                  <PanelLabel>Exposure vs target</PanelLabel>
                  <div className="flex gap-3">
                    <LegendItem color={C.level} label="target e_target" />
                    <LegendItem color={C.accent} label="actual" />
                  </div>
                </div>
                <EChart option={expOption} height={120} group={GROUP} ariaLabel={`${agent.name} actual equity exposure against its target`} />
              </div>
            </div>
          </Card>
        </>
      )}

      <CashInventory agent={agent} duration={duration} group={GROUP} title="Live cash & inventory timeline (momentum EKF)" />
    </div>
  );
}

function PanelLabel({ children }: { children: ReactNode }) {
  return <div className="micro flex flex-wrap items-center gap-x-1 normal-case tracking-normal text-[11px]">{children}</div>;
}
