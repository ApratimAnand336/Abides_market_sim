import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Inbox, RotateCw, X } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Button } from './controls';

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('animate-pulse rounded-[10px] bg-card-hover/70', className)} />;
}

export function EmptyState({ title, body, action }: { title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-[14px] border border-dashed border-border-strong bg-panel/50 px-6 py-12 text-center">
      <Inbox className="h-8 w-8 text-dim" aria-hidden />
      <p className="text-[15px] font-semibold text-text">{title}</p>
      {body && <div className="max-w-xl text-[13px] text-muted">{body}</div>}
      {action}
    </div>
  );
}

export function ErrorState({ title, error, onRetry }: { title: string; error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-[14px] border border-down/40 bg-down/5 p-5">
      <div className="mb-2 flex items-center gap-2 text-rose-200">
        <AlertTriangle className="h-4 w-4" aria-hidden />
        <p className="font-semibold">{title}</p>
      </div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-[10px] bg-bg/70 p-3 font-mono text-[11px] text-rose-100/90">
        {error}
      </pre>
      {onRetry && (
        <Button className="mt-3" onClick={onRetry}>
          <RotateCw className="h-3.5 w-3.5" aria-hidden /> Retry
        </Button>
      )}
    </div>
  );
}

export function Toast({ message, tone = 'success', onClose }: { message: string; tone?: 'success' | 'error'; onClose: () => void }) {
  return (
    <div
      role="status"
      className={cn(
        'fixed bottom-5 right-5 z-50 flex max-w-md items-start gap-2 rounded-[10px] border px-4 py-3 text-[13px] shadow-2xl',
        tone === 'success' ? 'border-up/40 bg-[#0B1A17] text-emerald-100' : 'border-down/40 bg-[#1A0B12] text-rose-100',
      )}
    >
      {tone === 'success' ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-up" aria-hidden /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-down" aria-hidden />}
      <span className="flex-1">{message}</span>
      <button type="button" onClick={onClose} aria-label="Dismiss" className="text-muted hover:text-text">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
