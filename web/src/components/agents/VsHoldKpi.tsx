import { Scale } from 'lucide-react';
import type { AgentBase } from '../../types/payload';
import { fmtPctSigned, fmtUsdSigned } from '../../lib/format';
import { KpiCard } from '../ui/KpiCard';
import { VS_HOLD_HINT } from './Leaderboard';

/** "vs holding" P&L (spec v1.1 D2) next to the plain P&L. */
export function VsHoldKpi({ agent }: { agent: AgentBase }) {
  const v = agent.final.pnl_vs_hold;
  return (
    <KpiCard
      label="P&L vs holding"
      value={fmtUsdSigned(v)}
      delta={fmtPctSigned(agent.final.pnl_vs_hold_pct, 3)}
      deltaTone={v > 0 ? 'up' : v < 0 ? 'down' : 'flat'}
      caption={`plain P&L ${fmtUsdSigned(agent.final.pnl)}`}
      icon={Scale}
      iconClass="text-warn"
      hint={VS_HOLD_HINT}
    />
  );
}
