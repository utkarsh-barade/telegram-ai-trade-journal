import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  BarChart2,
  PieChart,
  ShieldAlert,
  Percent,
  Award,
  Activity,
} from 'lucide-react';
import { OverviewMetrics } from '../types';

interface OverviewCardsProps {
  metrics: OverviewMetrics | null;
}

export const OverviewCards: React.FC<OverviewCardsProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="glass-panel h-24 rounded-2xl animate-pulse"></div>
        ))}
      </div>
    );
  }

  const isNetPositive = metrics.net_pnl >= 0;

  const cards = [
    {
      title: 'Total Trades',
      value: metrics.total_trades.toString(),
      sub: `${metrics.open_trades} currently open`,
      icon: BarChart2,
      color: 'text-indigo-400',
    },
    {
      title: 'Win Rate',
      value: `${metrics.win_rate}%`,
      sub: `${metrics.wins}W · ${metrics.losses}L · ${metrics.breakevens}BE`,
      icon: Percent,
      color: metrics.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400',
    },
    {
      title: 'Net P&L',
      value: `${isNetPositive ? '+' : ''}₹${metrics.net_pnl.toLocaleString()}`,
      sub: `Capital Ret: ${metrics.capital_return >= 0 ? '+' : ''}${metrics.capital_return}%`,
      icon: isNetPositive ? TrendingUp : TrendingDown,
      color: isNetPositive ? 'text-emerald-400' : 'text-rose-400',
    },
    {
      title: 'Average P&L',
      value: `${metrics.avg_pnl >= 0 ? '+' : ''}₹${metrics.avg_pnl.toLocaleString()}`,
      sub: 'Per exited trade',
      icon: DollarSign,
      color: metrics.avg_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400',
    },
    {
      title: 'Average R:R',
      value: `${metrics.avg_rr}R`,
      sub: 'Achieved Reward:Risk',
      icon: Target,
      color: 'text-sky-400',
    },
    {
      title: 'Profit Factor',
      value: metrics.profit_factor.toString(),
      sub: metrics.profit_factor >= 1.5 ? 'Strong Ratio' : 'Normal',
      icon: PieChart,
      color: metrics.profit_factor >= 1.0 ? 'text-emerald-400' : 'text-rose-400',
    },
    {
      title: 'Expectancy',
      value: `${metrics.expectancy >= 0 ? '+' : ''}₹${metrics.expectancy.toLocaleString()}`,
      sub: 'Expected value per trade',
      icon: Activity,
      color: metrics.expectancy >= 0 ? 'text-emerald-400' : 'text-rose-400',
    },
    {
      title: 'Max Drawdown',
      value: `-₹${metrics.max_drawdown.toLocaleString()}`,
      sub: `Peak Decline: -${metrics.max_drawdown_pct}%`,
      icon: ShieldAlert,
      color: 'text-amber-400',
    },
    {
      title: 'Best Trade',
      value: `+₹${metrics.best_trade.toLocaleString()}`,
      sub: 'Single highest profit',
      icon: Award,
      color: 'text-emerald-400',
    },
    {
      title: 'Worst Trade',
      value: `₹${metrics.worst_trade.toLocaleString()}`,
      sub: 'Single largest loss',
      icon: TrendingDown,
      color: 'text-rose-400',
    },
    {
      title: 'Wins / Losses',
      value: `${metrics.wins} / ${metrics.losses}`,
      sub: `${metrics.breakevens} Breakeven trades`,
      icon: BarChart2,
      color: 'text-slate-300',
    },
    {
      title: 'Open Positions',
      value: metrics.open_trades.toString(),
      sub: 'Active in market',
      icon: Target,
      color: 'text-indigo-400',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5 mb-8">
      {cards.map((card, i) => {
        const Icon = card.icon;
        return (
          <div
            key={i}
            className="glass-panel rounded-2xl p-4 flex flex-col justify-between hover:border-slate-700 transition-all"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                {card.title}
              </span>
              <Icon className={`w-4 h-4 ${card.color}`} />
            </div>

            <div>
              <div className={`text-lg font-bold font-mono tracking-tight ${card.color}`}>
                {card.value}
              </div>
              <div className="text-[10px] text-slate-500 truncate mt-0.5">
                {card.sub}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
