import { Activity, BarChart3, DollarSign, Layers, Menu, Users } from 'lucide-react';
import type { SimPayload } from '../types/payload';
import { fmtInt, fmtPrice, fmtPriceDelta } from '../lib/format';
import { Chip } from './ui/Badge';
import { KpiCard } from './ui/KpiCard';
import { Button } from './ui/controls';

export function Header({ payload, onOpenControls }: { payload: SimPayload | null; onOpenControls: () => void }) {
  const m = payload?.meta;
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        <Button variant="secondary" className="mt-1 lg:hidden" onClick={onOpenControls} aria-label="Open simulation controls">
          <Menu className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="flex items-center gap-2.5 text-[22px] font-bold tracking-tight text-text md:text-[28px]">
            <BarChart3 className="h-7 w-7 text-accent" aria-hidden />
            FinVerse · Market Simulation Dashboard
          </h1>
          <p className="mt-1 text-[13px] text-muted md:text-[14px]">
            Multi-agent discrete-event market simulation (ABIDES) with Kalman-filter investor agents.
          </p>
        </div>
      </div>
      {m && (
        <div className="flex flex-wrap items-center gap-2">
          <Chip>
            Ticker: <b className="text-text">{m.ticker}</b>
          </Chip>
          <Chip>
            Seed: <b className="text-indigo-300">{m.params.seed}</b>
          </Chip>
          <Chip>
            Close: <b className="text-text">{m.session.close}</b>
          </Chip>
          <Chip>
            Run: <b className="text-text">{m.run_id}</b>
          </Chip>
          <Chip>
            Engine: <b className="text-text">{m.engine_version}</b>
          </Chip>
        </div>
      )}
    </header>
  );
}

export function KpiRow({ payload }: { payload: SimPayload }) {
  const s = payload.stats;
  const t = payload.market.totals;
  const nf = payload.agents.fundamental.length;
  const nm = payload.agents.momentum.length;
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <KpiCard label="Opening price" value={fmtPrice(s.open)} caption="Market open (09:30)" icon={DollarSign} iconClass="text-up" />
      <KpiCard
        label="Closing price"
        value={fmtPrice(s.close)}
        delta={fmtPriceDelta(s.change, s.change_pct)}
        deltaTone={s.change > 0 ? 'up' : s.change < 0 ? 'down' : 'flat'}
        icon={Activity}
      />
      <KpiCard label="Price points" value={fmtInt(t.price_points)} caption="Order-book quote updates" icon={Layers} iconClass="text-mid" />
      <KpiCard
        label="Trades executed"
        value={fmtInt(t.trades)}
        caption={`${fmtInt(t.volume_shares)} shares`}
        icon={BarChart3}
        iconClass="text-spread"
      />
      <KpiCard label="EKF agents" value={fmtInt(nf + nm)} caption={`${nf} Fund · ${nm} Mom`} icon={Users} iconClass="text-warn" />
    </div>
  );
}
