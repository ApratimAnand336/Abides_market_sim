import { Activity, BarChart2, Cpu, Database, Newspaper } from 'lucide-react';
import type { SimPayload } from '../types/payload';
import { fmtInt } from '../lib/format';
import { Modal } from './ui/Modal';

const AGENT_INFO: Record<string, { label: string; text: string }> = {
  ExchangeAgent: {
    label: 'Exchange',
    text: 'Runs the limit order book for the ticker: matches orders by price-time priority and publishes quotes. It never trades.',
  },
  NoiseAgent: {
    label: 'Noise traders',
    text: 'Wake once at a random time and place a single small order in a random direction. They provide background liquidity.',
  },
  ValueAgent: {
    label: 'Value investors',
    text: 'Get noisy private observations of the fundamental value (the oracle) and trade towards it with Bayesian updating.',
  },
  EKF_Fundamentalist: {
    label: 'Fundamental EKF agents',
    text: 'Track a private fundamental-value estimate x̂ with a Kalman filter whose observation noise rises in choppy markets (Kaufman ER). A caution modulator scales size by recent prediction accuracy.',
  },
  AdaptivePOVMarketMakerAgent: {
    label: 'Market makers',
    text: 'Quote ladders on both sides of the book, sized as a share of recent volume, and adapt their spread to market conditions.',
  },
  MomentumAgent: {
    label: 'Stock momentum agents',
    text: 'ABIDES’ simple 20/50 moving-average crossover traders.',
  },
  EKF_Momentum: {
    label: 'Momentum EKF agents',
    text: 'Long-only trend followers: a damped-trend Kalman filter estimates level and speed, a state machine (NEUTRAL / BULL / BEAR / WATCH) decides direction, and a pyramiding ratchet sizes positions.',
  },
  NewsOracleAgent: {
    label: 'News oracle',
    text: 'Broadcasts injected headlines with a sentiment score to every agent at the chosen time.',
  },
};

const TABS = [
  { icon: BarChart2, name: 'Market Overview', text: 'Price as candles or tick mid, with the oracle, agent beliefs and news overlaid; traded volume, spread and the order book ladder.' },
  { icon: Cpu, name: 'Agent Performance', text: 'Leaderboard of all EKF agents, then the internals of one agent: its personality, filter state, caution and cash/inventory over time.' },
  { icon: Newspaper, name: 'News & Sentiment', text: 'Score a headline with FinBERT, see when injected news hit the market, how price moved afterwards and how agents reacted.' },
  { icon: Activity, name: 'Market Health', text: 'Whether the simulated market behaves like a real one: fat tails, no return autocorrelation, volatility clustering, tracking of fundamentals.' },
];

export function GuideModal({ open, onClose, payload }: { open: boolean; onClose: () => void; payload: SimPayload | null }) {
  const counts = payload?.meta.agent_counts ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <Modal open={open} onClose={onClose} title="Guide · how this dashboard works">
      <div className="flex flex-col gap-6 text-[14px] text-muted">
        <section>
          <h3 className="micro mb-3 text-text">Agent line-up {payload && `(${fmtInt(total)} agents in this run)`}</h3>
          {payload ? (
            <ul className="grid gap-2 sm:grid-cols-2">
              {Object.entries(counts).map(([type, n]) => (
                <li key={type} className="rounded-[10px] border border-border bg-card p-3">
                  <div className="mb-1 flex items-baseline justify-between gap-2">
                    <span className="font-semibold text-text">{AGENT_INFO[type]?.label ?? type}</span>
                    <span className="font-mono text-[13px] text-indigo-200">{fmtInt(n)}</span>
                  </div>
                  <p className="text-[12px] leading-relaxed">{AGENT_INFO[type]?.text ?? 'ABIDES agent.'}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p>Run a simulation to see its agent line-up.</p>
          )}
        </section>

        <section>
          <h3 className="micro mb-3 text-text">How to read each tab</h3>
          <ul className="flex flex-col gap-2">
            {TABS.map(({ icon: Icon, name, text }) => (
              <li key={name} className="flex gap-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
                <span>
                  <b className="text-text">{name}:</b> {text}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[12px]">
            Times are the simulated exchange clock (09:30 open). Zooming or hovering one chart in a tab moves every chart in that tab; double-click resets.
          </p>
        </section>

        <section className="flex gap-3 rounded-[10px] border border-up/30 bg-up/5 p-4">
          <Database className="mt-0.5 h-5 w-5 shrink-0 text-up" aria-hidden />
          <div>
            <h3 className="mb-1 font-semibold text-text">What is real data?</h3>
            <p className="text-[13px]">
              Everything. Every price, trade, agent state and statistic on screen comes from the ABIDES simulation’s own logs, exported by the Python
              backend. The browser only draws it; nothing is generated or estimated client-side. A field the run did not record shows as “—”.
            </p>
          </div>
        </section>
      </div>
    </Modal>
  );
}
