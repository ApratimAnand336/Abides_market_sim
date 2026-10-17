import { SlidersHorizontal } from 'lucide-react';
import type { MarketParams } from '../../types/payload';
import { formatParam, LP_PARAMS, RETAIL_PARAMS, type ParamDef } from '../../config/agentParams';
import { Card, SectionHeader } from '../ui/Card';

function Cards({ title, defs, values }: { title: string; defs: ParamDef[]; values: Record<string, number> }) {
  return (
    <div>
      <div className="micro mb-2 text-muted">{title}</div>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {defs
          .filter((d) => values[d.key] !== undefined && values[d.key] !== null)
          .map((d) => (
            <div key={d.key} className="rounded-[10px] border border-border bg-bg/60 px-3 py-2" title={d.description}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[11px] text-muted">{d.label}</span>
                <span className="font-mono text-[10px]" style={{ color: d.color }}>
                  {d.symbol}
                </span>
              </div>
              <div className="mt-0.5 font-mono text-[14px] text-text">{formatParam(values[d.key], d.format)}</div>
              <div className="mt-0.5 text-[10px] leading-snug text-dim">{d.description}</div>
            </div>
          ))}
      </div>
    </div>
  );
}

/** spec v1.5 A9.3: parameter cards of the retail crowd and of our market makers in this run. */
export function MarketParamsCard({ params }: { params: MarketParams }) {
  if (!params.retail && !params.lp) return null;
  return (
    <Card>
      <SectionHeader icon={SlidersHorizontal} title="Retail crowd and market makers" caption="Fixed parameters of this run (the same for every trader of a group unless noted)" />
      <div className="flex flex-col gap-4">
        {params.retail && <Cards title="Retail (types)" defs={RETAIL_PARAMS} values={params.retail} />}
        {params.lp && <Cards title="Market maker (ours)" defs={LP_PARAMS} values={params.lp} />}
      </div>
    </Card>
  );
}
