// Data contract between the FastAPI backend and the dashboard (spec Section 3).
// Mirrored in Python by api/schema.py, which validates every payload it writes.
//
// Conventions: Seconds = seconds since market open (09:30:00); prices are
// dollars; shares are integers; series are columnar (equal-length arrays).
//
// Deviation from the written spec (also recorded in api/schema.py):
// NewsRecord.price_after["1m"] and ["5m"] are nullable like "30m", because a
// news item near the close has no after-price and none may be invented.

export type Seconds = number;

/** Payload schema this dashboard renders (api/__init__.py SCHEMA_VERSION). */
export const SCHEMA_VERSION = '1.2';

export type EndTime = '10:00:00' | '11:00:00' | '12:00:00' | '14:00:00' | '16:00:00';

export interface NewsInput {
  offset: string; // HH:MM:SS after 09:30
  headline: string;
  sentiment: number; // [-1, 1]
}

export interface RunParams {
  seed: number;
  end_time: EndTime;
  num_fund: number; // FundamentalistAgent count (0–20)
  num_mom: number; // MomentumEKFAgent count (0–12)
  // market population (spec v1.1 D4); the server defaults to 97 / 1000 / 2
  num_value?: number; // ValueAgent count (0–150)
  num_noise?: number; // NoiseAgent count (0–2000)
  num_mm?: number; // market makers (0–2)
  news: NewsInput[];
}

export interface SimPayload {
  schema_version: '1.2';
  meta: {
    run_id: string;
    params: RunParams;
    engine_version: string;
    created_at: string; // ISO 8601
    wall_time_s: number;
    ticker: string;
    session: { open: '09:30:00'; close: string; duration_s: number };
    agent_counts: Record<string, number>; // by ABIDES type
  };
  market: Market;
  stats: MarketStats;
  news: NewsRecord[];
  agents: { fundamental: FundamentalAgent[]; momentum: MomentumAgent[] };
  population: PopulationRow[];
  hyperparam_ranges: Record<'fundamental' | 'momentum', Record<string, ParamRange>>;
  /** spec v1.3 §9.1: single-run realism metrics and grades (api/realism.py). */
  realism: Realism;
  /** spec v1.3 §6.1: scripted true-value events as applied (empty in dashboard runs). */
  oracle_events: OracleEvent[];
}

// ── realism (schema 1.2, spec v1.3 Part 9) ─────────────────────────────────

export type Grade = 'PASS' | 'WARN' | 'FAIL';
/** Closed interval [lo, hi]; null = open end. */
export type Interval = [number | null, number | null];

export interface Band {
  id: string; // G1 … G13
  key: string; // metric key in realism.metrics
  label: string;
  unit: string;
  pass: Interval[];
  warn: Interval[];
  text: string; // human-readable band
  note: string; // "what it means"
  scope: 'run' | 'lab';
  source: string;
  transform?: 'abs';
  rule?: 'clustering' | 'spread';
  metrics?: string[];
}

export interface Realism {
  bands: Band[];
  /** Part 3 values of this run (scalars; ac_1_5, acf_abs and gap_rho are lists). */
  metrics: Record<string, number | null | number[]>;
  /** G1, G3–G11 of this single run (null: not computable, e.g. too short a session). */
  grades: Record<string, Grade | null>;
}

export interface OracleEvent {
  type: 'jump' | 'vol';
  [k: string]: number | string | null;
}

/** GET /api/lab/summary (docs/v1.3/lab/summary.json), the parts the Realism tab reads. */
export interface LabAgg {
  median: number | null;
  p10: number | null;
  p90: number | null;
  min: number | null;
  max: number | null;
  n_seeds: number;
  status: 'OK' | 'INCOMPLETE';
}
export interface LabGrade {
  id: string;
  label: string;
  unit: string;
  band: string;
  stats: Record<string, LabAgg> | { value: number | null; n_seeds: number; status: string };
  grade: Grade | 'INCOMPLETE' | null;
  pass_share: number | null;
}
export interface LabSummary {
  generated: string;
  seeds: number[];
  configs: Record<string, { label: string; n_runs: number; engine_versions: string[]; dates: string[]; scorecard: Record<string, LabGrade> }>;
  impact: null | {
    G12: { value: number | null; ci: [number, number] | null; grade: Grade | 'N/A' | null };
    G13: { value: number | null; grade: Grade | 'INCOMPLETE' | null };
  };
}

/** One row per agent class in the market (spec v1.1 D4). Money in $. */
export interface PopulationRow {
  label: string;
  class_name: string;
  count: number;
  starting_cash_each: { min: number; max: number };
  starting_shares_total: number;
  wake_desc: string;
  orders_sent: number;
  shares_traded: number; // both sides of every execution
  volume_share_pct: number; // rows sum to 100
  final_value_total: number; // cash + shares × close
  pnl_total: number;
  pnl_vs_hold_total: number;
}

export interface ParamRange {
  min: number;
  max: number;
  scale?: 'log';
}

export interface Market {
  quotes: { t: Seconds[]; bid: number[]; ask: number[]; mid: number[] }; // LTTB on mid, ≤ 6000
  candles_1m: {
    t: Seconds[];
    o: number[];
    h: number[];
    l: number[];
    c: number[];
    volume: number[];
    trades: number[];
  };
  oracle: { t: Seconds[]; v: number[] }; // LTTB ≤ 2000
  depth: { t: Seconds[]; bids: [number, number][][]; asks: [number, number][][] }; // every 30 s, 10 levels
  totals: { price_points: number; trades: number; volume_shares: number };
  gap: { t: Seconds[]; v: number[] }; // mid − oracle ($), 1 s grid, LTTB ≤ 2000 (spec v1.1 D5)
}

export interface MarketStats {
  open: number;
  close: number;
  change: number;
  change_pct: number;
  low: number;
  high: number;
  spread: { mean: number; median: number; p95: number; max: number }; // dollars
  spread_ticks: { ticks: number[]; share: number[] }; // 1..10, last bucket = ≥11
  returns_1m: {
    n: number;
    mean: number;
    std: number;
    skew: number;
    excess_kurtosis: number;
    hist: { edges: number[]; counts: number[] };
    normal: { x: number[]; y: number[] };
    acf: number[];
    acf_abs: number[];
    acf_band: number;
  };
  returns_tick: { std: number; excess_kurtosis: number };
  tracking: { rms: number; mean_abs: number; corr: number };
  // spec v1.1 D5: mispricing half-life from rho(L) = exp(−kL)
  gap: { std: number; mean_abs: number; half_life_min: number | null; lags_s: number[]; rho: number[] };
  trades: number;
  volume_shares: number;
}

export interface NewsReaction {
  agent_id: number;
  kind: 'fundamental' | 'momentum';
  before: number | null; // fundamental: x̂ ($); momentum: v̂
  after: number;
  change_pct: number | null;
}

export interface NewsRecord {
  t: Seconds;
  headline: string;
  sentiment: number;
  price_before: number | null;
  price_after: { '1m': number | null; '5m': number | null; '30m': number | null };
  reactions: NewsReaction[];
  event_window: { t_rel: Seconds[]; mid_rel_bps: number[] };
}

export interface AgentBase {
  id: number;
  name: string;
  hyperparams: Record<string, number>;
  start: { cash: number; shares: number; value: number };
  final: {
    cash: number;
    shares: number;
    value: number;
    pnl: number;
    pnl_pct: number;
    // spec v1.1 D2: final value − (start cash + start shares × close)
    pnl_vs_hold: number;
    pnl_vs_hold_pct: number;
    exposure_pct: number;
    n_orders: number;
    n_fills: number;
  };
  holdings: { t: Seconds[]; cash: number[]; shares: number[] };
  value_1m: { t: Seconds[]; v: number[] };
  fills: { t: Seconds[]; side: ('BUY' | 'SELL')[]; qty: number[]; price: number[] };
}

export interface FundamentalAgent extends AgentBase {
  kind: 'fundamental';
  ekf: {
    t: Seconds[];
    mid: number[];
    x_hat: number[];
    P: number[]; // $²
    R: number[]; // $²
    K: number[];
    ER: number[];
    ER_smooth: number[];
    Q: number[]; // $², process noise added at each prediction (spec v1.1 F3)
    sigma_f2: number[]; // $²/s, the agent's estimate of how fast value moves
  };
  caution: { t: Seconds[]; D: number[]; E: number[]; C: number[] }; // E in $
  news: {
    t: Seconds;
    headline: string;
    sentiment: number;
    shift: number; // signed $
    sigma_move: number; // $, a typical 30-minute move
    x_hat_before: number;
    x_hat_after: number;
    P_before: number; // $²
    P_after: number; // $²
  }[];
}

export type MomState = 'NEUTRAL' | 'BULL' | 'BEAR' | 'WATCH';

export interface MomentumAgent extends AgentBase {
  kind: 'momentum';
  warmup_end_t: Seconds | null;
  thresholds: { theta_in: number; theta_out: number };
  kf: {
    t: Seconds[];
    mid: number[];
    level: number[];
    band_lo: number[];
    band_hi: number[];
    v_hat: number[];
    T: number[];
    K0: number[];
    K1: number[];
    ER: number[];
    ER_smooth: number[];
    epsbar: number[];
    g_Q: number[];
  };
  caution: { t: Seconds[]; C: number[]; E: number[] };
  states: {
    t: Seconds;
    from: string | null;
    to: MomState;
    reason: string;
    L: number | null;
    extreme: number | null;
  }[];
  decisions: {
    counts: { order: number; dead_band: number; anti_chase: number; no_cash: number; no_shares: number };
    series: {
      t: Seconds[];
      a: number[];
      s: number[];
      m: number[];
      g: number[];
      e_target: number[];
      exposure: number[];
      // optional (momentum agent spec v1.1); shown only when present
      added?: (number | null)[];
      exit_pending?: (number | null)[];
      sigma_hat2?: (number | null)[];
      sigma_tau?: (number | null)[];
    };
  };
  news: { t: Seconds; headline: string; sentiment: number; v_hat_after: number }[];
}

export type AnyAgent = FundamentalAgent | MomentumAgent;

// ── API responses ────────────────────────────────────────────────────────

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface RunStatus {
  run_id: string;
  status: JobStatus;
  elapsed_s: number;
  expected_s: number | null;
  error?: string;
}

export interface RunListItem {
  run_id: string;
  params: RunParams;
  created_at: string;
  wall_time_s: number;
  summary: { close: number; change_pct: number; trades: number };
}

export interface Health {
  ok: boolean;
  engine_version: string;
  finbert_available: boolean;
}

export interface SentimentScore {
  positive: number;
  negative: number;
  neutral: number;
  compound: number;
}
