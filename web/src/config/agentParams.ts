// Labels, descriptions and formats for agent hyperparameters (spec 6.3.3).
// Values come from the payload's agent.hyperparams; ranges come from the
// payload's hyperparam_ranges (Python param_ranges.py, the single source).

export type ParamFormat =
  | { kind: 'int'; unit?: string }
  | { kind: 'float'; digits: number }
  | { kind: 'percent'; digits: number } // value is a fraction, shown ×100
  | { kind: 'seconds' };

export interface ParamDef {
  key: string;
  symbol: string;
  label: string;
  description: string;
  format: ParamFormat;
  color: string;
}

export function formatParam(v: number, f: ParamFormat): string {
  switch (f.kind) {
    case 'int':
      return `${Math.round(v)}${f.unit ? ` ${f.unit}` : ''}`;
    case 'float':
      return v.toFixed(f.digits);
    case 'percent':
      return `${(v * 100).toFixed(f.digits)}%`;
    case 'seconds':
      return v >= 120 ? `${(v / 60).toFixed(1)} min` : `${v.toFixed(0)} s`;
  }
}

export const FUNDAMENTAL_PARAMS: ParamDef[] = [
  { key: 'er_window', symbol: 'n_ER', label: 'Efficiency-ratio memory', description: 'Observations used to judge trend vs noise', format: { kind: 'int', unit: 'obs' }, color: '#38BDF8' },
  { key: 'delta', symbol: 'δ', label: 'Noise sensitivity', description: 'Base observation noise as a fraction of price', format: { kind: 'float', digits: 4 }, color: '#34D399' },
  { key: 'lambda_er', symbol: 'λ_ER', label: 'Distrust of choppy prices', description: 'Penalty on observations when the market is choppy', format: { kind: 'float', digits: 2 }, color: '#818CF8' },
  { key: 'sigma_n', symbol: 'σ_n', label: 'Private signal noise', description: 'Noise on the agent’s private look at the fundamental', format: { kind: 'float', digits: 0 }, color: '#C084FC' },
  { key: 'gamma', symbol: 'γ', label: 'Caution memory', description: 'How long past right/wrong calls affect confidence', format: { kind: 'float', digits: 3 }, color: '#FB7185' },
  { key: 'k', symbol: 'k', label: 'Caution sensitivity', description: 'How quickly confidence reacts to results', format: { kind: 'float', digits: 3 }, color: '#2DD4BF' },
  { key: 'mu', symbol: 'μ', label: 'Limit safety margin', description: 'How far from its estimate it will pay or sell', format: { kind: 'percent', digits: 2 }, color: '#FDE047' },
  { key: 'q', symbol: 'q', label: 'Belief flexibility', description: 'How fast it assumes true value drifts; higher keeps the estimate responsive', format: { kind: 'float', digits: 2 }, color: '#F59E0B' },
  { key: 'a_max', symbol: 'a_max', label: 'Maximum tilt', description: 'Largest move of its stock share away from 50% on a strong view', format: { kind: 'percent', digits: 0 }, color: '#4ADE80' },
  { key: 'z0', symbol: 'z₀', label: 'Conviction scale', description: 'Edge, in units of its own uncertainty, that earns most of the tilt', format: { kind: 'float', digits: 2 }, color: '#F472B6' },
  { key: 's_max', symbol: 's_max', label: 'Step size cap', description: 'Largest trade per decision, as a share of wealth', format: { kind: 'percent', digits: 1 }, color: '#FB923C' },
  { key: 'b_f', symbol: 'b_f', label: 'Dead band', description: 'Skips trades smaller than this share of wealth', format: { kind: 'percent', digits: 1 }, color: '#94A3B8' },
  { key: 'k_news', symbol: 'k_news', label: 'News reaction', description: 'Belief shift per headline, in typical 30-minute price moves', format: { kind: 'float', digits: 2 }, color: '#22D3EE' },
];

export const MOMENTUM_PARAMS: ParamDef[] = [
  { key: 'tau_ratio', symbol: 'τ/w̄', label: 'Trend memory (in decisions)', description: 'Trend lifetime measured in decisions; τ = this × decision interval', format: { kind: 'float', digits: 1 }, color: '#F59E0B' },
  { key: 'tau', symbol: 'τ', label: 'Trend memory', description: 'How long the agent believes a trend lasts (= τ/w̄ × w̄, not drawn directly)', format: { kind: 'seconds' }, color: '#FCD34D' },
  { key: 'wake_mean', symbol: 'w̄', label: 'Decision interval', description: 'Average time between decisions', format: { kind: 'seconds' }, color: '#38BDF8' },
  { key: 'theta_in', symbol: 'θ_in', label: 'Entry threshold', description: 'Trend strength needed to enter', format: { kind: 'float', digits: 2 }, color: '#34D399' },
  { key: 'theta_out', symbol: 'θ_out', label: 'Stay threshold', description: 'Trend strength needed to stay in', format: { kind: 'float', digits: 2 }, color: '#FBBF24' },
  { key: 'ER_min', symbol: 'ER_min', label: 'Choppiness gate', description: 'Minimum efficiency ratio to allow an entry', format: { kind: 'float', digits: 2 }, color: '#A78BFA' },
  { key: 'kappa_l', symbol: 'κ_l', label: 'Real share of wiggle', description: 'How much of price noise it treats as real level moves', format: { kind: 'float', digits: 3 }, color: '#60A5FA' },
  { key: 'kappa_v', symbol: 'κ_v', label: 'Trend size vs noise', description: 'How big a trend it expects relative to noise', format: { kind: 'float', digits: 2 }, color: '#F472B6' },
  { key: 'lambda_er', symbol: 'λ_ER', label: 'Distrust of choppy prices', description: 'Penalty on observations when the market is choppy', format: { kind: 'float', digits: 2 }, color: '#818CF8' },
  { key: 'kappa_R', symbol: 'κ_R', label: 'Observation noise scale', description: 'How noisy it assumes each price is', format: { kind: 'float', digits: 2 }, color: '#2DD4BF' },
  { key: 'c_P', symbol: 'c_P', label: 'Initial self-doubt', description: 'Uncertainty right after warm-up', format: { kind: 'float', digits: 2 }, color: '#C084FC' },
  { key: 'T_0', symbol: 'T₀', label: 'Evidence for full size', description: 'Trend strength that earns full position size', format: { kind: 'float', digits: 2 }, color: '#4ADE80' },
  { key: 'lambda_v', symbol: 'λ_v', label: 'Murkiness penalty', description: 'Shrinks positions in choppy markets', format: { kind: 'float', digits: 2 }, color: '#FB923C' },
  { key: 'e_max', symbol: 'e_max', label: 'Maximum exposure', description: 'Largest share of wealth it holds in stock', format: { kind: 'percent', digits: 1 }, color: '#10B981' },
  { key: 'k_stop', symbol: 'k_stop', label: 'Trailing stop', description: 'Pull-back (in typical moves) that ends a trend', format: { kind: 'float', digits: 2 }, color: '#F43F5E' },
  { key: 'k_add', symbol: 'k_add', label: 'Add spacing', description: 'New-high distance required before adding', format: { kind: 'float', digits: 2 }, color: '#22D3EE' },
  { key: 'k_re', symbol: 'k_re', label: 'Re-entry margin', description: 'How far past the old peak before re-entering', format: { kind: 'float', digits: 2 }, color: '#E879F9' },
  { key: 'mu_m', symbol: 'μ_m', label: 'Anti-chase band', description: 'How far beyond its forecast it will chase', format: { kind: 'float', digits: 2 }, color: '#FDE047' },
  { key: 'eta_news', symbol: 'η_news', label: 'Lean toward headlines', description: 'How far news nudges its trend speed', format: { kind: 'float', digits: 3 }, color: '#A3E635' },
  { key: 'rho_news', symbol: 'ρ_news', label: 'Open-mindedness after news', description: 'How much news widens its uncertainty', format: { kind: 'float', digits: 2 }, color: '#94A3B8' },
  { key: 'gamma', symbol: 'γ', label: 'Caution memory', description: 'How long past right/wrong calls affect confidence', format: { kind: 'float', digits: 3 }, color: '#FB7185' },
  { key: 'k_c', symbol: 'k_c', label: 'Caution sensitivity', description: 'How quickly confidence reacts to results', format: { kind: 'float', digits: 3 }, color: '#14B8A6' },
  { key: 'N_w', symbol: 'N_w', label: 'Warm-up length', description: 'Observations before it starts trading', format: { kind: 'int', unit: 'obs' }, color: '#64748B' },
  { key: 'n_er', symbol: 'n_ER', label: 'Efficiency-ratio memory', description: 'Observations used to judge trend vs noise', format: { kind: 'int', unit: 'obs' }, color: '#0EA5E9' },
];

// spec v1.4 Part 4 (informed mode) and v1.4.1 Part 2 (learning from prices).
// Ranges: payload.hyperparam_ranges.informed / .price_learning.
export const INFORMED_PARAMS: ParamDef[] = [
  { key: 'wake_mean', symbol: 'w̄', label: 'Decision interval', description: 'Average time between decisions (random, Poisson)', format: { kind: 'seconds' }, color: '#38BDF8' },
  { key: 'T_r', symbol: 'T_r', label: 'Research interval', description: 'Average time between its own research readings of the true value', format: { kind: 'seconds' }, color: '#34D399' },
  { key: 'sigma_r', symbol: 'σ_r', label: 'Research noise', description: 'Typical error of one research reading, in cents', format: { kind: 'float', digits: 0 }, color: '#C084FC' },
  { key: 'rho', symbol: 'ρ', label: 'Price distrust', description: 'How much less it trusts the market price than normal noise implies', format: { kind: 'float', digits: 1 }, color: '#818CF8' },
  { key: 'm0', symbol: 'm₀', label: 'Required edge', description: 'Cents of mispricing it needs before it trades (its reservation price)', format: { kind: 'float', digits: 2 }, color: '#FB7185' },
  { key: 'kappa_m', symbol: 'κ_m', label: 'Edge per uncertainty', description: 'Extra edge it asks for when unsure of its belief', format: { kind: 'float', digits: 2 }, color: '#F59E0B' },
  { key: 'h0', symbol: 'h₀', label: 'Quote width', description: 'Cents beyond its edge where it keeps a small two-sided quote', format: { kind: 'float', digits: 2 }, color: '#2DD4BF' },
  { key: 'theta_q', symbol: 'θ_q', label: 'Quote size', description: 'Shares quoted per side, as a share of its wealth', format: { kind: 'percent', digits: 2 }, color: '#4ADE80' },
  { key: 'w_min', symbol: 'w_min', label: 'Short limit', description: 'Most it may sell short, as a share of wealth (fixed)', format: { kind: 'percent', digits: 0 }, color: '#F43F5E' },
  { key: 'w_max', symbol: 'w_max', label: 'Long limit', description: 'Most it may hold in stock, as a share of wealth, borrowing the rest (fixed)', format: { kind: 'percent', digits: 0 }, color: '#10B981' },
];

export const PRICE_LEARNING_PARAMS: ParamDef[] = [
  { key: 'n_pl', symbol: 'n_pl', label: 'Persistence gate', description: 'Looks in a row the price must disagree before it learns from it', format: { kind: 'int', unit: 'looks' }, color: '#94A3B8' },
  { key: 'eps_thr', symbol: 'ε_thr', label: 'Surprise threshold', description: 'How surprising the price must be (in normal-noise units) to raise its trust', format: { kind: 'float', digits: 2 }, color: '#E879F9' },
  { key: 'a_pl', symbol: 'a_pl', label: 'Surprise memory', description: 'Weight of the newest gated surprise in its running average', format: { kind: 'float', digits: 2 }, color: '#22D3EE' },
];


// spec v1.5 A9.3: the retail crowd and our market makers (LiquidityProviderAgent). Values come
// from the payload's market_params (Python param_ranges.py RETAIL / LP and this run's design).
export const RETAIL_PARAMS: ParamDef[] = [
  { key: 'n', symbol: 'N_r', label: 'Retail traders', description: 'Traders in the crowd', format: { kind: 'int' }, color: '#38BDF8' },
  { key: 'mu_per_agent', symbol: 'μ', label: 'Actions per trader', description: 'Average orders per trader per calm day', format: { kind: 'float', digits: 1 }, color: '#34D399' },
  { key: 'kappa_v', symbol: 'κ_v', label: 'Excitement by volatility', description: 'How much busier the crowd gets when prices move fast', format: { kind: 'float', digits: 1 }, color: '#F472B6' },
  { key: 'kappa_n', symbol: 'κ_n', label: 'Excitement by news', description: 'How much busier the crowd gets after a headline', format: { kind: 'float', digits: 1 }, color: '#FBBF24' },
  { key: 'cap', symbol: 'cap', label: 'Activity cap', description: 'Largest multiple of the calm activity', format: { kind: 'float', digits: 0 }, color: '#94A3B8' },
  { key: 'p_liquidity', symbol: 'p_liq', label: 'Liquidity traders', description: 'Share who buy or sell for their own reasons (50/50)', format: { kind: 'percent', digits: 0 }, color: '#60A5FA' },
  { key: 'p_trend', symbol: 'p_trend', label: 'Trend followers', description: 'Share who buy after rises and sell after falls', format: { kind: 'percent', digits: 0 }, color: '#4ADE80' },
  { key: 'p_contrarian', symbol: 'p_con', label: 'Contrarians', description: 'Share who buy after falls and sell after rises', format: { kind: 'percent', digits: 0 }, color: '#FB7185' },
  { key: 'p_stop', symbol: 'p_stop', label: 'Stop-loss users', description: 'Share who place a stop below each purchase', format: { kind: 'percent', digits: 0 }, color: '#C084FC' },
  { key: 'size_median', symbol: 'q̃', label: 'Typical order', description: 'Median order size (log-normal)', format: { kind: 'int', unit: 'sh' }, color: '#2DD4BF' },
  { key: 'wealth', symbol: 'W_r', label: 'Wealth per trader', description: 'Dollars per trader, half in shares at the open', format: { kind: 'int', unit: '$' }, color: '#FDE047' },
];

export const LP_PARAMS: ParamDef[] = [
  { key: 'n', symbol: 'n_lp', label: 'Market makers', description: 'Our liquidity providers quoting both sides', format: { kind: 'int' }, color: '#38BDF8' },
  { key: 'wealth', symbol: 'W', label: 'Capital each', description: 'Dollars per market maker', format: { kind: 'int', unit: '$' }, color: '#FDE047' },
  { key: 'dt_s', symbol: 'Δt', label: 'Requote check', description: 'How often it looks at its quotes', format: { kind: 'seconds' }, color: '#34D399' },
  { key: 'c_h', symbol: 'c_h', label: 'Half-spread factor', description: 'Half-spread as a share of the typical 10-second move', format: { kind: 'float', digits: 2 }, color: '#F472B6' },
  { key: 'levels', symbol: 'L', label: 'Ladder levels', description: 'Price levels quoted on each side', format: { kind: 'int' }, color: '#60A5FA' },
  { key: 'theta_lp', symbol: 'θ', label: 'Quoted size', description: 'Shares quoted per side as a share of wealth', format: { kind: 'percent', digits: 1 }, color: '#2DD4BF' },
  { key: 'l_max', symbol: 'l_max', label: 'Inventory limit', description: 'Largest position as a share of wealth', format: { kind: 'percent', digits: 0 }, color: '#FB923C' },
  { key: 'psi', symbol: 'ψ', label: 'Inventory skew', description: 'How far quotes lean away from a growing position', format: { kind: 'float', digits: 2 }, color: '#A78BFA' },
];
