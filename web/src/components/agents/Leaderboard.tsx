import { Trophy } from 'lucide-react';
import type { AnyAgent, SimPayload } from '../../types/payload';
import { allAgents, agentColorMap, currentState } from '../../lib/agents';
import { fmtInt, fmtPct, fmtPctSigned, fmtPrice, fmtUsdSigned } from '../../lib/format';
import { Card, SectionHeader } from '../ui/Card';
import { KindBadge, StateBadge } from '../ui/Badge';
import { DataTable, type Column } from '../ui/DataTable';

export function Leaderboard({ payload, selected, onSelect }: { payload: SimPayload; selected: number | null; onSelect: (a: AnyAgent) => void }) {
  const colors = agentColorMap(payload);
  const rows = allAgents(payload);
  const tone = (v: number) => (v > 0 ? 'text-up' : v < 0 ? 'text-down' : 'text-muted');

  const columns: Column<AnyAgent>[] = [
    {
      key: 'name',
      header: 'Agent',
      sortValue: (a) => a.name,
      render: (a) => (
        <span className="flex items-center gap-2 font-mono text-[12px] text-text">
          <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colors.get(a.id) }} />
          {a.name}
        </span>
      ),
    },
    { key: 'kind', header: 'Type', sortValue: (a) => a.kind, render: (a) => <KindBadge kind={a.kind} /> },
    {
      key: 'state',
      header: 'State',
      sortValue: (a) => (a.kind === 'momentum' ? currentState(a) : ''),
      render: (a) => (a.kind === 'momentum' ? <StateBadge state={currentState(a)} /> : <span className="text-dim">n/a</span>),
    },
    { key: 'value', header: 'Final value', align: 'right', sortValue: (a) => a.final.value, render: (a) => <span className="font-mono">{fmtPrice(a.final.value)}</span> },
    {
      key: 'pnl',
      header: 'P&L ($)',
      align: 'right',
      sortValue: (a) => a.final.pnl,
      render: (a) => <span className={`font-mono ${tone(a.final.pnl)}`}>{fmtUsdSigned(a.final.pnl)}</span>,
    },
    {
      key: 'pnl_pct',
      header: 'P&L (%)',
      align: 'right',
      sortValue: (a) => a.final.pnl_pct,
      render: (a) => (
        <span className={`font-mono ${tone(a.final.pnl_pct)}`}>
          {a.final.pnl_pct > 0 ? '▲ ' : a.final.pnl_pct < 0 ? '▼ ' : ''}
          {fmtPctSigned(a.final.pnl_pct, 3)}
        </span>
      ),
    },
    { key: 'exposure', header: 'Exposure %', align: 'right', sortValue: (a) => a.final.exposure_pct, render: (a) => <span className="font-mono">{fmtPct(a.final.exposure_pct, 1)}</span> },
    { key: 'fills', header: 'Fills', align: 'right', sortValue: (a) => a.final.n_fills, render: (a) => <span className="font-mono">{fmtInt(a.final.n_fills)}</span> },
  ];

  return (
    <Card>
      <SectionHeader icon={Trophy} title="Leaderboard" caption="P&L against total starting wealth · click a row to inspect the agent" iconClass="text-warn" />
      <DataTable
        caption="EKF agent leaderboard"
        rows={rows}
        columns={columns}
        rowKey={(a) => a.id}
        initialSort={{ key: 'pnl_pct', dir: 'desc' }}
        onRowClick={onSelect}
        selectedKey={selected ?? undefined}
      />
    </Card>
  );
}
