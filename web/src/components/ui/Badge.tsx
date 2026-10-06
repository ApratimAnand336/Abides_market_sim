import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export function Chip({ children, className, tone = 'default' }: { children: ReactNode; className?: string; tone?: 'default' | 'accent' }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-[8px] border px-2.5 py-1 font-mono text-[12px]',
        tone === 'default' && 'border-border bg-panel text-muted',
        tone === 'accent' && 'border-accent/40 bg-accent/10 text-indigo-200',
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATE_STYLE: Record<string, string> = {
  BULL: 'border-up/40 bg-up/10 text-emerald-300',
  BEAR: 'border-down/40 bg-down/10 text-rose-300',
  WATCH: 'border-warn/40 bg-warn/10 text-amber-200',
  NEUTRAL: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
};
const STATE_ICON: Record<string, string> = { BULL: '▲', BEAR: '▼', WATCH: '◐', NEUTRAL: '■' };

/** State badge: colour + symbol + name, never colour alone. */
export function StateBadge({ state, prefix }: { state: string; prefix?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-[8px] border px-2 py-0.5 font-mono text-[11px] font-bold',
        STATE_STYLE[state] ?? STATE_STYLE.NEUTRAL,
      )}
    >
      <span aria-hidden>{STATE_ICON[state] ?? '■'}</span>
      {prefix}
      {state}
    </span>
  );
}

export function KindBadge({ kind }: { kind: 'fundamental' | 'momentum' }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-[8px] border px-2 py-0.5 text-[11px] font-semibold',
        kind === 'fundamental' ? 'border-sky-500/40 bg-sky-500/10 text-sky-300' : 'border-violet-500/40 bg-violet-500/10 text-violet-300',
      )}
    >
      {kind === 'fundamental' ? 'Fundamental' : 'Momentum'}
    </span>
  );
}

/** Signed sentiment chip: sign + colour. */
export function SentimentChip({ value }: { value: number }) {
  const tone = value > 0.1 ? 'text-up border-up/40 bg-up/10' : value < -0.1 ? 'text-down border-down/40 bg-down/10' : 'text-muted border-border bg-panel';
  const arrow = value > 0.1 ? '▲' : value < -0.1 ? '▼' : '■';
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-[8px] border px-1.5 py-0.5 font-mono text-[11px] font-bold', tone)}>
      <span aria-hidden>{arrow}</span>
      {value > 0 ? '+' : value < 0 ? '−' : ''}
      {Math.abs(value).toFixed(2)}
    </span>
  );
}
