import React from 'react';
import { Eye, Edit3, Trash2, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react';
import { Trade } from '../types';

interface TradeTableProps {
  trades: Trade[];
  totalCount: number;
  page: number;
  limit: number;
  sortBy: string;
  sortDir: string;
  onPageChange: (newPage: number) => void;
  onSortChange: (field: string) => void;
  onView: (trade: Trade) => void;
  onEdit: (trade: Trade) => void;
  onDelete: (id: number) => void;
}

export const TradeTable: React.FC<TradeTableProps> = ({
  trades,
  totalCount,
  page,
  limit,
  sortBy,
  sortDir,
  onPageChange,
  onSortChange,
  onView,
  onEdit,
  onDelete,
}) => {
  const totalPages = Math.ceil(totalCount / limit) || 1;

  const renderOutcomeBadge = (t: Trade) => {
    const outcome = t.outcome;
    let cls = 'badge-open';
    if (outcome === 'WIN') cls = 'badge-win';
    else if (outcome === 'LOSS') cls = 'badge-loss';
    else if (outcome === 'PARTIAL_EXIT') cls = 'badge-partial';
    else if (outcome === 'BREAKEVEN') cls = 'badge-breakeven';
    else if (outcome === 'NEEDS_REVIEW') cls = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';

    const mStatus = t.monitoring_status || 'MONITORED';

    return (
      <div className="flex flex-col gap-1 items-start">
        <span className={`px-2.5 py-0.5 rounded-lg text-[10px] font-bold tracking-wide uppercase ${cls}`}>
          {outcome}
        </span>
        {mStatus === 'NEEDS_REVIEW' && (
          <span className="text-[9px] font-semibold text-amber-400 flex items-center gap-1">
            ⚠️ Needs Review
          </span>
        )}
        {mStatus === 'DATA_UNAVAILABLE' && (
          <span className="text-[9px] font-semibold text-rose-400 flex items-center gap-1">
            📡 Data Stale
          </span>
        )}
        {mStatus === 'MONITORED' && (outcome === 'OPEN' || outcome === 'PARTIAL_EXIT') && (
          <span className="text-[9px] font-medium text-emerald-400/80 flex items-center gap-1">
            ● Live Monitored
          </span>
        )}
      </div>
    );
  };

  const renderTargetsColumn = (t: Trade) => {
    if (!t.targets || t.targets.length === 0) {
      return <span className="text-slate-400">{t.target ? `₹${t.target}` : '—'}</span>;
    }

    const bookedPct = Math.round(100 - t.remaining_qty_pct);

    return (
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-1 text-[11px]">
          {t.targets.map((leg, idx) => (
            <span
              key={idx}
              className={`px-1.5 py-0.5 rounded font-mono ${
                leg.status === 'HIT'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
              title={`${leg.level}: ₹${leg.target_price} (${leg.planned_qty_pct}% qty)`}
            >
              {leg.target_price}
              <span className="text-[9px] opacity-75 ml-0.5">
                ({leg.status === 'HIT' ? '✓' : ''}{leg.planned_qty_pct}%)
              </span>
            </span>
          ))}
        </div>

        {bookedPct > 0 && bookedPct < 100 && (
          <div className="flex items-center gap-2 mt-0.5">
            <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-amber-400 h-1.5 rounded-full"
                style={{ width: `${bookedPct}%` }}
              ></div>
            </div>
            <span className="text-[9px] font-mono text-amber-400 font-semibold">
              {bookedPct}% booked
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="glass-panel rounded-2xl shadow-xl overflow-hidden mb-8">
      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => onSortChange('trade_date')}>
                <div className="flex items-center gap-1">
                  Date / ID
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => onSortChange('stock')}>
                Stock / Instrument
              </th>
              <th className="py-3.5 px-4">Direction</th>
              <th className="py-3.5 px-4">Entry</th>
              <th className="py-3.5 px-4">SL</th>
              <th className="py-3.5 px-4">Targets</th>
              <th className="py-3.5 px-4">Exit (Weighted)</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-4 cursor-pointer hover:text-slate-200" onClick={() => onSortChange('pnl_inr')}>
                P&L ₹ (%)
              </th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-800/60 text-xs">
            {trades.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-8 text-center text-slate-500">
                  No trades match the current filter criteria.
                </td>
              </tr>
            ) : (
              trades.map((t) => {
                const dateStr = t.trade_date
                  ? new Date(t.trade_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
                  : '—';

                const pnlClass = (t.pnl_inr || 0) > 0 ? 'text-emerald-400' : (t.pnl_inr || 0) < 0 ? 'text-rose-400' : 'text-slate-400';

                return (
                  <tr key={t.id} className="hover:bg-slate-900/40 transition-colors">
                    {/* Date / ID */}
                    <td className="py-3 px-4 font-mono">
                      <div className="font-semibold text-slate-200">{t.display_id}</div>
                      <div className="text-[10px] text-slate-500">{dateStr}</div>
                    </td>

                    {/* Stock / Instrument */}
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-100">{t.instrument}</div>
                      <div className="text-[10px] text-slate-400">
                        {t.expiry ? `Exp: ${t.expiry}` : ''}
                      </div>
                    </td>

                    {/* Direction */}
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold ${
                        t.direction === 'BUY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}>
                        {t.direction}
                      </span>
                    </td>

                    {/* Entry */}
                    <td className="py-3 px-4 font-mono font-medium text-slate-200">
                      ₹{t.entry_price}
                    </td>

                    {/* SL */}
                    <td className="py-3 px-4 font-mono text-slate-400">
                      {t.stop_loss ? `₹${t.stop_loss}` : '—'}
                    </td>

                    {/* Targets */}
                    <td className="py-3 px-4">
                      {renderTargetsColumn(t)}
                    </td>

                    {/* Exit (Weighted) */}
                    <td className="py-3 px-4 font-mono font-medium text-slate-200">
                      {t.weighted_exit_price ? `₹${t.weighted_exit_price}` : (t.exit_price ? `₹${t.exit_price}` : '—')}
                    </td>

                    {/* Outcome & Monitoring Status */}
                    <td className="py-3 px-4">
                      {renderOutcomeBadge(t)}
                    </td>

                    {/* P&L ₹ (%) */}
                    <td className="py-3 px-4 font-mono font-semibold">
                      {t.pnl_inr !== undefined && t.pnl_inr !== null ? (
                        <div className={pnlClass}>
                          {t.pnl_inr >= 0 ? '+' : ''}₹{t.pnl_inr.toLocaleString()}
                          <div className="text-[10px] opacity-75">
                            ({t.pnl_pct !== undefined && t.pnl_pct !== null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : ''})
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => onView(t)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                          title="View Trade Detail & Audit Trail"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => onEdit(t)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                          title="Edit Trade / Legs"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => onDelete(t.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                          title="Delete Trade"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/40 flex items-center justify-between">
        <div className="text-xs text-slate-400">
          Showing <span className="font-mono font-semibold text-slate-200">{trades.length}</span> of{' '}
          <span className="font-mono font-semibold text-slate-200">{totalCount}</span> trades
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="p-2 rounded-lg glass-panel hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent text-slate-300"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs font-mono text-slate-400">
            Page <span className="text-slate-200 font-bold">{page}</span> of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="p-2 rounded-lg glass-panel hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent text-slate-300"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
