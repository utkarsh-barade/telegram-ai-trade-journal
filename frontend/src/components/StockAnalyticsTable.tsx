import React from 'react';
import { StockAnalyticsItem } from '../types';
import { Layers } from 'lucide-react';

interface Props {
  items: StockAnalyticsItem[];
}

export const StockAnalyticsTable: React.FC<Props> = ({ items }) => {
  return (
    <div className="glass-panel rounded-2xl overflow-hidden shadow-xl border border-slate-800 mb-8">
      <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-indigo-400" />
          <h3 className="font-bold text-slate-100 text-sm tracking-wide">Stock / Instrument Performance Detail</h3>
        </div>
        <span className="text-xs text-slate-400 font-mono">{items.length} Instruments</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <th className="py-3.5 px-4">Stock Symbol</th>
              <th className="py-3.5 px-4">Trades</th>
              <th className="py-3.5 px-4">Wins / Losses</th>
              <th className="py-3.5 px-4">Win Rate</th>
              <th className="py-3.5 px-4">Profit Factor</th>
              <th className="py-3.5 px-4">Avg R:R</th>
              <th className="py-3.5 px-4 text-right">Net Position P&L ₹</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {items.map((item) => (
              <tr key={item.stock} className="hover:bg-slate-900/40 transition-colors">
                <td className="py-3 px-4 font-semibold text-slate-100 font-mono">
                  {item.stock}
                </td>
                <td className="py-3 px-4 font-mono text-slate-300">
                  {item.trades_count}
                </td>
                <td className="py-3 px-4 font-mono text-slate-400">
                  <span className="text-emerald-400 font-semibold">{item.wins}W</span> /{' '}
                  <span className="text-rose-400 font-semibold">{item.losses}L</span>
                </td>
                <td className="py-3 px-4 font-mono font-bold text-slate-200">
                  {item.win_rate}%
                </td>
                <td className="py-3 px-4 font-mono text-slate-200">
                  {item.profit_factor}
                </td>
                <td className="py-3 px-4 font-mono text-slate-300">
                  {item.avg_rr}
                </td>
                <td className="py-3 px-4 text-right font-mono font-bold">
                  <span className={item.net_pnl_inr >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {item.net_pnl_inr >= 0 ? '+' : ''}₹{item.net_pnl_inr.toLocaleString()}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
