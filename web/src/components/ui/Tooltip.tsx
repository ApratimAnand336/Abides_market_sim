import { useId, useState, type ReactNode } from 'react';

/** Lightweight hover/focus tooltip (keyboard reachable via the wrapped element). */
export function Tooltip({ text, children, className }: { text: string; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className={`relative inline-flex ${className ?? ''}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      aria-describedby={open ? id : undefined}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          id={id}
          className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-[260px] -translate-x-1/2 rounded-lg border border-border-strong bg-[#0B1220] px-2.5 py-1.5 text-[11px] leading-snug text-text shadow-xl"
        >
          {text}
        </span>
      )}
    </span>
  );
}

/** "—" placeholder for a field the run did not record (ground rule 1). */
export function Missing() {
  return (
    <Tooltip text="Not recorded in this run">
      <span tabIndex={0} className="cursor-help text-dim">
        —
      </span>
    </Tooltip>
  );
}
