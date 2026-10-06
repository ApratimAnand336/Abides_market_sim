import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/cn';

export function Card({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn('rounded-[14px] border border-border bg-card p-5', className)}>
      {children}
    </section>
  );
}

/** Section panel (slightly darker than cards) grouping several cards. */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('rounded-[14px] border border-border bg-panel p-5', className)}>{children}</div>;
}

export function SectionHeader({
  icon: Icon,
  title,
  caption,
  right,
  iconClass = 'text-accent',
}: {
  icon?: LucideIcon;
  title: string;
  caption?: ReactNode;
  right?: ReactNode;
  iconClass?: string;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <div className="flex items-center gap-2">
        {Icon && <Icon className={cn('h-4 w-4 shrink-0', iconClass)} aria-hidden />}
        <h3 className="text-[12px] font-bold uppercase tracking-[0.08em] text-text">{title}</h3>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {caption && <span className="font-mono text-[11px] text-muted">{caption}</span>}
        {right}
      </div>
    </div>
  );
}

/** Legend entry: swatch + label (identity never by colour alone: always labelled). */
export function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 font-mono text-[11px] text-muted">
      <span
        aria-hidden
        className="inline-block h-0 w-3.5"
        style={{ borderTop: `2px ${dashed ? 'dashed' : 'solid'} ${color}` }}
      />
      {label}
    </span>
  );
}
