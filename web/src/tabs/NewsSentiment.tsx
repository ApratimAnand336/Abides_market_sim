import { useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import { Loader2, Newspaper, Sparkles, Timer, TrendingUp } from 'lucide-react';
import type { NewsRecord, SentimentScore, SimPayload } from '../types/payload';
import { api } from '../lib/api';
import { EChart } from '../charts/EChart';
import { C, axisTooltip, grid, insideZoom, pairs, timeAxis, tipHtml, valueAxis } from '../charts/theme';
import { bisectRight, newsMarkLine } from '../charts/series';
import { clockHMS, escapeHtml, fmtBps, fmtPct, fmtPctSigned, fmtPrice, fmtSci, fmtSigned } from '../lib/format';
import { useQueryFlag } from '../lib/urlState';
import { Card, LegendItem, SectionHeader } from '../components/ui/Card';
import { KpiCard } from '../components/ui/KpiCard';
import { Button, Toggle } from '../components/ui/controls';
import { SentimentChip } from '../components/ui/Badge';
import { DataTable, type Column } from '../components/ui/DataTable';
import { EmptyState } from '../components/ui/feedback';
import { cn } from '../lib/cn';

const GROUP = 'news';

const bps = (after: number | null, before: number | null) => (after === null || before === null || before === 0 ? null : (after / before - 1) * 1e4);

export function NewsSentiment({ payload, finbertAvailable }: { payload: SimPayload; finbertAvailable: boolean }) {
  const duration = payload.meta.session.duration_s;
  const { news, market } = payload;
  const [showOracle, setShowOracle] = useQueryFlag('nOracle', false);
  const names = useMemo(() => {
    const m = new Map<number, string>();
    for (const a of [...payload.agents.fundamental, ...payload.agents.momentum]) m.set(a.id, a.name);
    return m;
  }, [payload]);

  const impactOption = useMemo<EChartsOption>(() => {
    const ml = newsMarkLine(news);
    for (const d of ml.data) d.label.formatter = `${clockHMS(d.xAxis).slice(0, 5)}  ${d.label.formatter}`;
    return {
      grid: grid({ top: 28, bottom: 28 }),
      xAxis: timeAxis(duration),
      yAxis: valueAxis('price'),
      dataZoom: insideZoom(),
      tooltip: axisTooltip((params: any[]) => {
        const t = params?.[0]?.axisValue;
        const i = bisectRight(market.quotes.t, t);
        if (i < 0) return '';
        const rows = [{ label: 'Mid', value: fmtPrice(market.quotes.mid[i]), color: C.mid }];
        if (showOracle) {
          const j = bisectRight(market.oracle.t, t);
          if (j >= 0) rows.push({ label: 'Oracle', value: fmtPrice(market.oracle.v[j]), color: C.oracle });
        }
        let html = tipHtml(clockHMS(t), rows);
        for (const n of news.filter((n) => Math.abs(n.t - t) <= Math.max(30, duration / 300))) {
          html += `<div style="margin-top:6px;max-width:260px;white-space:normal;color:${n.sentiment >= 0 ? C.up : C.down}">📰 ${escapeHtml(n.headline)}</div>`;
        }
        return html;
      }),
      series: [
        { type: 'line', name: 'Mid', data: pairs(market.quotes.t, market.quotes.mid), showSymbol: false, lineStyle: { color: C.mid, width: 1.5 }, markLine: ml },
        ...(showOracle ? [{ type: 'line' as const, name: 'Oracle', data: pairs(market.oracle.t, market.oracle.v), showSymbol: false, lineStyle: { color: C.oracle, width: 1.25, type: 'dashed' as const } }] : []),
      ],
    };
  }, [news, market, duration, showOracle]);

  const eventOption = useMemo<EChartsOption>(
    () => ({
      grid: grid({ top: 16, bottom: 32, left: 64, right: 44 }),
      xAxis: {
        type: 'value',
        min: -300,
        max: 1800,
        interval: 300,
        axisLabel: { color: C.dim, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, formatter: (v: number) => (v === 0 ? 'news' : `${v > 0 ? '+' : '−'}${Math.abs(v) / 60} min`) },
        axisLine: { lineStyle: { color: C.border } },
        splitLine: { lineStyle: { color: C.border, type: 'dashed' } },
      },
      yAxis: valueAxis((v: number) => `${fmtSigned(v, 0)} bps`),
      tooltip: {
        ...axisTooltip((params: any[]) => {
          const x = params?.[0]?.axisValue;
          if (x === undefined) return '';
          const head = `${x === 0 ? 'at news' : `${x > 0 ? '+' : '−'}${Math.round(Math.abs(x))} s`}`;
          return tipHtml(
            head,
            params.map((p: any) => ({ label: p.seriesName, value: fmtBps(p.value?.[1]), color: p.color })),
          );
        }),
      },
      series: news.map((n, k) => ({
        type: 'line' as const,
        name: `${clockHMS(n.t).slice(0, 5)} ${n.sentiment >= 0 ? '▲' : '▼'}`,
        data: pairs(n.event_window.t_rel, n.event_window.mid_rel_bps),
        showSymbol: false,
        lineStyle: { color: n.sentiment >= 0 ? C.up : C.down, width: 1.5, type: k % 2 ? ('dashed' as const) : ('solid' as const) },
        markLine:
          k === 0
            ? { silent: true, symbol: ['none', 'none'], data: [{ xAxis: 0 }], lineStyle: { color: C.muted, type: 'solid' as const }, label: { show: false } }
            : undefined,
      })),
    }),
    [news],
  );

  const columns: Column<NewsRecord>[] = [
    { key: 't', header: 'Time', sortValue: (n) => n.t, render: (n) => <span className="font-mono">{clockHMS(n.t)}</span> },
    { key: 'headline', header: 'Headline', render: (n) => <span className="block max-w-[320px] text-text">{n.headline}</span> },
    { key: 's', header: 'Sentiment', sortValue: (n) => n.sentiment, render: (n) => <SentimentChip value={n.sentiment} /> },
    { key: 'p', header: 'Price at t', align: 'right', render: (n) => <span className="font-mono">{fmtPrice(n.price_before)}</span> },
    ...(['1m', '5m', '30m'] as const).map<Column<NewsRecord>>((h) => ({
      key: h,
      header: `Δ ${h}`,
      align: 'right',
      sortValue: (n) => bps(n.price_after[h], n.price_before) ?? -Infinity,
      render: (n) => <BpsCell v={bps(n.price_after[h], n.price_before)} />,
    })),
    {
      key: 'fund',
      header: 'Fundamental',
      align: 'right',
      render: (n) => {
        const r = n.reactions.filter((x) => x.kind === 'fundamental');
        if (!r.length) return <span className="text-dim">none</span>;
        const avg = r.reduce((s, x) => s + (x.change_pct ?? 0), 0) / r.length;
        return (
          <span className="whitespace-nowrap font-mono text-[12px]">
            {r.length} · avg {fmtPctSigned(avg, 2)}
          </span>
        );
      },
    },
    {
      key: 'mom',
      header: 'Momentum',
      align: 'right',
      render: (n) => {
        const r = n.reactions.filter((x) => x.kind === 'momentum');
        if (!r.length) return <span className="text-dim" title="Momentum agents ignore news while warming up">none</span>;
        const leaning = r.filter((x) => x.before !== null && (x.after - x.before) * n.sentiment > 0).length;
        return (
          <span className="whitespace-nowrap font-mono text-[12px]">
            {leaning}/{r.length} leaning
          </span>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <FinbertCard available={finbertAvailable} />

      <Card>
        <SectionHeader
          icon={TrendingUp}
          title="Price impact timeline"
          caption="Vertical lines indicate news delivery into the market"
          right={<Toggle checked={showOracle} onChange={setShowOracle} label="Oracle" swatch={C.oracle} dashed />}
        />
        <div className="mb-2 flex flex-wrap gap-4">
          <LegendItem color={C.mid} label="Mid" />
          <LegendItem color={C.up} label="▲ positive news" dashed />
          <LegendItem color={C.down} label="▼ negative news" dashed />
        </div>
        <EChart option={impactOption} height={340} group={GROUP} ariaLabel="Mid price over the session with news delivery times" />
      </Card>

      <Card>
        <SectionHeader icon={Newspaper} title={`Injected news shocks (${news.length})`} caption="Δ = mid move after the news, in basis points; expand a row for per-agent reactions" iconClass="text-spread" />
        {news.length === 0 ? (
          <EmptyState
            title="No news events were injected for this run"
            body="Queue predefined or custom news in the sidebar and run a simulation to observe the market reaction."
          />
        ) : (
          <DataTable
            caption="Injected news and market reaction"
            rows={news}
            columns={columns}
            rowKey={(n) => `${n.t}-${n.headline}`}
            expand={(n) => <Reactions news={n} names={names} />}
          />
        )}
      </Card>

      {news.length > 0 && (
        <Card>
          <SectionHeader icon={Timer} title="Event study" caption="Mid move around each news item (bps vs time from delivery, −5 to +30 min)" iconClass="text-warn" />
          <p className="mb-3 text-[12px] text-muted">
            Read it for under-reaction (a slow drift in the news direction), momentum (the move keeps going) and reversal (it gives back the initial jump).
            Green = positive headline, red = negative.
          </p>
          <div className="mb-2 flex flex-wrap gap-4">
            {news.map((n, k) => (
              <LegendItem key={k} color={n.sentiment >= 0 ? C.up : C.down} dashed={k % 2 === 1} label={`${clockHMS(n.t).slice(0, 5)} ${n.sentiment >= 0 ? '▲' : '▼'} ${n.headline.length > 38 ? `${n.headline.slice(0, 38)}…` : n.headline}`} />
            ))}
          </div>
          <EChart option={eventOption} height={300} ariaLabel="Event study: price path in basis points around each news item" />
        </Card>
      )}
    </div>
  );
}

function BpsCell({ v }: { v: number | null }) {
  if (v === null) return <span className="text-dim" title="After the session close">—</span>;
  return <span className={cn('whitespace-nowrap font-mono', v > 0 ? 'text-up' : v < 0 ? 'text-down' : 'text-muted')}>{`${v > 0 ? '▲' : v < 0 ? '▼' : ''} ${fmtBps(v)}`}</span>;
}

function Reactions({ news, names }: { news: NewsRecord; names: Map<number, string> }) {
  if (!news.reactions.length) return <p className="text-[12px] text-muted">No EKF agent reacted (momentum agents ignore news while warming up).</p>;
  return (
    <table className="w-full max-w-3xl text-[12px]">
      <thead>
        <tr className="micro text-left">
          <th className="py-1 pr-3 font-semibold">Agent</th>
          <th className="py-1 pr-3 font-semibold">Belief</th>
          <th className="py-1 pr-3 text-right font-semibold">Before</th>
          <th className="py-1 pr-3 text-right font-semibold">After</th>
          <th className="py-1 text-right font-semibold">Change</th>
        </tr>
      </thead>
      <tbody>
        {news.reactions.map((r) => (
          <tr key={r.agent_id} className="border-t border-border/60 font-mono">
            <td className="py-1.5 pr-3 text-text">{names.get(r.agent_id) ?? r.agent_id}</td>
            <td className="py-1.5 pr-3 text-muted">{r.kind === 'fundamental' ? 'x̂ (value estimate)' : 'v̂ (trend speed)'}</td>
            <td className="py-1.5 pr-3 text-right">{r.kind === 'fundamental' ? fmtPrice(r.before) : fmtSci(r.before)}</td>
            <td className="py-1.5 pr-3 text-right">{r.kind === 'fundamental' ? fmtPrice(r.after) : fmtSci(r.after)}</td>
            <td className="py-1.5 text-right">
              {r.change_pct !== null ? (
                <span className={r.change_pct > 0 ? 'text-up' : r.change_pct < 0 ? 'text-down' : ''}>{fmtPctSigned(r.change_pct, 2)}</span>
              ) : r.before !== null ? (
                <span className={(r.after - r.before) * news.sentiment > 0 ? 'text-up' : 'text-muted'}>
                  {(r.after - r.before) * news.sentiment > 0 ? 'leans with news' : 'no lean'}
                </span>
              ) : (
                <span className="text-dim">—</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FinbertCard({ available }: { available: boolean }) {
  const [text, setText] = useState('Company reports strong quarterly growth');
  const [score, setScore] = useState<SentimentScore | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setScore(await api.sentiment(text.trim()));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className={cn(!available && 'opacity-70')}>
      <SectionHeader icon={Sparkles} title="FinBERT financial sentiment analyzer" caption="ProsusAI/finbert, scored on the server" iconClass="text-warn" />
      {!available ? (
        <p className="rounded-[10px] border border-dashed border-border-strong bg-bg/50 px-4 py-3 text-[13px] text-muted">
          FinBERT not installed on the server. Install <code className="font-mono text-text">transformers</code> and <code className="font-mono text-text">torch</code> to
          enable.
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-2 sm:flex-row">
            <label htmlFor="finbert-input" className="sr-only">
              Headline to score
            </label>
            <input
              id="finbert-input"
              value={text}
              maxLength={200}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && text.trim() && !busy && run()}
              className="flex-1 rounded-[10px] border border-border bg-panel px-3 py-2 text-[13px] text-text focus:border-border-strong focus:outline-none"
            />
            <Button variant="primary" onClick={run} disabled={!text.trim() || busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
              {busy ? 'Scoring…' : 'Score with FinBERT'}
            </Button>
          </div>
          {err && <p className="mt-2 text-[12px] text-rose-300">{err}</p>}
          {score && (
            <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
              <KpiCard label="Positive" value={fmtPct(score.positive * 100, 1)} />
              <KpiCard label="Negative" value={fmtPct(score.negative * 100, 1)} />
              <KpiCard label="Neutral" value={fmtPct(score.neutral * 100, 1)} />
              <KpiCard
                label="Compound"
                value={<SentimentChipLarge v={score.compound} />}
                caption="positive − negative"
              />
            </div>
          )}
        </>
      )}
    </Card>
  );
}

function SentimentChipLarge({ v }: { v: number }) {
  return (
    <span className={cn(v > 0.05 ? 'text-up' : v < -0.05 ? 'text-down' : 'text-muted')}>
      {v > 0.05 ? '▲ ' : v < -0.05 ? '▼ ' : ''}
      {fmtSigned(v, 4)}
    </span>
  );
}
