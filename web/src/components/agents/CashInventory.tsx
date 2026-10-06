import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { Wallet } from 'lucide-react';
import type { AgentBase } from '../../types/payload';
import { EChart } from '../../charts/EChart';
import { C, axisTooltip, grid, insideZoom, pairs, stepPairs, timeAxis, tipHtml, valueAxis } from '../../charts/theme';
import { bisectRight } from '../../charts/series';
import { clockHMS, fmtInt, fmtPctSigned, fmtPrice, fmtUsdSigned } from '../../lib/format';
import { Card, LegendItem, SectionHeader } from '../ui/Card';

const usdAxis = (v: number) => `$${Math.round(v).toLocaleString('en-US')}`;

/** Cash (step, green where it rose / red where it fell, fill dots), share
 *  inventory (step area) and portfolio value vs start value. */
export function CashInventory({ agent, duration, group, title }: { agent: AgentBase; duration: number; group: string; title: string }) {
  const h = agent.holdings;
  const f = agent.fills;

  const cashOption = useMemo<EChartsOption>(() => {
    const segColor = (i: number) => (i === 0 ? C.muted : h.cash[i] > h.cash[i - 1] ? C.up : h.cash[i] < h.cash[i - 1] ? C.down : C.muted);
    const fillCash = f.t.map((t) => h.cash[Math.max(0, bisectRight(h.t, t))]);
    const lo = Math.min(...h.cash);
    const hi = Math.max(...h.cash);
    const pad = (hi - lo || Math.max(1, hi * 0.01)) * 0.12;
    return {
      grid: grid({ left: 72, top: 12, bottom: 24 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis(usdAxis, { min: lo - pad, max: hi + pad, scale: false, splitNumber: 3 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        if (t === undefined) return '';
        const i = Math.max(0, bisectRight(h.t, t));
        const rows = [{ label: 'Cash', value: fmtPrice(h.cash[i]), color: segColor(i) }];
        const near = f.t.map((ft, k) => [ft, k] as const).filter(([ft]) => Math.abs(ft - t) <= Math.max(20, duration / 400));
        for (const [, k] of near) rows.push({ label: f.side[k] === 'BUY' ? '▲ BUY' : '▼ SELL', value: `${fmtInt(f.qty[k])} @ ${fmtPrice(f.price[k])}`, color: f.side[k] === 'BUY' ? C.up : C.down });
        return tipHtml(clockHMS(t), rows);
      }),
      series: [
        {
          type: 'custom',
          name: 'Cash',
          clip: true,
          encode: { x: 0, y: 1 },
          data: h.t.map((t, i) => [t, h.cash[i], i]),
          renderItem: (_: unknown, api: any) => {
            const i = api.value(2);
            const x0 = api.value(0);
            const x1 = i + 1 < h.t.length ? h.t[i + 1] : duration;
            const [a, y] = api.coord([x0, h.cash[i]]);
            const [b] = api.coord([x1, h.cash[i]]);
            const children: any[] = [{ type: 'line', shape: { x1: a, y1: y, x2: b, y2: y }, style: { stroke: segColor(i), lineWidth: 2 } }];
            if (i + 1 < h.t.length) {
              const [, y2] = api.coord([x1, h.cash[i + 1]]);
              children.push({ type: 'line', shape: { x1: b, y1: y, x2: b, y2 }, style: { stroke: C.dim, lineWidth: 1 } });
            }
            return { type: 'group', children };
          },
        } as any,
        {
          type: 'scatter',
          name: 'Fills',
          data: f.t.map((t, k) => ({ value: [t, fillCash[k]], itemStyle: { color: f.side[k] === 'BUY' ? C.up : C.down, borderColor: C.card, borderWidth: 2 } })),
          symbol: 'circle',
          symbolSize: 8,
          z: 5,
        },
      ],
    };
  }, [h, f, duration]);

  const sharesOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ left: 72, top: 12, bottom: 24 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis((v: number) => `${v.toFixed(0)} sh`, { min: 0, scale: false, splitNumber: 2 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        if (t === undefined) return '';
        const i = Math.max(0, bisectRight(h.t, t));
        return tipHtml(clockHMS(t), [{ label: 'Shares', value: fmtInt(h.shares[i]), color: C.accent }]);
      }),
      series: [
        {
          type: 'line',
          name: 'Shares',
          step: 'end',
          data: stepPairs(h.t, h.shares, duration),
          showSymbol: false,
          lineStyle: { color: C.accent, width: 2 },
          areaStyle: { color: 'rgba(99,102,241,0.18)' },
        },
      ],
    }),
    [h, duration],
  );

  const valueOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ left: 72, top: 12, bottom: 24 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis(usdAxis, { splitNumber: 3 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        if (t === undefined) return '';
        const i = Math.max(0, bisectRight(agent.value_1m.t, t));
        const v = agent.value_1m.v[i];
        return tipHtml(clockHMS(agent.value_1m.t[i] ?? t), [
          { label: 'Value', value: fmtPrice(v), color: C.text },
          { label: 'vs start', value: fmtUsdSigned(v - agent.start.value) },
        ]);
      }),
      series: [
        {
          type: 'line',
          name: 'Portfolio value',
          data: pairs(agent.value_1m.t, agent.value_1m.v),
          showSymbol: false,
          lineStyle: { color: C.text, width: 1.5 },
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            data: [{ yAxis: agent.start.value }],
            lineStyle: { color: C.muted, type: 'dashed' },
            label: { formatter: `start ${fmtPrice(agent.start.value)}`, color: C.muted, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, position: 'insideStartTop' },
          },
        },
      ],
    }),
    [agent, duration],
  );

  const pnlTone = agent.final.pnl > 0 ? 'text-up' : agent.final.pnl < 0 ? 'text-down' : 'text-muted';
  return (
    <Card>
      <SectionHeader icon={Wallet} title={title} caption={`${fmtInt(h.t.length)} portfolio state points · ${fmtInt(f.t.length)} fills`} iconClass="text-up" />
      <div className="flex flex-col gap-4">
        <div>
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <span className="micro">Cash balance</span>
            <div className="flex gap-3">
              <LegendItem color={C.up} label="rose" />
              <LegendItem color={C.down} label="fell" />
              <span className="flex items-center gap-1 font-mono text-[11px] text-muted">● fill (▲ buy / ▼ sell in tooltip)</span>
            </div>
          </div>
          <EChart option={cashOption} height={150} group={group} ariaLabel={`${agent.name} cash balance over time`} />
        </div>
        <div>
          <span className="micro mb-1 block">Share inventory</span>
          <EChart option={sharesOption} height={120} group={group} ariaLabel={`${agent.name} share inventory over time`} />
        </div>
        <div>
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <span className="micro">Portfolio value</span>
            <span className={`font-mono text-[12px] font-semibold ${pnlTone}`}>
              P&amp;L {fmtUsdSigned(agent.final.pnl)} ({fmtPctSigned(agent.final.pnl_pct, 3)})
            </span>
          </div>
          <EChart option={valueOption} height={130} group={group} ariaLabel={`${agent.name} portfolio value over time against its starting value`} />
        </div>
      </div>
    </Card>
  );
}
