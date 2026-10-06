// Data layer (spec 7.1): TanStack Query for health, presets, cached runs,
// payloads (cached in memory per run_id) and the run lifecycle.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { RunParams, RunStatus, SimPayload } from '../types/payload';

const POLL_MS = 1500;

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: 60_000 });
}

export function usePresets() {
  return useQuery({ queryKey: ['presets'], queryFn: api.presets });
}

export function useRunList() {
  return useQuery({ queryKey: ['runs'], queryFn: api.runs, staleTime: 0 });
}

const payloadKey = (runId: string) => ['payload', runId] as const;

export function usePayload(runId: string | null) {
  return useQuery({
    queryKey: payloadKey(runId ?? ''),
    queryFn: () => api.data(runId!),
    enabled: !!runId,
    staleTime: Infinity,
    gcTime: 30 * 60_000,
  });
}

export interface RunProgress {
  runId: string;
  status: RunStatus['status'];
  elapsed: number;
  expected: number | null;
  error?: string;
}

/**
 * The displayed run plus an optional pending run. The previous payload stays
 * on screen (dimmed by the UI) until the new one has been fetched, then the
 * displayed run id swaps atomically.
 */
export function useRunController(initialRunId: string | null) {
  const qc = useQueryClient();
  const [displayedId, setDisplayedId] = useState<string | null>(initialRunId);
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [lastParams, setLastParams] = useState<RunParams | null>(null);
  const pendingRef = useRef<string | null>(null);

  useEffect(() => {
    if (initialRunId && !displayedId) setDisplayedId(initialRunId);
  }, [initialRunId, displayedId]);

  const status = useQuery({
    queryKey: ['status', progress?.runId ?? ''],
    queryFn: () => api.status(progress!.runId),
    enabled: !!progress && (progress.status === 'queued' || progress.status === 'running'),
    refetchInterval: POLL_MS,
  });

  // advance the progress from each poll; on done, fetch then swap
  useEffect(() => {
    const s = status.data;
    if (!s || !progress || s.run_id !== progress.runId) return;
    if (s.status === 'done') {
      pendingRef.current = s.run_id;
      qc.fetchQuery({ queryKey: payloadKey(s.run_id), queryFn: () => api.data(s.run_id) })
        .then(() => {
          if (pendingRef.current !== s.run_id) return;
          setDisplayedId(s.run_id);
          setProgress(null);
          qc.invalidateQueries({ queryKey: ['runs'] });
        })
        .catch((e: Error) => setProgress({ ...progress, status: 'failed', error: e.message }));
    } else {
      setProgress({ runId: s.run_id, status: s.status, elapsed: s.elapsed_s, expected: s.expected_s, error: s.error });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.data]);

  // local elapsed ticker between polls
  useEffect(() => {
    if (!progress || (progress.status !== 'running' && progress.status !== 'queued')) return;
    const id = window.setInterval(() => {
      setProgress((p) => (p && p.status === 'running' ? { ...p, elapsed: p.elapsed + 0.25 } : p));
    }, 250);
    return () => window.clearInterval(id);
  }, [progress?.status, progress?.runId]);

  const start = useCallback(
    async (params: RunParams) => {
      setLastParams(params);
      const res = await api.start(params);
      if (res.status === 'done') {
        // cache hit: just load it
        await qc.fetchQuery({ queryKey: payloadKey(res.run_id), queryFn: () => api.data(res.run_id) });
        setDisplayedId(res.run_id);
        setProgress(null);
        qc.invalidateQueries({ queryKey: ['runs'] });
        return { cached: true, runId: res.run_id };
      }
      setProgress({ runId: res.run_id, status: res.status, elapsed: 0, expected: null });
      return { cached: false, runId: res.run_id };
    },
    [qc],
  );

  const cancel = useCallback(async () => {
    if (!progress) return;
    pendingRef.current = null;
    if (progress.status === 'queued') await api.cancel(progress.runId).catch(() => undefined);
    setProgress(null);
  }, [progress]);

  const retry = useCallback(async () => {
    if (lastParams) await start(lastParams);
  }, [lastParams, start]);

  const dismissError = useCallback(() => setProgress(null), []);

  const load = useCallback((runId: string) => {
    pendingRef.current = null;
    setProgress(null);
    setDisplayedId(runId);
  }, []);

  return { displayedId, progress, start, cancel, retry, dismissError, load };
}

export type { SimPayload };
