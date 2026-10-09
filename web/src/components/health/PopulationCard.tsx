import { Info, Users } from 'lucide-react';
import type { PopulationRow } from '../../types/payload';
import { C } from '../../charts/theme';
import { fmtInt, fmtPct, fmtPrice, fmtUsdSigned } from '../../lib/format';
import { Card, SectionHeader } from '../ui/Card';
import { DataTable, type Column } from '../ui/DataTable';
import { Tooltip } from '../ui/Tooltip';

// one colour per agent class, stable across runs
const CLASS_COLORS: Record<string, string> = {
  NoiseAgent: C.dim,
  ValueAgent: C.oracle, // they see the oracle: same colour as the oracle line
  AdaptiveMarketMakerAgent: C.spread,
  MomentumAgent: C.level,
  FundamentalistAgent: C.pink,
  MomentumEKFAgent: C.mid,
};
const colorOf = (r: PopulationRow) => CLASS_COLORS[r.class_name] ?? C.muted;

// compact dollars so the 11-column table fits its card; exact value on hover
const compact = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 2 });
const usdC = (v: number) => compact.format(v);
const usdCSigned = (v: number) => (v > 0 ? `+${usdC(v)}` : v < 0 ? `−${usdC(-v)}` : usdC(0));

const VALUE_HINT =
  'Value agents look at the hidden true value (with noise) and trade toward it. They place most of the orders, so they decide how tightly the price follows true value.';

/** Market population table and volume-share bar (spec v1.1 D4). */
export function PopulationCard({ rows }: { rows: PopulationRow[] }) {
  const tone = (v: number) => (v > 0 ? 'text-up' : v < 0 ? 'text-down' : 'text-muted');
  const cash = (r: PopulationRow) =>
    r.starting_cash_each.min === r.starting_cash_each.max
      ? usdC(r.starting_cash_each.min)
      : `${usdC(r.starting_cash_each.min)} – ${usdC(r.starting_cash_each.max)}`;

  const columns: Column<PopulationRow>[] = [
    {
      key: 'label',
      header: 'Group',
      sortValue: (r) => r.label,
      render: (r) => (
        <span className="flex items-center gap-2 whitespace-nowrap text-text">
          <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colorOf(r) }} />
          {r.label}
        </span>
      ),
    },
    { key: 'count', header: 'Agents', align: 'right', sortValue: (r) => r.count, render: (r) => <span className="font-mono">{fmtInt(r.count)}</span> },
    { key: 'cash', header: 'Start cash', align: 'right', sortValue: (r) => r.starting_cash_each.min, render: (r) => <span className="font-mono">{cash(r)}</span> },
    { key: 'shares0', header: 'Start shares', align: 'right', sortValue: (r) => r.starting_shares_total, render: (r) => <span className="font-mono">{fmtInt(r.starting_shares_total)}</span> },
    { key: 'wake', header: 'Wakes up', render: (r) => <span className="text-muted">{r.wake_desc}</span> },
    { key: 'orders', header: 'Orders', align: 'right', sortValue: (r) => r.orders_sent, render: (r) => <span className="font-mono">{fmtInt(r.orders_sent)}</span> },
    { key: 'traded', header: 'Traded', align: 'right', sortValue: (r) => r.shares_traded, render: (r) => <span className="font-mono">{fmtInt(r.shares_traded)}</span> },
    {
      key: 'share',
      header: 'Vol. share',
      headerHint: 'Shares this group bought or sold, as a share of all traded shares counted on both sides (the column sums to 100%).',
      align: 'right',
      sortValue: (r) => r.volume_share_pct,
      render: (r) => <span className="font-mono">{fmtPct(r.volume_share_pct, 1)}</span>,
    },
    { key: 'value', header: 'Final value', align: 'right', sortValue: (r) => r.final_value_total, render: (r) => <span className="whitespace-nowrap font-mono" title={fmtPrice(r.final_value_total)}>{usdC(r.final_value_total)}</span> },
    { key: 'pnl', header: 'P&L', align: 'right', sortValue: (r) => r.pnl_total, render: (r) => <span className={`whitespace-nowrap font-mono ${tone(r.pnl_total)}`} title={fmtUsdSigned(r.pnl_total)}>{usdCSigned(r.pnl_total)}</span> },
    {
      key: 'vs_hold',
      header: 'vs holding',
      headerHint: 'Final value minus what the group’s starting cash and shares would be worth at the close.',
      align: 'right',
      sortValue: (r) => r.pnl_vs_hold_total,
      render: (r) => <span className={`whitespace-nowrap font-mono ${tone(r.pnl_vs_hold_total)}`} title={fmtUsdSigned(r.pnl_vs_hold_total)}>{usdCSigned(r.pnl_vs_hold_total)}</span>,
    },
  ];

  return (
    <Card>
      <SectionHeader
        icon={Users}
        title="Market population"
        caption="Every group of traders in this run and its share of the traded volume · values at the closing mid"
        right={
          <Tooltip text={VALUE_HINT}>
            <span tabIndex={0} className="flex cursor-help items-center gap-1 text-[11px] text-muted">
              <Info className="h-3.5 w-3.5 text-oracle" aria-hidden /> Who sets the price?
            </span>
          </Tooltip>
        }
      />
      <div className="mb-4">
        <div className="flex h-6 w-full overflow-hidden rounded-[8px] bg-bg" role="img" aria-label={`Volume share: ${rows.map((r) => `${r.label} ${r.volume_share_pct.toFixed(1)}%`).join(', ')}`}>
          {rows
            .filter((r) => r.volume_share_pct > 0)
            .map((r) => (
              <div
                key={r.class_name}
                title={`${r.label}: ${r.volume_share_pct.toFixed(1)}% of volume`}
                className="h-full border-r-2 border-card last:border-r-0"
                style={{ width: `${r.volume_share_pct}%`, background: colorOf(r) }}
              />
            ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          {rows.map((r) => (
            <span key={r.class_name} className="flex items-center gap-1.5 font-mono text-[11px] text-muted">
              <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: colorOf(r) }} />
              {r.label} <b className="text-text">{fmtPct(r.volume_share_pct, 1)}</b>
            </span>
          ))}
        </div>
      </div>
      <DataTable compact caption="Market population by agent class" rows={rows} columns={columns} rowKey={(r) => r.class_name} initialSort={{ key: 'share', dir: 'desc' }} />
    </Card>
  );
}
