import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { EChartsOption } from 'echarts';
import { BarChart3, BookOpen, RotateCcw, Ruler } from 'lucide-react';
import type { SimPayload } from '../types/payload';
import { EChart, resetGroupZoom } from '../charts/EChart';
import { C, axisTooltip, grid, insideZoom, pairs, sliderZoom, timeAxis, tipHtml, valueAxis } from '../charts/theme';
import {
  aggregateCandles,
  bandSeries,
  bisectRight,
  candleSeries,
  clipToDomain,
  intervalBarSeries,
  markersNear,
  newsMarkLine,
  stressMarkArea,
  newsNear,
  offScaleMarkerSeries,
  type Candle,
  type OffScaleMarker,
} from '../charts/series';
import { agentColorMap } from '../lib/agents';
import { clockHMS, escapeHtml, fmtInt, fmtNum, fmtPct, fmtPrice } from '../lib/format';
import { useQueryFlag, useQueryParam } from '../lib/urlState';
import { Card, LegendItem, SectionHeader } from '../components/ui/Card';
import { Button, SegmentedControl, Toggle } from '../components/ui/controls';
import { cn } from '../lib/cn';

const GROUP = 'overview';
const INTERVALS = { '1m': 1, '5m': 5, '15m': 15 } as const;
type IntervalKey = keyof typeof INTERVALS;

export function MarketOverview({ payload }: { payload: SimPayload }) {
  const { market, stats, news } = payload;
  const duration = payload.meta.session.duration_s;
  const [view, setView] = useQueryParam('view', 'candles');
  const [ivKey, setIvKey] = useQueryParam('iv', '5m');
  const [showOracle, setShowOracle] = useQueryFlag('oracle', true);
  const [showXhat, setShowXhat] = useQueryFlag('xhat', false);
  const [showLevel, setShowLevel] = useQueryFlag('lhat', false);
  const [showNews, setShowNews] = useQueryFlag('news', true);
  const [showBand, setShowBand] = useQueryFlag('band', false);
  const [hoverT, setHoverT] = useState<number | null>(null);
  const raf = useRef<number | null>(null);

  // spec v1.1 D3: belief-line overlays only for selected agents (component
  // state, not storage). Default: every fundamentalist, no momentum agent.
  const defaultOverlay = useCallback(() => new Set(payload.agents.fundamental.map((a) => a.id)), [payload]);
  const [overlayIds, setOverlayIds] = useState<Set<number>>(defaultOverlay);
  useEffect(() => setOverlayIds(defaultOverlay()), [defaultOverlay]);
  const toggleOverlay = (id: number) =>
    setOverlayIds((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const overlayFund = useMemo(() => payload.agents.fundamental.filter((a) => overlayIds.has(a.id)), [payload.agents.fundamental, overlayIds]);
  const overlayMom = useMemo(() => payload.agents.momentum.filter((a) => overlayIds.has(a.id)), [payload.agents.momentum, overlayIds]);

  const iv = (INTERVALS[ivKey as IntervalKey] ?? 5) as number;
  const ivS = iv * 60;
  const candles = useMemo(() => aggregateCandles(market.candles_1m, iv), [market.candles_1m, iv]);
  const candleT = useMemo(() => candles.map((c) => c.t), [candles]);
  const colors = useMemo(() => agentColorMap(payload), [payload]);
  const isCandles = view !== 'tick';

  // y-domain from market prices only (candle lows/highs or the mid), ±10% of
  // the range; overlays never move it: they break where they leave it (D1)
  const yDomain = useMemo<[number, number]>(() => {
    let lo: number;
    let hi: number;
    if (isCandles) {
      lo = Math.min(...candles.map((c) => c.l));
      hi = Math.max(...candles.map((c) => c.h));
    } else {
      lo = Math.min(...market.quotes.bid);
      hi = Math.max(...market.quotes.ask);
    }
    const pad = (hi - lo || 0.5) * 0.1;
    return [lo - pad, hi + pad];
  }, [isCandles, candles, market.quotes]);

  const mainOption = useMemo<EChartsOption>(() => {
    const series: any[] = [];
    if (isCandles) {
      series.push(candleSeries(candles, ivS));
    } else {
      if (showBand) series.push(bandSeries('Bid/ask band', market.quotes.t, market.quotes.bid, market.quotes.ask, 'rgba(56,189,248,0.22)'));
      series.push({ type: 'line', name: 'Mid', data: pairs(market.quotes.t, market.quotes.mid), showSymbol: false, lineStyle: { color: C.mid, width: 1.5 }, z: 3 });
    }
    if (showOracle) {
      series.push({ type: 'line', name: 'Oracle', data: pairs(market.oracle.t, market.oracle.v), showSymbol: false, lineStyle: { color: C.oracle, width: 1.5, type: 'dashed' }, z: 4 });
    }
    const offScale: OffScaleMarker[] = [];
    if (showXhat) {
      for (const a of overlayFund) {
        const color = colors.get(a.id)!;
        const { data, markers } = clipToDomain(a.ekf.t, a.ekf.x_hat, yDomain, `x̂ ${a.name}`, color);
        offScale.push(...markers);
        series.push({ type: 'line', name: `x̂ ${a.name}`, data, connectNulls: false, showSymbol: false, lineStyle: { color, width: 1.25, opacity: 0.7 }, z: 2 });
      }
    }
    if (showLevel) {
      for (const a of overlayMom) {
        const color = colors.get(a.id)!;
        const { data, markers } = clipToDomain(a.kf.t, a.kf.level, yDomain, `l̂ ${a.name}`, color);
        offScale.push(...markers);
        series.push({ type: 'line', name: `l̂ ${a.name}`, data, connectNulls: false, showSymbol: false, lineStyle: { color, width: 1 }, z: 2 });
      }
    }
    if (showNews && news.length && series.length) series[series.length - 1].markLine = newsMarkLine(news);
    const stress = stressMarkArea(payload.day_info);
    if (stress && series.length) series[0].markArea = stress;
    if (offScale.length) series.push(offScaleMarkerSeries(offScale, yDomain));

    return {
      grid: grid({ bottom: 64, top: 20 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis('price', { min: yDomain[0], max: yDomain[1], scale: false }),
      dataZoom: sliderZoom(),
      tooltip: axisTooltip((params: any[]) => mainTip(params?.[0]?.axisValue)),
      series,
    };

    function mainTip(t: number | undefined): string {
      if (t === undefined) return '';
      const rows: { color?: string; label: string; value: string }[] = [];
      if (isCandles) {
        const i = bisectRight(candleT, t);
        const c = candles[i];
        if (c) {
          rows.push(
            { label: 'O', value: fmtPrice(c.o) },
            { label: 'H', value: fmtPrice(c.h) },
            { label: 'L', value: fmtPrice(c.l) },
            { label: 'C', value: fmtPrice(c.c), color: c.c >= c.o ? C.up : C.down },
            { label: 'Vol', value: `${fmtInt(c.volume)} sh` },
            { label: 'Trades', value: fmtInt(c.trades) },
          );
        }
      } else {
        const i = bisectRight(market.quotes.t, t);
        if (i >= 0) {
          rows.push(
            { label: 'Mid', value: fmtPrice(market.quotes.mid[i]), color: C.mid },
            { label: 'Bid', value: fmtPrice(market.quotes.bid[i]) },
            { label: 'Ask', value: fmtPrice(market.quotes.ask[i]) },
          );
        }
      }
      if (showOracle) {
        const j = bisectRight(market.oracle.t, t);
        if (j >= 0) rows.push({ label: 'Oracle', value: fmtPrice(market.oracle.v[j]), color: C.oracle });
      }
      for (const m of markersNear(offScale, t, Math.max(30, duration / 300))) {
        rows.push({ label: `${m.edge === 'top' ? '▲' : '▼'} ${m.label} (off-scale)`, value: fmtPrice(m.v), color: m.color });
      }
      let html = tipHtml(clockHMS(t), rows);
      for (const n of newsNear(news, t, Math.max(30, duration / 300))) {
        html += `<div style="margin-top:6px;max-width:260px;white-space:normal;color:${n.sentiment >= 0 ? C.up : C.down}">📰 ${n.kind === 'information' ? 'Information' : 'Hype'}: ${escapeHtml(n.headline)} (${n.sentiment >= 0 ? '+' : '−'}${Math.abs(n.sentiment).toFixed(2)})</div>`;
      }
      return html;
    }
  }, [isCandles, candles, candleT, ivS, market, showBand, showOracle, showXhat, showLevel, showNews, news, overlayFund, overlayMom, colors, duration, yDomain, payload.day_info]);

  const volOption = useMemo<EChartsOption>(() => {
    const t = candles.map((c) => c.t);
    const v = candles.map((c) => c.volume);
    return {
      grid: grid({ top: 10, bottom: 24 }),
      xAxis: timeAxis(duration, {}, true),
      yAxis: valueAxis('num', { min: 0, scale: false, splitNumber: 2 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const x = params?.[0]?.axisValue;
        const i = bisectRight(t, x);
        const c = candles[i];
        return c ? tipHtml(`${clockHMS(c.t)} – ${clockHMS(c.t + ivS)}`, [{ label: 'Volume', value: `${fmtInt(c.volume)} sh` }, { label: 'Trades', value: fmtInt(c.trades) }]) : '';
      }),
      series: [intervalBarSeries('Volume', t, v, ivS, (i) => (candles[i].c >= candles[i].o ? 'rgba(16,185,129,0.75)' : 'rgba(244,63,94,0.75)'))],
    };
  }, [candles, ivS, duration]);

  const spreadCents = useMemo(() => market.quotes.ask.map((a, i) => Math.round((a - market.quotes.bid[i]) * 1000) / 10), [market.quotes]);
  const spreadOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ top: 10, bottom: 24 }),
      xAxis: timeAxis(duration, {}, true),
      yAxis: valueAxis((v: number) => `${v}¢`, { min: 0, scale: false, splitNumber: 2 }),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const x = params?.[0]?.axisValue;
        const i = bisectRight(market.quotes.t, x);
        return i >= 0 ? tipHtml(clockHMS(market.quotes.t[i]), [{ label: 'Spread', value: `${spreadCents[i].toFixed(1)}¢`, color: C.spread }]) : '';
      }),
      series: [
        {
          type: 'line',
          name: 'Spread',
          step: 'end',
          data: pairs(market.quotes.t, spreadCents),
          showSymbol: false,
          lineStyle: { color: C.spread, width: 1 },
          areaStyle: { color: 'rgba(168,85,247,0.12)' },
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            data: [{ yAxis: stats.spread.mean * 100 }],
            lineStyle: { color: C.muted, type: 'dashed' },
            label: { formatter: `mean ${(stats.spread.mean * 100).toFixed(1)}¢`, color: C.muted, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, position: 'insideEndTop' },
          },
        },
      ],
    }),
    [market.quotes, spreadCents, stats.spread.mean, duration],
  );

  // hover drives the readout bar and the depth ladder; throttled to one
  // update per frame
  const onEvents = useMemo(
    () => ({
      updateAxisPointer: (e: any) => {
        const v = e?.axesInfo?.find((a: any) => a.axisDim === 'x')?.value;
        if (raf.current !== null) cancelAnimationFrame(raf.current);
        raf.current = requestAnimationFrame(() => setHoverT(typeof v === 'number' ? v : null));
      },
      globalout: () => setHoverT(null),
    }),
    [],
  );

  const readoutCandle: Candle | undefined = useMemo(() => {
    const t = hoverT ?? candles[candles.length - 1]?.t;
    if (t === undefined) return undefined;
    return candles[Math.max(0, bisectRight(candleT, t))];
  }, [hoverT, candles, candleT]);

  const maxVol = Math.max(0, ...candles.map((c) => c.volume));
  const resetZoom = useCallback(() => resetGroupZoom(GROUP), []);

  return (
    <div className="flex flex-col gap-6">
      {/* toolbar */}
      <Card className="flex flex-wrap items-center justify-between gap-4 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="micro">Chart view</span>
          <SegmentedControl
            label="Chart view"
            value={isCandles ? 'candles' : 'tick'}
            onChange={setView}
            options={[
              { value: 'candles', label: 'Candlesticks' },
              { value: 'tick', label: `Tick Mid-Price (${fmtInt(market.totals.price_points)})` },
            ]}
          />
          {isCandles ? (
            <SegmentedControl
              label="Candle interval"
              size="sm"
              value={(ivKey in INTERVALS ? ivKey : '5m') as IntervalKey}
              onChange={setIvKey}
              options={(Object.keys(INTERVALS) as IntervalKey[]).map((k) => ({ value: k, label: k }))}
            />
          ) : (
            <Toggle checked={showBand} onChange={setShowBand} label="Bid/ask band" swatch="rgba(56,189,248,0.5)" />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <Toggle checked={showOracle} onChange={setShowOracle} label="Oracle fundamental" swatch={C.oracle} dashed />
          <Toggle checked={showXhat} onChange={setShowXhat} label="EKF estimates (x̂)" swatch={C.pink} />
          <Toggle checked={showLevel} onChange={setShowLevel} label="Momentum trend levels (l̂)" swatch={C.level} />
          <Toggle checked={showNews} onChange={setShowNews} label="News shocks" swatch={C.up} dashed />
          <Button variant="ghost" onClick={resetZoom}>
            <RotateCcw className="h-3.5 w-3.5" aria-hidden /> Reset zoom
          </Button>
        </div>
        {(payload.agents.fundamental.length > 0 || payload.agents.momentum.length > 0) && (
          <div className="flex w-full flex-wrap items-center gap-2 border-t border-border pt-3" role="group" aria-label="Overlay agents">
            <span className="micro mr-1">Overlay agents</span>
            {[...payload.agents.fundamental, ...payload.agents.momentum].map((a) => {
              const on = overlayIds.has(a.id);
              const color = colors.get(a.id)!;
              return (
                <button
                  key={a.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleOverlay(a.id)}
                  title={`${a.kind === 'fundamental' ? 'x̂' : 'l̂'} overlay for ${a.name}`}
                  className={cn(
                    'flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] transition-colors',
                    on ? 'text-text' : 'border-border text-dim hover:text-muted',
                  )}
                  style={on ? { borderColor: `${color}99`, background: `${color}1F` } : undefined}
                >
                  <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: on ? color : 'transparent', boxShadow: `inset 0 0 0 1.5px ${color}` }} />
                  {a.kind === 'fundamental' ? 'x̂' : 'l̂'} {a.name}
                </button>
              );
            })}
            <span className="font-mono text-[11px] text-dim">
              {!showXhat && !showLevel ? 'turn on x̂ or l̂ above to draw them' : 'x̂ / l̂ toggles apply to the selected agents'}
            </span>
          </div>
        )}
      </Card>

      {/* main chart */}
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-border bg-bg/60 px-3 py-2 font-mono text-[12px]">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted" aria-live="off">
            {isCandles && readoutCandle ? (
              <>
                <span>
                  t: <b className="text-text">{clockHMS(hoverT ?? readoutCandle.t)}</b>
                </span>
                <span>O <b className="text-text">{fmtPrice(readoutCandle.o)}</b></span>
                <span>H <b className="text-text">{fmtPrice(readoutCandle.h)}</b></span>
                <span>L <b className="text-text">{fmtPrice(readoutCandle.l)}</b></span>
                <span>
                  C <b className={readoutCandle.c >= readoutCandle.o ? 'text-up' : 'text-down'}>{fmtPrice(readoutCandle.c)}</b>
                </span>
                <span>Vol <b className="text-text">{fmtInt(readoutCandle.volume)} sh</b></span>
                <span>Trades <b className="text-text">{fmtInt(readoutCandle.trades)}</b></span>
              </>
            ) : (
              <TickReadout payload={payload} t={hoverT} />
            )}
          </div>
          <div className="flex items-center gap-4">
            {isCandles ? (
              <>
                <span className="flex items-center gap-1.5 text-muted"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm bg-up" /> ▲ Bullish</span>
                <span className="flex items-center gap-1.5 text-muted"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm bg-down" /> ▼ Bearish</span>
              </>
            ) : (
              <LegendItem color={C.mid} label="Mid" />
            )}
            {showOracle && <LegendItem color={C.oracle} label="Oracle" dashed />}
            {payload.day_info && (
              <span className="font-mono text-[11px] text-dim">
                {payload.day_info.day_type} day
                {payload.day_info.stress_episodes.length > 0 && ` · ${payload.day_info.stress_episodes.length} stress episode${payload.day_info.stress_episodes.length > 1 ? 's' : ''} (shaded)`}
                {news.length > 0 && ' · news: solid = information, dashed = hype'}
              </span>
            )}
          </div>
        </div>
        <EChart option={mainOption} height={460} group={GROUP} onEvents={onEvents} ariaLabel={`${isCandles ? `${iv}-minute candlestick` : 'tick mid-price'} chart of ${payload.meta.ticker} over the session`} />
        {((showXhat && overlayFund.length > 0) || (showLevel && overlayMom.length > 0)) && (
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {showXhat && overlayFund.map((a) => <LegendItem key={a.id} color={colors.get(a.id)!} label={`x̂ ${a.name}`} />)}
            {showLevel && overlayMom.map((a) => <LegendItem key={a.id} color={colors.get(a.id)!} label={`l̂ ${a.name}`} />)}
            <span className="font-mono text-[11px] text-dim">overlays break where they leave the price range · ▲▼ at the edge mark off-scale stretches (hover for the value)</span>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <SectionHeader icon={BarChart3} title="Volume (shares)" caption={`Max: ${fmtInt(maxVol)} shares per ${iv}-min candle`} iconClass="text-up" />
          <EChart option={volOption} height={120} group={GROUP} ariaLabel="Traded volume in shares per candle" />
        </Card>
        <Card>
          <SectionHeader
            icon={Ruler}
            title="Bid-ask spread"
            caption={`Mean ${fmtNum(stats.spread.mean * 100, 1)}¢ · Max ${fmtNum(stats.spread.max * 100, 0)}¢`}
            iconClass="text-spread"
          />
          <EChart option={spreadOption} height={120} group={GROUP} ariaLabel="Bid-ask spread in cents over the session" />
        </Card>
      </div>

      <DepthLadder payload={payload} t={hoverT} />
    </div>
  );
}

function TickReadout({ payload, t }: { payload: SimPayload; t: number | null }) {
  const q = payload.market.quotes;
  const i = t === null ? q.t.length - 1 : Math.max(0, bisectRight(q.t, t));
  return (
    <>
      <span>
        t: <b className="text-text">{clockHMS(t ?? q.t[i])}</b>
      </span>
      <span>Mid <b className="text-text">{fmtPrice(q.mid[i])}</b></span>
      <span>Bid <b className="text-text">{fmtPrice(q.bid[i])}</b></span>
      <span>Ask <b className="text-text">{fmtPrice(q.ask[i])}</b></span>
      <span>Spread <b className="text-text">{((q.ask[i] - q.bid[i]) * 100).toFixed(1)}¢</b></span>
    </>
  );
}

function DepthLadder({ payload, t }: { payload: SimPayload; t: number | null }) {
  const d = payload.market.depth;
  if (!d.t.length) {
    return (
      <Card>
        <SectionHeader icon={BookOpen} title="Order book depth" />
        <p className="text-[13px] text-muted">No order-book snapshots were recorded in this run.</p>
      </Card>
    );
  }
  const i = t === null ? d.t.length - 1 : Math.max(0, Math.min(d.t.length - 1, Math.round(t / 30)));
  // the grid is every 30 s but may skip leading points; pick nearest by time
  const idx = nearestIndex(d.t, t ?? d.t[d.t.length - 1], i);
  const bids = d.bids[idx];
  const asks = d.asks[idx];
  const bidVol = bids.reduce((s, [, q]) => s + q, 0);
  const askVol = asks.reduce((s, [, q]) => s + q, 0);
  const maxQ = Math.max(1, ...bids.map(([, q]) => q), ...asks.map(([, q]) => q));
  const spreadC = bids.length && asks.length ? Math.round((asks[0][0] - bids[0][0]) * 100) : null;
  const imbalance = bidVol + askVol > 0 ? bidVol / (bidVol + askVol) : null;
  const levels = Math.max(bids.length, asks.length);

  return (
    <Card>
      <SectionHeader
        icon={BookOpen}
        title="Order book depth"
        caption={`Book at ${clockHMS(d.t[idx]).slice(0, 8)} · spread ${spreadC ?? '—'}¢ · imbalance ${imbalance === null ? '—' : imbalance.toFixed(2)}`}
        right={<span className="text-[11px] text-dim">{t === null ? 'latest snapshot · hover a chart to scrub' : 'snapshot nearest the hovered time'}</span>}
      />
      <div className="mx-auto max-w-3xl">
        <div className="micro mb-2 grid grid-cols-[1fr_auto_auto_1fr] gap-2 text-center">
          <span className="text-right text-up">Bids (shares)</span>
          <span className="w-20">Bid</span>
          <span className="w-20">Ask</span>
          <span className="text-left text-down">Asks (shares)</span>
        </div>
        <div role="table" aria-label="Order book ladder, 10 levels each side" className="flex flex-col gap-[2px]">
          {Array.from({ length: levels }).map((_, k) => {
            const b = bids[k];
            const a = asks[k];
            return (
              <div role="row" key={k} className="grid grid-cols-[1fr_auto_auto_1fr] items-center gap-2 font-mono text-[12px]">
                <div role="cell" className="flex items-center justify-end gap-2">
                  {b && <span className="text-muted">{fmtInt(b[1])}</span>}
                  <div className="h-4 w-full max-w-[260px] overflow-hidden rounded-sm">
                    {b && <div className="ml-auto h-full rounded-l-sm bg-up/70" style={{ width: `${(b[1] / maxQ) * 100}%` }} />}
                  </div>
                </div>
                <span role="cell" className={cn('w-20 text-right', b ? 'text-emerald-300' : 'text-dim')}>{b ? b[0].toFixed(2) : '—'}</span>
                <span role="cell" className={cn('w-20 text-left', a ? 'text-rose-300' : 'text-dim')}>{a ? a[0].toFixed(2) : '—'}</span>
                <div role="cell" className="flex items-center gap-2">
                  <div className="h-4 w-full max-w-[260px] overflow-hidden rounded-sm">
                    {a && <div className="h-full rounded-r-sm bg-down/70" style={{ width: `${(a[1] / maxQ) * 100}%` }} />}
                  </div>
                  {a && <span className="text-muted">{fmtInt(a[1])}</span>}
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-center font-mono text-[11px] text-dim">
          Bid volume {fmtInt(bidVol)} · Ask volume {fmtInt(askVol)} · bid share {imbalance === null ? '—' : fmtPct(imbalance * 100, 1)}
        </p>
      </div>
    </Card>
  );
}

function nearestIndex(t: number[], x: number, guess: number): number {
  let best = Math.max(0, Math.min(t.length - 1, guess));
  const j = bisectRight(t, x);
  for (const k of [j, j + 1]) {
    if (k >= 0 && k < t.length && Math.abs(t[k] - x) < Math.abs(t[best] - x)) best = k;
  }
  return best;
}

