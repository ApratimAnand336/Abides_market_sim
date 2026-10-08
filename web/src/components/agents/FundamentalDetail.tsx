import { useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import { Banknote, Cpu, Gauge, Layers, LineChart, ShieldCheck } from 'lucide-react';
import type { FundamentalAgent, SimPayload } from '../../types/payload';
import { EChart } from '../../charts/EChart';
import { C, axisTooltip, grid, insideZoom, pairs, robustDomain, timeAxis, tipHtml, valueAxis } from '../../charts/theme';
import { bisectRight, clipToDomain, markersNear, offScaleMarkerSeries } from '../../charts/series';
import { clockHMS, fmtInt, fmtNum, fmtPct, fmtPrice, fmtSci } from '../../lib/format';
import { FUNDAMENTAL_PARAMS } from '../../config/agentParams';
import { Card, LegendItem, SectionHeader } from '../ui/Card';
import { Select, Toggle } from '../ui/controls';
import { EmptyState } from '../ui/feedback';
import { PersonalityProfile } from './PersonalityProfile';
import { CashInventory } from './CashInventory';
import { KpiCard } from '../ui/KpiCard';
import { VsHoldKpi } from './VsHoldKpi';

const GROUP = 'agents';

export function FundamentalDetail({
  payload,
  agent,
  color,
  onSelect,
}: {
  payload: SimPayload;
  agent: FundamentalAgent;
  color: string;
  onSelect: (id: number) => void;
}) {
  const duration = payload.meta.session.duration_s;
  const e = agent.ekf;
  const [fullRange, setFullRange] = useState(false);
  const [rawEr, setRawEr] = useState(true);

  // y-domain from the mid's 0.5–99.5 percentile ±15%; x̂ breaks where it
  // leaves it (spec v1.1 D1) unless "Show full range" is on
  const midDomain = useMemo(() => robustDomain(e.mid), [e.mid]);
  const domain = useMemo<[number, number]>(() => {
    if (!fullRange) return midDomain;
    const lo = Math.min(midDomain[0], ...e.x_hat);
    const hi = Math.max(midDomain[1], ...e.x_hat);
    const pad = (hi - lo) * 0.05;
    return [lo - pad, hi + pad];
  }, [fullRange, midDomain, e.x_hat]);
  const offScale = useMemo(() => e.x_hat.filter((v) => v < midDomain[0] || v > midDomain[1]).length, [e.x_hat, midDomain]);

  const xhatOption = useMemo<EChartsOption>(() => {
    // off-scale x̂ becomes a gap, with one edge marker per off-scale run
    const clipped = fullRange ? null : clipToDomain(e.t, e.x_hat, domain, `x̂ ${agent.name}`, color);
    const markers = clipped?.markers ?? [];
    return {
      grid: grid({ top: 14, bottom: 26 }),
      xAxis: timeAxis(duration, {}, true),
      yAxis: valueAxis('price', { min: domain[0], max: domain[1], scale: false }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(e.t, t);
        if (i < 0) return '';
        const off = e.x_hat[i] < midDomain[0] || e.x_hat[i] > midDomain[1];
        const rows = [
          { label: 'Mid', value: fmtPrice(e.mid[i]), color: C.mid },
          { label: `x̂${off && !fullRange ? ' (off-scale)' : ''}`, value: fmtPrice(e.x_hat[i]), color },
          { label: 'x̂ − mid', value: fmtPrice(e.x_hat[i] - e.mid[i]) },
        ];
        for (const m of markersNear(markers, t, Math.max(30, duration / 300))) {
          if (m.t !== e.t[i]) rows.push({ label: `${m.edge === 'top' ? '▲' : '▼'} run peak at ${clockHMS(m.t)}`, value: fmtPrice(m.v), color });
        }
        return tipHtml(clockHMS(e.t[i]), rows);
      }),
      series: [
        { type: 'line', name: 'Mid', data: pairs(e.t, e.mid), showSymbol: false, lineStyle: { color: C.mid, width: 1.5 } },
        { type: 'line', name: 'x̂', data: clipped ? clipped.data : pairs(e.t, e.x_hat), connectNulls: false, showSymbol: false, lineStyle: { color, width: 2 } },
        ...(markers.length ? [offScaleMarkerSeries(markers, domain, 'x̂ off-scale')] : []),
      ],
    };
  }, [e, duration, domain, fullRange, color, midDomain, agent.name]);

  const kOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ top: 14, bottom: 26, right: 44 }),
      xAxis: timeAxis(duration, {}, true),
      // K on a log axis so its decay towards 0 stays visible (spec 6.3.2 #4);
      // ER on the right in [0, 1]
      yAxis: [
        valueAxis(fmtSci, { type: 'log', scale: false, logBase: 10 }),
        valueAxis((v: number) => v.toFixed(1), { min: 0, max: 1, scale: false, splitLine: { show: false }, position: 'right' }),
      ],
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(e.t, t);
        if (i < 0) return '';
        return tipHtml(clockHMS(e.t[i]), [
          { label: 'K', value: fmtSci(e.K[i]), color: C.mid },
          { label: 'ER (smoothed)', value: fmtNum(e.ER_smooth[i], 3), color: C.warn },
          { label: 'ER (raw)', value: fmtNum(e.ER[i], 3) },
        ]);
      }),
      series: [
        ...(rawEr
          ? [{ type: 'scatter' as const, name: 'ER raw', yAxisIndex: 1, data: pairs(e.t, e.ER), symbolSize: 2, itemStyle: { color: 'rgba(251,191,36,0.22)' }, silent: true, large: true }]
          : []),
        { type: 'line', name: 'ER smoothed', yAxisIndex: 1, data: pairs(e.t, e.ER_smooth), showSymbol: false, lineStyle: { color: C.warn, width: 1.5 } },
        { type: 'line', name: 'K', yAxisIndex: 0, data: pairs(e.t, e.K.map((k) => (k > 0 ? k : null))), showSymbol: false, lineStyle: { color: C.mid, width: 1.5 } },
      ],
    }),
    [e, duration, rawEr],
  );

  const cautionOption = useMemo<EChartsOption>(() => {
    const c = agent.caution;
    return {
      grid: grid({ top: 14, bottom: 26, right: 56 }),
      xAxis: timeAxis(duration),
      yAxis: [
        valueAxis((v: number) => v.toFixed(1), { min: 0, max: 1, scale: false }),
        valueAxis((v: number) => `${v < 0 ? '−' : ''}$${Math.abs(v).toFixed(2)}`, { splitLine: { show: false }, position: 'right' }),
      ],
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(c.t, t);
        if (i < 0) return '';
        return tipHtml(clockHMS(c.t[i]), [
          { label: 'Confidence C', value: fmtNum(c.C[i], 3), color: C.up },
          { label: 'Memory E', value: fmtPrice(c.E[i]), color: C.down },
          { label: 'Last view D', value: c.D[i] > 0 ? '▲ up' : c.D[i] < 0 ? '▼ down' : 'none' },
        ]);
      }),
      series: [
        {
          type: 'line',
          name: 'C',
          data: pairs(c.t, c.C),
          showSymbol: false,
          lineStyle: { color: C.up, width: 1.5 },
          areaStyle: { color: 'rgba(16,185,129,0.12)' },
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            data: [{ yAxis: 0.5 }],
            lineStyle: { color: C.muted, type: 'dashed' },
            label: { formatter: 'C = 0.5', color: C.muted, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, position: 'insideStartTop' },
          },
        },
        { type: 'line', name: 'E', yAxisIndex: 1, data: pairs(c.t, c.E), showSymbol: false, lineStyle: { color: C.down, width: 1 } },
      ],
    };
  }, [agent.caution, duration]);

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-wrap items-center justify-between gap-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-accent/40 bg-accent/15 text-indigo-300">
            <Cpu className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="flex flex-wrap items-center gap-2 text-[16px] font-bold text-text">
              <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
              {agent.name}
              <span className="rounded-[8px] border border-accent/40 bg-accent/10 px-2 py-0.5 font-mono text-[11px] text-indigo-200">ID: {agent.id}</span>
            </h3>
            <p className="text-[12px] text-muted">Extended Kalman Filter with Emotional Caution &amp; Dynamic Allocation</p>
          </div>
        </div>
        <Select
          label="Fundamental agent"
          value={agent.id}
          options={payload.agents.fundamental.map((a) => ({ value: a.id, label: a.name }))}
          onChange={onSelect}
          className="w-56"
        />
      </Card>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <VsHoldKpi agent={agent} />
        <KpiCard label="Cash reserves" value={fmtPrice(agent.final.cash)} caption={`started with ${fmtPrice(agent.start.cash)}`} icon={Banknote} iconClass="text-up" />
        <KpiCard label="Shares" value={fmtInt(agent.final.shares)} caption={`Active equity exposure ${fmtPct(agent.final.exposure_pct, 1)}`} icon={Layers} />
        <KpiCard
          label="Caution confidence C"
          value={agent.caution.C.length ? fmtPct(agent.caution.C[agent.caution.C.length - 1] * 100, 1) : '—'}
          caption={`${fmtInt(agent.final.n_orders)} orders · ${fmtInt(agent.final.n_fills)} fills`}
          icon={ShieldCheck}
          iconClass="text-up"
        />
      </div>

      <PersonalityProfile params={FUNDAMENTAL_PARAMS} values={agent.hyperparams} ranges={payload.hyperparam_ranges.fundamental} />

      {e.t.length === 0 ? (
        <EmptyState title="No filter updates recorded for this agent" body="The agent never observed a two-sided book during the session." />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card>
              <SectionHeader
                icon={LineChart}
                title={<>EKF state: posterior estimate <span className="normal-case">(x̂)</span> vs market mid</>}
                right={<Toggle checked={fullRange} onChange={setFullRange} label="Show full range" />}
              />
              <div className="mb-2 flex flex-wrap items-center gap-4">
                <LegendItem color={C.mid} label="Market mid" />
                <LegendItem color={color} label="EKF estimate x̂" />
                {offScale > 0 && !fullRange && (
                  <span className="rounded-[8px] border border-warn/40 bg-warn/10 px-2 py-0.5 font-mono text-[11px] text-amber-200">
                    ▲▼ x̂ off-scale at {offScale} of {e.t.length} points
                  </span>
                )}
              </div>
              <EChart option={xhatOption} height={260} group={GROUP} ariaLabel={`${agent.name} estimate x hat against the market mid price`} />
            </Card>
            <Card>
              <SectionHeader icon={Gauge} title="Kalman gain (K) & efficiency ratio (ER)" right={<Toggle checked={rawEr} onChange={setRawEr} label="Raw ER dots" />} />
              <div className="mb-2 flex flex-wrap items-center gap-4">
                <LegendItem color={C.mid} label="K (left, log scale)" />
                <LegendItem color={C.warn} label="ER, 20-update mean (right, 0–1)" />
              </div>
              <EChart option={kOption} height={260} group={GROUP} ariaLabel={`${agent.name} Kalman gain on a log scale and efficiency ratio`} />
            </Card>
          </div>
          <Card>
            <SectionHeader icon={ShieldCheck} title="Caution modulator" caption="C = confidence from recent prediction accuracy; E = smoothed virtual P&L of the last directional view" iconClass="text-up" />
            <div className="mb-2 flex flex-wrap items-center gap-4">
              <LegendItem color={C.up} label="Confidence C (left, 0–1)" />
              <LegendItem color={C.down} label="Memory E (right, $)" />
            </div>
            <EChart option={cautionOption} height={220} group={GROUP} ariaLabel={`${agent.name} caution confidence and memory over time`} />
          </Card>
        </>
      )}

      <CashInventory agent={agent} duration={duration} group={GROUP} title="Live cash & inventory timeline" />
    </div>
  );
}
