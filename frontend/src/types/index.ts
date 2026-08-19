export interface TargetLeg {
  id?: number;
  level: string;
  target_price: number;
  planned_qty_pct: number;
  status: 'PENDING' | 'HIT' | 'SKIPPED';
  exit_price?: number | null;
  exit_datetime?: string | null;
}

export interface OutcomeHistory {
  id: number;
  from_outcome?: str | null;
  to_outcome: string;
  note?: string | null;
  changed_by?: number | null;
  created_at: string;
}

export interface Trade {
  id: number;
  display_id: string;
  trade_date?: string | null;
  entry_time?: string | null;
  stock: string;
  instrument: string;
  strike?: number | null;
  option_type?: 'CE' | 'PE' | null;
  expiry?: string | null;
  direction: 'BUY' | 'SELL';
  entry_price: number;
  stop_loss?: number | null;
  target?: number | null;
  exit_price?: number | null;
  weighted_exit_price?: number | null;
  remaining_qty_pct: number;
  exit_datetime?: string | null;
  outcome: 'NEW' | 'VALIDATING' | 'OPEN' | 'PARTIAL_EXIT' | 'WIN' | 'LOSS' | 'CLOSED' | 'BREAKEVEN' | 'EXPIRED' | 'NEEDS_REVIEW';
  monitoring_status?: 'MONITORED' | 'NEEDS_REVIEW' | 'DATA_UNAVAILABLE' | 'PAUSED';
  pnl_inr?: number | null;
  pnl_pct?: number | null;
  capital?: number | null;
  capital_pnl_pct?: number | null;
  risk_inr?: number | null;
  risk_pct?: number | null;
  planned_rr?: number | null;
  achieved_rr?: number | null;
  analyst_id: number;
  analyst_username?: string | null;
  notes?: string | null;
  raw_message: string;
  date_is_explicit: boolean;
  created_at: string;
  updated_at: string;
  targets?: TargetLeg[];
  outcome_history?: OutcomeHistory[];
}

export interface TargetHitRates {
  tg1_rate: number;
  tg2_rate: number;
  final_rate: number;
  total_trades_with_targets: number;
}

export interface AnalystLeaderboardItem {
  analyst_id: number;
  analyst_name: string;
  trades_count: number;
  wins: number;
  losses: number;
  breakevens: number;
  open_count: number;
  partial_count: number;
  win_rate: number;
  avg_win_inr: number;
  avg_win_pct: number;
  avg_loss_inr: number;
  avg_loss_pct: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  expectancy_val: number;
  expectancy_label: 'Positive' | 'Negative' | 'Neutral';
  avg_planned_rr: number;
  avg_achieved_rr: number;
  rr_delta: number;
  net_pnl_inr: number;
  capital_return_pct: number;
  max_drawdown_inr: number;
  max_drawdown_pct: number;
  longest_win_streak: number;
  longest_loss_streak: number;
  current_streak: number;
  target_hit_rates: TargetHitRates;
  disclaimer: string;
}

export interface StockAnalyticsItem {
  stock: string;
  trades_count: number;
  wins: number;
  losses: number;
  win_rate: number;
  net_pnl_inr: number;
  profit_factor: number;
  avg_rr: number;
}

export interface TrendPoint {
  period: string;
  trades_count: number;
  win_rate: number;
  net_pnl: number;
  expectancy: number;
  profit_factor: number;
}

export interface OverviewMetrics {
  total_trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  breakevens: number;
  win_rate: number;
  net_pnl: number;
  capital_return: number;
  avg_pnl: number;
  avg_rr: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  expectancy: number;
  profit_factor: number;
  best_trade: number;
  worst_trade: number;
}

export interface TradeFilterState {
  preset: string;
  start_date: string;
  end_date: string;
  stock: string;
  option_type: string;
  strike: string;
  analyst_id: string;
  outcome: string;
  pnl_filter: string;
  search: string;
}

export interface FilterOptions {
  stocks: string[];
  strikes: number[];
  analysts: { id: number; name: string }[];
  outcomes: string[];
}

export interface ChartDataResponse {
  daily_pnl: { date: string; pnl: number; trades: number; wins: number; losses: number }[];
  cumulative_pnl: { trade_id: string; date: string; cum_pnl: number }[];
  win_loss_distribution: { name: string; value: number; color: string }[];
  drawdown_series: { trade_id: string; date: string; drawdown: number }[];
  stock_performance: { stock: string; trades: number; win_rate: number; net_pnl: number }[];
  analyst_performance: { analyst: string; trades: number; win_rate: number; net_pnl: number }[];
  planned_vs_achieved_rr: { trade_id: string; stock: string; planned_rr: number; achieved_rr: number }[];
}

export interface UserProfile {
  username: string;
  role: string;
  display_name: string;
}
