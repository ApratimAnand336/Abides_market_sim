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
  { key: 'beta', symbol: 'β', label: 'Aggression multiplier', description: 'How much the order size grows with the mispricing', format: { kind: 'float', digits: 2 }, color: '#F59E0B' },
  { key: 'er_window', symbol: 'n_ER', label: 'Efficiency-ratio memory', description: 'Observations used to judge trend vs noise', format: { kind: 'int', unit: 'obs' }, color: '#38BDF8' },
  { key: 'delta', symbol: 'δ', label: 'Noise sensitivity', description: 'Base observation noise as a fraction of price', format: { kind: 'float', digits: 4 }, color: '#34D399' },
  { key: 'lambda_er', symbol: 'λ_ER', label: 'Distrust of choppy prices', description: 'Penalty on observations when the market is choppy', format: { kind: 'float', digits: 2 }, color: '#818CF8' },
  { key: 'sigma_n', symbol: 'σ_n', label: 'Private signal noise', description: 'Noise on the agent’s private look at the fundamental', format: { kind: 'float', digits: 0 }, color: '#C084FC' },
  { key: 'gamma', symbol: 'γ', label: 'Caution memory', description: 'How long past right/wrong calls affect confidence', format: { kind: 'float', digits: 3 }, color: '#FB7185' },
  { key: 'k', symbol: 'k', label: 'Caution sensitivity', description: 'How quickly confidence reacts to results', format: { kind: 'float', digits: 3 }, color: '#2DD4BF' },
  { key: 'mu', symbol: 'μ', label: 'Limit safety margin', description: 'How far from its estimate it will pay or sell', format: { kind: 'percent', digits: 2 }, color: '#FDE047' },
  { key: 'news_sensitivity', symbol: 'η', label: 'News reaction', description: 'Largest shift of the estimate per headline', format: { kind: 'percent', digits: 2 }, color: '#22D3EE' },
];

export const MOMENTUM_PARAMS: ParamDef[] = [
  { key: 'tau', symbol: 'τ', label: 'Trend memory', description: 'How long the agent believes a trend lasts', format: { kind: 'seconds' }, color: '#F59E0B' },
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
