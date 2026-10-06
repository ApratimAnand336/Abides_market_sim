import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Tooltip } from './Tooltip';

export function KpiCard({
  label,
  value,
  delta,
  deltaTone,
  caption,
  icon: Icon,
  iconClass = 'text-accent',
  hint,
}: {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  deltaTone?: 'up' | 'down' | 'flat';
  caption?: ReactNode;
  icon?: LucideIcon;
  iconClass?: string;
  hint?: string;
}) {
  const body = (
    <div className="flex h-full flex-col rounded-[14px] border border-border bg-card px-5 py-4">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="micro">{label}</span>
        {Icon && <Icon className={cn('h-4 w-4 shrink-0', iconClass)} aria-hidden />}
      </div>
      <p className="font-mono text-[26px] font-bold leading-tight text-text">{value}</p>
      {delta && (
        <p
          className={cn(
            'mt-0.5 font-mono text-[12px] font-medium',
            deltaTone === 'up' && 'text-up',
            deltaTone === 'down' && 'text-down',
            deltaTone === 'flat' && 'text-muted',
          )}
        >
          {delta}
        </p>
      )}
      {caption && <p className="mt-0.5 text-[11px] text-muted">{caption}</p>}
    </div>
  );
  return hint ? <Tooltip text={hint}>{body}</Tooltip> : body;
}
