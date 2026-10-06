import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { useId } from 'react';
import { cn } from '../../lib/cn';

// ── Button ────────────────────────────────────────────────────────────────

type Variant = 'primary' | 'secondary' | 'ghost';

export function Button({
  variant = 'secondary',
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      {...rest}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-[10px] text-[13px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        // white on --accent is 4.47:1 (just under 4.5), so the resting fill is
        // --accent-strong (6.3:1) and hover goes one step darker
        variant === 'primary' && 'bg-accent-strong px-4 py-2.5 text-white hover:bg-[#4338ca]',
        variant === 'secondary' && 'border border-border-strong bg-card px-3 py-2 text-text hover:bg-card-hover',
        variant === 'ghost' && 'px-2 py-1 text-muted hover:bg-card-hover hover:text-text',
        className,
      )}
    >
      {children}
    </button>
  );
}

// ── SegmentedControl ──────────────────────────────────────────────────────

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  label,
  size = 'md',
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
  size?: 'sm' | 'md';
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[10px] border border-border bg-bg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-[8px] font-medium transition-colors',
            size === 'sm' ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-[12px]',
            value === o.value ? 'bg-accent-strong text-white' : 'text-muted hover:text-text',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Toggle (checkbox with colour swatch) ──────────────────────────────────

export function Toggle({
  checked,
  onChange,
  label,
  swatch,
  dashed,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  swatch?: string;
  dashed?: boolean;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex cursor-pointer select-none items-center gap-2 text-[12px] text-muted hover:text-text">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-3.5 w-3.5 accent-[#6366F1]" />
      {swatch && (
        <span aria-hidden className="inline-block h-0 w-4" style={{ borderTop: `2px ${dashed ? 'dashed' : 'solid'} ${swatch}` }} />
      )}
      <span>{label}</span>
    </label>
  );
}

// ── Slider (value bubble + min/mid/max ticks) ─────────────────────────────

export function Slider({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  help,
  format = (v: number) => String(v),
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  help?: string;
  format?: (v: number) => string;
}) {
  const id = useId();
  const mid = (min + max) / 2;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label htmlFor={id} className="text-[12px] font-medium text-muted">
          {label}
        </label>
        <span className="rounded-[8px] border border-accent/40 bg-accent/10 px-2 py-0.5 font-mono text-[12px] font-bold text-indigo-200">
          {format(value)}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full cursor-pointer"
        aria-describedby={help ? `${id}-help` : undefined}
      />
      <div className="mt-0.5 flex justify-between font-mono text-[10px] text-dim">
        <span>{format(min)}</span>
        <span>{format(Number.isInteger(step) ? Math.round(mid) : mid)}</span>
        <span>{format(max)}</span>
      </div>
      {help && (
        <p id={`${id}-help`} className="mt-1 text-[11px] text-dim">
          {help}
        </p>
      )}
    </div>
  );
}

// ── Select ────────────────────────────────────────────────────────────────

export function Select<T extends string | number>({
  label,
  value,
  options,
  onChange,
  className,
  hideLabel,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  className?: string;
  hideLabel?: boolean;
}) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className={cn('mb-1.5 block text-[12px] font-medium text-muted', hideLabel && 'sr-only')}>
        {label}
      </label>
      <select
        id={id}
        value={String(value)}
        onChange={(e) => {
          const o = options.find((x) => String(x.value) === e.target.value);
          if (o) onChange(o.value);
        }}
        className="w-full rounded-[10px] border border-border bg-card px-3 py-2 font-mono text-[12px] text-text focus:border-border-strong focus:outline-none"
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── NumberInput / TextInput ───────────────────────────────────────────────

export function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  right,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  right?: ReactNode;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[12px] font-medium text-muted">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={id}
          type="number"
          value={Number.isFinite(value) ? value : ''}
          min={min}
          max={max}
          onChange={(e) => onChange(e.target.value === '' ? NaN : Math.trunc(Number(e.target.value)))}
          className="w-full rounded-[10px] border border-border bg-card px-3 py-2 font-mono text-[13px] text-text focus:border-border-strong focus:outline-none"
        />
        {right}
      </div>
    </div>
  );
}

export function TextInput({
  label,
  value,
  onChange,
  placeholder,
  error,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  error?: string | null;
  mono?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[12px] font-medium text-muted">
        {label}
      </label>
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-err` : undefined}
        className={cn(
          'w-full rounded-[10px] border bg-card px-3 py-2 text-[13px] text-text focus:outline-none',
          mono && 'font-mono',
          error ? 'border-down/60' : 'border-border focus:border-border-strong',
        )}
      />
      {error && (
        <p id={`${id}-err`} className="mt-1 text-[11px] text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}
