import { Loader2 } from 'lucide-react';
import type { RunProgress } from '../hooks/useSimulation';
import { fmtDuration, fmtElapsed } from '../lib/format';
import { ErrorState } from './ui/feedback';
import { Button } from './ui/controls';

export function RunBanner({ progress, onRetry, onDismiss }: { progress: RunProgress; onRetry: () => void; onDismiss: () => void }) {
  if (progress.status === 'failed') {
    return (
      <div className="mb-6">
        <ErrorState title="Simulation failed" error={progress.error ?? 'Unknown error'} onRetry={onRetry} />
        <Button variant="ghost" className="mt-2" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    );
  }
  const queued = progress.status === 'queued';
  return (
    <div role="status" aria-live="polite" className="mb-6 overflow-hidden rounded-[14px] border border-accent/40 bg-accent/10">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3 text-[13px] text-indigo-100">
        <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />
        <span className="font-semibold">{queued ? 'Queued · waiting for the current simulation' : 'Running simulation'}</span>
        {!queued && (
          <span className="font-mono text-indigo-200">
            {fmtElapsed(progress.elapsed)} elapsed
            {progress.expected !== null && ` · ~${fmtDuration(progress.expected)} expected`}
          </span>
        )}
        <span className="text-[12px] text-muted">Previous results stay visible until the new run is ready.</span>
      </div>
      <div className="relative h-1 w-full bg-accent/10">
        <div className="animate-indeterminate absolute inset-y-0 w-2/5 bg-accent" />
      </div>
    </div>
  );
}
