import type { SimPayload } from '../types/payload';

export function NewsSentiment(_: { payload: SimPayload; finbertAvailable: boolean }) {
  return <p className="text-muted">NewsSentiment (coming soon)</p>;
}

