import React, { useState } from 'react';
import { AnalystLeaderboardItem } from '../types';
import { Award, AlertCircle, TrendingUp, TrendingDown, ShieldAlert, Zap } from 'lucide-react';

interface Props {
  leaderboard: AnalystLeaderboardItem[];
  disclaimer: string;
}

export const AnalystLeaderboard: React.FC<Props> = ({ leaderboard, disclaimer }) => {
  const [sortBy, setSortBy] = useState<keyof AnalystLeaderboardItem>('net_pnl_inr');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: keyof AnalystLeaderboardItem) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
  };

  const sortedLeaderboard = [...leaderboard].sort((a, b) => {
    const valA = (a[sortBy] as number) || 0;
    const valB = (b[sortBy] as number) || 0;
    return sortDir === 'asc' ? valA - valB : valB - valA;
  });

  return (
    <div className="space-y-6 mb-8">
      {/* Mandatory Analytical Framing Disclaimer */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 flex items-start gap-3 text-amber-300 text-xs">
        <AlertCircle className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
        <div>
          <span className="font-bold uppercase tracking-wider text-[11px] block text-amber-400 mb-0.5">
            Analytical Indicator Framing Disclaimer
          </span>
          <p className="opacity-90">{disclaimer}</p>
        </div>
      </div>

      {/* Return Type Clarification Legend */}
      <div className="glass-panel rounded-2xl p-4 border border-slate-800 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400"></div>
          <div>
            <span className="font-semibold text-slate-100">Option Premium Return (%)</span>
            <p className="text-[10px] text-slate-400">Direct price move % on the instrument/option premium</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400"></div>
          <div>
            <span className="font-semibold text-slate-100">Position P&L (₹)</span>
            <p className="text-[10px] text-slate-400">Realized weighted rupee gain/loss on position</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-2.5 h-2.5 rounded-full bg-indigo-400"></div>
          <div>
            <span className="font-semibold text-slate-100">Capital Return (%)</span>
            <p className="text-[10px] text-slate-400">Total Net P&L as % of configured trading capital</p>
          </div>
        </div>
      </div>

      {/* Leaderboard Table */}
      <div className="glass-panel rounded-2xl overflow-hidden shadow-xl border border-slate-800">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Award className="w-5 h-5 text-indigo-400" />
            <h3 className="font-bold text-slate-100 text-sm tracking-wide">Analyst Evaluation Leaderboard</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">{leaderboard.length} Analysts evaluated</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('analyst_name')}>Analyst</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('trades_count')}>Trades</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('win_rate')}>Win Rate</th>
                <th className="py-3.5 px-4">Avg Win / Loss</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('profit_factor')}>Profit Factor</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('expectancy_val')}>Expectancy</th>
                <th className="py-3.5 px-4">R:R (Achieved vs Plan)</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('net_pnl_inr')}>Position P&L ₹</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('capital_return_pct')}>Capital Return %</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('max_drawdown_pct')}>Max Drawdown</th>
                <th className="py-3.5 px-4 text-center">Streaks (Win / Loss / Active)</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800/60">
              {sortedLeaderboard.map((item, idx) => {
                const expectancyBadge =
                  item.expectancy_label === 'Positive'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    : item.expectancy_label === 'Negative'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                    : 'bg-amber-500/20 text-amber-300 border-amber-500/30';

                return (
                  <tr key={item.analyst_id} className="hover:bg-slate-900/40 transition-colors">
                    {/* Analyst Name */}
                    <td className="py-3.5 px-4 font-semibold text-slate-100 flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-[10px] font-mono text-indigo-400">
                        {idx + 1}
                      </span>
                      {item.analyst_name}
                    </td>

                    {/* Trades Count */}
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      {item.trades_count}
                      <div className="text-[10px] text-slate-500">
                        {item.wins}W / {item.losses}L / {item.open_count + item.partial_count}O
                      </div>
                    </td>

                    {/* Win Rate */}
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-200">
                      {item.win_rate}%
                    </td>

                    {/* Avg Win / Loss (₹ and Premium %) */}
                    <td className="py-3.5 px-4 font-mono text-[11px]">
                      <div className="text-emerald-400">
                        +₹{item.avg_win_inr.toLocaleString()} <span className="text-[10px] opacity-75">(+{item.avg_win_pct}%)</span>
                      </div>
                      <div className="text-rose-400">
                        -₹{item.avg_loss_inr.toLocaleString()} <span className="text-[10px] opacity-75">(-{item.avg_loss_pct}%)</span>
                      </div>
                    </td>

                    {/* Profit Factor */}
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-200">
                      {item.profit_factor}
                    </td>

                    {/* Expectancy */}
                    <td className="py-3.5 px-4">
                      <span className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border ${expectancyBadge}`}>
                        {item.expectancy_label}
                        <span className="ml-1 opacity-75 font-mono">(₹{item.expectancy_val})</span>
                      </span>
                    </td>

                    {/* R:R Comparison */}
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      <span>{item.avg_achieved_rr}</span>
                      <span className="text-[10px] text-slate-500 ml-1">(Plan: {item.avg_planned_rr})</span>
                      <div className={`text-[10px] font-semibold ${item.rr_delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        Δ {item.rr_delta >= 0 ? '+' : ''}{item.rr_delta}
                      </div>
                    </td>

                    {/* Position P&L ₹ */}
                    <td className="py-3.5 px-4 font-mono font-bold text-sm">
                      <span className={item.net_pnl_inr >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {item.net_pnl_inr >= 0 ? '+' : ''}₹{item.net_pnl_inr.toLocaleString()}
                      </span>
                    </td>

                    {/* Capital Return % */}
                    <td className="py-3.5 px-4 font-mono font-bold">
                      <span className={item.capital_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {item.capital_return_pct >= 0 ? '+' : ''}{item.capital_return_pct}%
                      </span>
                    </td>

                    {/* Max Drawdown */}
                    <td className="py-3.5 px-4 font-mono text-rose-400">
                      -{item.max_drawdown_pct}%
                      <div className="text-[10px] text-slate-500">-₹{item.max_drawdown_inr.toLocaleString()}</div>
                    </td>

                    {/* Streaks */}
                    <td className="py-3.5 px-4 text-center font-mono text-[11px]">
                      <div className="flex items-center justify-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" title="Longest Win Streak">
                          🔥 {item.longest_win_streak}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20" title="Longest Loss Streak">
                          ❄️ {item.longest_loss_streak}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 mt-1">
                        Active: <span className={item.current_streak > 0 ? 'text-emerald-400 font-bold' : item.current_streak < 0 ? 'text-rose-400 font-bold' : 'text-slate-400'}>
                          {item.current_streak > 0 ? `+${item.current_streak} Win` : item.current_streak < 0 ? `${item.current_streak} Loss` : 'None'}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
