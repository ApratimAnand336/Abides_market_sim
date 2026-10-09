import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { Crosshair, Hourglass, Ruler, Scale } from 'lucide-react';
import type { SimPayload } from '../../types/payload';
import { EChart } from '../../charts/EChart';
import { C, axisTooltip, grid, insideZoom, pairs, timeAxis, tipHtml, valueAxis } from '../../charts/theme';
import { bisectRight } from '../../charts/series';
import { clockHMS, fmtNum, fmtPrice } from '../../lib/format';
import { Card, SectionHeader } from '../ui/Card';
import { KpiCard } from '../ui/KpiCard';

const signedUsd = (v: number) => `${v < 0 ? '−' : v > 0 ? '+' : ''}$${Math.abs(v).toFixed(2)}`;

/** Gap between the traded price and the hidden true value (spec v1.1 D5). */
export function PriceVsValue({ payload }: { payload: SimPayload }) {
  const g = payload.stats.gap;
  const s = payload.market.gap;
  const duration = payload.meta.session.duration_s;

  const option = useMemo<EChartsOption>(
    () => ({
      grid: grid({ top: 14, bottom: 26, left: 64 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis(signedUsd, { splitNumber: 4 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(s.t, t);
        if (i < 0) return '';
        return tipHtml(clockHMS(s.t[i]), [{ label: 'mid − true value', value: signedUsd(s.v[i]), color: C.oracle }]);
      }),
      series: [
        {
          type: 'line',
          name: 'gap',
          data: pairs(s.t, s.v),
          showSymbol: false,
          lineStyle: { color: C.oracle, width: 1.25 },
          areaStyle: { color: 'rgba(245,158,11,0.10)', origin: 0 },
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            data: [{ yAxis: 0 }],
            lineStyle: { color: C.muted, type: 'dashed' },
            label: { formatter: 'price = true value', color: C.muted, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, position: 'insideStartTop' },
          },
        },
      ],
    }),
    [s, duration],
  );

  return (
    <Card>
      <SectionHeader
        icon={Scale}
        title="Price vs true value"
        caption="How far, and for how long, the traded price strays from the hidden true value in this run."
        iconClass="text-oracle"
      />
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard label="Gap std" value={fmtPrice(g.std)} caption="spread of mid − true value" icon={Ruler} iconClass="text-oracle" hint="Standard deviation of the mid minus the hidden true value, on a 1-second grid." />
        <KpiCard label="Mean |gap|" value={fmtPrice(g.mean_abs)} caption="typical size of a mispricing" icon={Crosshair} iconClass="text-oracle" />
        <KpiCard
          label="Half-life"
          value={g.half_life_min === null ? '—' : `${fmtNum(g.half_life_min, 1)} min`}
          caption={`ρ at ${g.lags_s.map((l) => `${l / 60}m`).join(' / ')}: ${g.rho.map((r) => fmtNum(r, 2)).join(' / ')}`}
          icon={Hourglass}
          iconClass="text-oracle"
          hint="Time for a mispricing to shrink by half, from the gap's autocorrelation: ρ(L) = exp(−kL), half-life = ln 2 / k (median over lags with 0.05 < ρ < 0.98). One day holds only about a dozen independent mispricings, so the estimate varies a lot between runs (about ±50% for a true 10-minute half-life)."
        />
      </div>
      {s.t.length ? (
        <EChart option={option} height={200} ariaLabel="Mid price minus hidden true value over the session" />
      ) : (
        <p className="py-8 text-center text-[13px] text-muted">No gap series: the session has no two-sided quotes or oracle values.</p>
      )}
    </Card>
  );
}
