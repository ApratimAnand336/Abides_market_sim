import { AGENT_PALETTE } from '../charts/theme';
import type { AnyAgent, SimPayload } from '../types/payload';

/** All EKF agents in a fixed order: fundamental first, then momentum. */
export function allAgents(p: SimPayload): AnyAgent[] {
  return [...p.agents.fundamental, ...p.agents.momentum];
}

/** Colour by agent order (never by rank), cycling only past 10 agents. */
export function agentColorMap(p: SimPayload): Map<number, string> {
  const m = new Map<number, string>();
  allAgents(p).forEach((a, i) => m.set(a.id, AGENT_PALETTE[i % AGENT_PALETTE.length]));
  return m;
}

/** Current (last) state of a momentum agent: NEUTRAL until its first transition. */
export function currentState(a: { states: { to: string }[]; warmup_end_t: number | null }): string {
  if (a.warmup_end_t === null) return 'WARMING UP';
  return a.states.length ? a.states[a.states.length - 1].to : 'NEUTRAL';
}
