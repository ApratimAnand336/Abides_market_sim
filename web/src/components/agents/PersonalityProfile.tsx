import { Brain } from 'lucide-react';
import type { ParamRange } from '../../types/payload';
import { formatParam, type ParamDef } from '../../config/agentParams';
import { Card, SectionHeader } from '../ui/Card';
import { Missing } from '../ui/Tooltip';
import { cn } from '../../lib/cn';

function position(v: number, r: ParamRange): number {
  if (r.max === r.min) return 1;
  const p = r.scale === 'log' ? (Math.log(v) - Math.log(r.min)) / (Math.log(r.max) - Math.log(r.min)) : (v - r.min) / (r.max - r.min);
  return Math.max(0, Math.min(1, p));
}

/** Grid of hyperparameter cards: value, range and where the value sits in it. */
export function PersonalityProfile({
  params,
  values,
  ranges,
  columns = 3,
}: {
  params: ParamDef[];
  values: Record<string, number>;
  ranges: Record<string, ParamRange>;
  columns?: 3 | 4;
}) {
  return (
    <Card>
      <SectionHeader icon={Brain} title="Agent personality profile" caption="Hyperparameters drawn for this agent, shown within the range they were drawn from" />
      <div className={cn('grid grid-cols-1 gap-3 sm:grid-cols-2', columns === 3 ? 'lg:grid-cols-3' : 'lg:grid-cols-3 2xl:grid-cols-4')}>
        {params.map((d) => {
          const v = values[d.key];
          const r = ranges[d.key];
          const has = typeof v === 'number' && Number.isFinite(v);
          const pct = has && r ? position(v, r) * 100 : 0;
          return (
            <div key={d.key} className="flex flex-col justify-between rounded-[10px] border border-border bg-panel p-3.5 transition-colors hover:border-border-strong">
              <div>
                <div className="mb-1 flex items-start justify-between gap-2">
                  <span className="text-[13px] font-semibold text-text">{d.label}</span>
                  <span
                    className="shrink-0 rounded-[8px] border px-1.5 py-0.5 font-mono text-[11px]"
                    style={{ color: d.color, borderColor: `${d.color}55`, background: `${d.color}14` }}
                  >
                    {d.symbol}
                  </span>
                </div>
                <p className="mb-2 text-[12px] leading-snug text-muted">{d.description}</p>
              </div>
              <div>
                <div className="mb-1.5 flex items-baseline justify-between gap-2 font-mono">
                  <span className="whitespace-nowrap text-[20px] font-bold text-text">{has ? formatParam(v, d.format) : <Missing />}</span>
                  <span className="text-right text-[11px] text-dim">
                    {r ? (r.min === r.max ? 'fixed' : `${formatParam(r.min, d.format)} – ${formatParam(r.max, d.format)}${r.scale === 'log' ? ' (log)' : ''}`) : '—'}
                  </span>
                </div>
                <div
                  className="h-1.5 w-full overflow-hidden rounded-full bg-bg"
                  role="meter"
                  aria-label={`${d.label} position in range`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(pct)}
                >
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: d.color }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
