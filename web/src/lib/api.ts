import type {
  Health,
  LabSummary,
  RunListItem,
  RunParams,
  RunStatus,
  SentimentScore,
  SimPayload,
} from '../types/payload';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>('/api/health'),
  presets: () => request<{ headline: string; sentiment: number }[]>('/api/news/presets'),
  runs: () => request<RunListItem[]>('/api/runs'),
  start: (params: RunParams) =>
    request<{ run_id: string; status: RunStatus['status'] }>('/api/simulations', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  status: (runId: string) => request<RunStatus>(`/api/simulations/${runId}`),
  cancel: (runId: string) =>
    request<{ cancelled: boolean }>(`/api/simulations/${runId}`, { method: 'DELETE' }),
  data: (runId: string) => request<SimPayload>(`/api/simulations/${runId}/data`),
  /** spec v1.3 §9.3: 404 until the realism lab has written its summary */
  labSummary: () => request<LabSummary>('/api/lab/summary'),
  sentiment: (headline: string) =>
    request<SentimentScore>('/api/sentiment', { method: 'POST', body: JSON.stringify({ headline }) }),
};
