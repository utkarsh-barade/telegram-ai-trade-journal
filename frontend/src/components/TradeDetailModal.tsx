import React from 'react';
import { X, Clock, FileText, CheckCircle2, AlertCircle, Layers } from 'lucide-react';
import { Trade } from '../types';

interface TradeDetailModalProps {
  trade: Trade | null;
  isOpen: boolean;
  onClose: () => void;
}

export const TradeDetailModal: React.FC<TradeDetailModalProps> = ({
  trade,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !trade) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay">
      <div className="glass-panel w-full max-w-3xl rounded-2xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto border border-slate-700 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-100 font-mono">{trade.display_id}</h2>
              <span className="text-sm font-bold text-indigo-400">{trade.instrument}</span>
              <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                trade.direction === 'BUY' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
              }`}>
                {trade.direction}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Date: {trade.trade_date ? new Date(trade.trade_date).toLocaleString() : '—'}
            </p>
          </div>

          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Pricing & Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="glass-card p-3 rounded-xl">
            <span className="text-slate-400 block mb-1">Entry Price</span>
            <span className="font-mono text-base font-bold text-slate-100">₹{trade.entry_price}</span>
          </div>

          <div className="glass-card p-3 rounded-xl">
            <span className="text-slate-400 block mb-1">Stop Loss</span>
            <span className="font-mono text-base font-bold text-slate-300">
              {trade.stop_loss ? `₹${trade.stop_loss}` : '—'}
            </span>
          </div>

          <div className="glass-card p-3 rounded-xl">
            <span className="text-slate-400 block mb-1">Weighted Exit</span>
            <span className="font-mono text-base font-bold text-slate-100">
              {trade.weighted_exit_price ? `₹${trade.weighted_exit_price}` : (trade.exit_price ? `₹${trade.exit_price}` : '—')}
            </span>
          </div>

          <div className="glass-card p-3 rounded-xl">
            <span className="text-slate-400 block mb-1">Net P&L</span>
            <span className={`font-mono text-base font-bold ${
              (trade.pnl_inr || 0) > 0 ? 'text-emerald-400' : (trade.pnl_inr || 0) < 0 ? 'text-rose-400' : 'text-slate-300'
            }`}>
              {trade.pnl_inr !== undefined && trade.pnl_inr !== null
                ? `${trade.pnl_inr >= 0 ? '+' : ''}₹${trade.pnl_inr.toLocaleString()}`
                : '—'}
            </span>
          </div>
        </div>

        {/* Target Legs Table */}
        <div>
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-400" />
            Staggered Target Legs Breakdown
          </h3>

          <div className="glass-card rounded-xl overflow-hidden border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-900/60 text-slate-400 border-b border-slate-800">
                  <th className="py-2.5 px-3">Level</th>
                  <th className="py-2.5 px-3">Target Price</th>
                  <th className="py-2.5 px-3">Qty %</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Exit Price</th>
                  <th className="py-2.5 px-3">Exit DateTime</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {trade.targets && trade.targets.length > 0 ? (
                  trade.targets.map((leg, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/40">
                      <td className="py-2 px-3 font-bold text-slate-200">{leg.level}</td>
                      <td className="py-2 px-3 font-mono">₹{leg.target_price}</td>
                      <td className="py-2 px-3 font-mono">{leg.planned_qty_pct}%</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          leg.status === 'HIT'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : leg.status === 'SKIPPED'
                            ? 'bg-slate-800 text-slate-500'
                            : 'bg-indigo-500/20 text-indigo-300'
                        }`}>
                          {leg.status}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono text-slate-300">
                        {leg.exit_price ? `₹${leg.exit_price}` : '—'}
                      </td>
                      <td className="py-2 px-3 text-slate-400">
                        {leg.exit_datetime ? new Date(leg.exit_datetime).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-slate-500">
                      No target legs defined.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Audit Trail History */}
        <div>
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" />
            Outcome History Audit Trail
          </h3>

          <div className="glass-card rounded-xl p-4 border border-slate-800 space-y-3">
            {trade.outcome_history && trade.outcome_history.length > 0 ? (
              trade.outcome_history.map((item, idx) => (
                <div key={idx} className="flex items-start gap-3 text-xs border-b border-slate-800/60 pb-2.5 last:border-0 last:pb-0">
                  <div className="w-2 h-2 rounded-full bg-indigo-500 mt-1.5 flex-shrink-0"></div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">
                        {item.from_outcome ? `${item.from_outcome} → ` : ''}
                        <span className="text-indigo-400">{item.to_outcome}</span>
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </div>
                    {item.note && <p className="text-slate-400 text-[11px] mt-0.5">{item.note}</p>}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-slate-500 text-xs text-center py-2">No state transitions recorded yet.</p>
            )}
          </div>
        </div>

        {/* Raw Telegram Message */}
        <div>
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
            <FileText className="w-4 h-4 text-indigo-400" />
            Original Telegram Message
          </h3>
          <div className="p-3 rounded-xl bg-slate-900/90 font-mono text-xs text-slate-300 border border-slate-800 whitespace-pre-wrap">
            {trade.raw_message}
          </div>
        </div>
      </div>
    </div>
  );
};
