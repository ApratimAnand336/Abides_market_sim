import { useMemo } from 'react';
import type { AnyAgent, SimPayload } from '../types/payload';
import { agentColorMap } from '../lib/agents';
import { useQueryParam } from '../lib/urlState';
import { Leaderboard } from '../components/agents/Leaderboard';
import { FundamentalDetail } from '../components/agents/FundamentalDetail';
import { MomentumDetail } from '../components/agents/MomentumDetail';
import { EmptyState } from '../components/ui/feedback';

export function AgentPerformance({ payload }: { payload: SimPayload }) {
  const { fundamental, momentum } = payload.agents;
  const colors = useMemo(() => agentColorMap(payload), [payload]);
  const [faRaw, setFa] = useQueryParam('fa', '');
  const [maRaw, setMa] = useQueryParam('ma', '');

  const fund = fundamental.find((a) => String(a.id) === faRaw) ?? fundamental[0];
  const mom = momentum.find((a) => String(a.id) === maRaw) ?? momentum[0];

  const select = (a: AnyAgent) => {
    if (a.kind === 'fundamental') setFa(String(a.id));
    else setMa(String(a.id));
    // let the detail re-render, then bring it into view
    requestAnimationFrame(() => document.getElementById(a.kind === 'fundamental' ? 'fund-detail' : 'mom-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  if (!fundamental.length && !momentum.length) {
    return <EmptyState title="No EKF agents in this run" body="Run a simulation with at least one fundamental or momentum EKF agent to see agent internals." />;
  }

  return (
    <div className="flex flex-col gap-10">
      <Leaderboard payload={payload} selected={null} onSelect={select} />

      <section id="fund-detail" className="scroll-mt-6">
        <h2 className="micro mb-3 text-text">Fundamental EKF agents ({fundamental.length})</h2>
        {fund ? (
          <FundamentalDetail payload={payload} agent={fund} color={colors.get(fund.id)!} onSelect={(id) => setFa(String(id))} />
        ) : (
          <EmptyState title="No fundamental EKF agents in this run" />
        )}
      </section>

      <section id="mom-detail" className="scroll-mt-6">
        <h2 className="micro mb-3 text-text">Momentum EKF agents ({momentum.length})</h2>
        {mom ? (
          <MomentumDetail payload={payload} agent={mom} color={colors.get(mom.id)!} onSelect={(id) => setMa(String(id))} />
        ) : (
          <EmptyState title="No momentum EKF agents in this run" />
        )}
      </section>
    </div>
  );
}
