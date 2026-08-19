import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, AlertCircle } from 'lucide-react';
import { TargetLeg, Trade } from '../types';

interface AddEditTradeModalProps {
  trade?: Trade | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<Trade>) => Promise<void>;
}

export const AddEditTradeModal: React.FC<AddEditTradeModalProps> = ({
  trade,
  isOpen,
  onClose,
  onSave,
}) => {
  const isEdit = !!trade;

  const [tradeDate, setTradeDate] = useState('');
  const [stock, setStock] = useState('');
  const [strike, setStrike] = useState<string>('');
  const [optionType, setOptionType] = useState<string>('');
  const [expiry, setExpiry] = useState('');
  const [direction, setDirection] = useState<'BUY' | 'SELL'>('BUY');
  const [entryPrice, setEntryPrice] = useState<string>('');
  const [stopLoss, setStopLoss] = useState<string>('');
  const [capital, setCapital] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [outcome, setOutcome] = useState<string>('OPEN');
  const [targets, setTargets] = useState<TargetLeg[]>([
    { level: 'FINAL', target_price: 0, planned_qty_pct: 100, status: 'PENDING' },
  ]);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (trade) {
      setTradeDate(trade.trade_date ? trade.trade_date.slice(0, 10) : '');
      setStock(trade.stock || '');
      setStrike(trade.strike !== null && trade.strike !== undefined ? String(trade.strike) : '');
      setOptionType(trade.option_type || '');
      setExpiry(trade.expiry || '');
      setDirection(trade.direction || 'BUY');
      setEntryPrice(trade.entry_price ? String(trade.entry_price) : '');
      setStopLoss(trade.stop_loss !== null && trade.stop_loss !== undefined ? String(trade.stop_loss) : '');
      setCapital(trade.capital ? String(trade.capital) : '');
      setNotes(trade.notes || '');
      setOutcome(trade.outcome || 'OPEN');
      if (trade.targets && trade.targets.length > 0) {
        setTargets(trade.targets.map(t => ({ ...t })));
      } else if (trade.target) {
        setTargets([{ level: 'FINAL', target_price: trade.target, planned_qty_pct: 100, status: 'PENDING' }]);
      }
    } else {
      setTradeDate(new Date().toISOString().slice(0, 10));
      setStock('');
      setStrike('');
      setOptionType('');
      setExpiry('');
      setDirection('BUY');
      setEntryPrice('');
      setStopLoss('');
      setCapital('');
      setNotes('');
      setOutcome('OPEN');
      setTargets([{ level: 'FINAL', target_price: 0, planned_qty_pct: 100, status: 'PENDING' }]);
    }
  }, [trade, isOpen]);

  if (!isOpen) return null;

  // Calculate sum of planned_qty_pct across targets
  const totalQtyPct = targets.reduce((sum, t) => sum + (Number(t.planned_qty_pct) || 0), 0);
  const unallocatedPct = 100 - totalQtyPct;
  const isOver100 = totalQtyPct > 100;

  const handleAddLeg = () => {
    const nextIdx = targets.length + 1;
    // Rename previous final leg to TG_idx
    const updated = targets.map((t, idx) => {
      if (idx === targets.length - 1 && t.level === 'FINAL') {
        return { ...t, level: `TG${idx + 1}` };
      }
      return t;
    });

    const defaultShare = unallocatedPct > 0 ? unallocatedPct : 0;
    updated.push({
      level: 'FINAL',
      target_price: 0,
      planned_qty_pct: defaultShare,
      status: 'PENDING',
    });
    setTargets(updated);
  };

  const handleRemoveLeg = (index: number) => {
    if (targets.length <= 1) return;
    const updated = targets.filter((_, i) => i !== index);
    // Ensure last leg is named FINAL
    if (updated.length > 0) {
      updated[updated.length - 1].level = 'FINAL';
    }
    setTargets(updated);
  };

  const handleTargetChange = (index: number, field: keyof TargetLeg, value: any) => {
    const updated = [...targets];
    updated[index] = { ...updated[index], [field]: value };
    setTargets(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isOver100) {
      setError('Target leg allocation Qty% cannot exceed 100%');
      return;
    }

    if (!stock || !entryPrice) {
      setError('Stock and Entry Price are required.');
      return;
    }

    setSaving(true);

    try {
      const payload: Partial<Trade> = {
        trade_date: tradeDate ? new Date(tradeDate).toISOString() : undefined,
        stock: stock.toUpperCase(),
        strike: strike ? parseFloat(strike) : undefined,
        option_type: optionType ? (optionType as any) : undefined,
        expiry: expiry || undefined,
        direction,
        entry_price: parseFloat(entryPrice),
        stop_loss: stopLoss ? parseFloat(stopLoss) : undefined,
        capital: capital ? parseFloat(capital) : undefined,
        notes: notes || undefined,
        outcome: outcome as any,
        targets: targets.map(t => ({
          ...t,
          target_price: Number(t.target_price),
          planned_qty_pct: Number(t.planned_qty_pct),
        })),
      };

      await onSave(payload);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save trade');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay">
      <div className="glass-panel w-full max-w-2xl rounded-2xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto border border-slate-700">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
          <h2 className="text-base font-bold text-slate-100">
            {isEdit ? `Edit Trade ${trade?.display_id}` : 'Create Historical Trade'}
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Row 1: Date & Stock & Strike */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Trade Date</label>
              <input
                type="date"
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Stock Ticker *</label>
              <input
                type="text"
                value={stock}
                onChange={(e) => setStock(e.target.value.toUpperCase())}
                placeholder="e.g. DLF, NIFTY"
                required
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Strike Price</label>
              <input
                type="number"
                step="any"
                value={strike}
                onChange={(e) => setStrike(e.target.value)}
                placeholder="e.g. 650"
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
          </div>

          {/* Row 2: CE/PE, Expiry, Direction */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Option Type</label>
              <select
                value={optionType}
                onChange={(e) => setOptionType(e.target.value)}
                className="w-full px-3 py-2 rounded-xl glass-input"
              >
                <option value="">Equity / Stock</option>
                <option value="CE">CE (Call)</option>
                <option value="PE">PE (Put)</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Expiry</label>
              <input
                type="text"
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
                placeholder="e.g. Aug 2026"
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Direction *</label>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl glass-input font-bold"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
          </div>

          {/* Row 3: Entry, SL, Capital */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Entry Price ₹ *</label>
              <input
                type="number"
                step="any"
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
                placeholder="e.g. 24.0"
                required
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Stop Loss ₹</label>
              <input
                type="number"
                step="any"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                placeholder="e.g. 22.0"
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Account Capital ₹</label>
              <input
                type="number"
                step="any"
                value={capital}
                onChange={(e) => setCapital(e.target.value)}
                placeholder="e.g. 100000"
                className="w-full px-3 py-2 rounded-xl glass-input"
              />
            </div>
          </div>

          {/* Target Legs Section */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200">Staggered Target Legs</span>
              <div className="flex items-center gap-3">
                <span className={`font-mono text-[11px] ${isOver100 ? 'text-rose-400 font-bold' : 'text-slate-400'}`}>
                  Allocated: {totalQtyPct}% (Unallocated: {unallocatedPct}%)
                </span>
                <button
                  type="button"
                  onClick={handleAddLeg}
                  className="px-2.5 py-1 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-600 hover:text-white transition-all flex items-center gap-1 text-[11px]"
                >
                  <Plus className="w-3 h-3" /> Add Target Level
                </button>
              </div>
            </div>

            {targets.map((leg, idx) => (
              <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-slate-800/40 p-2.5 rounded-lg border border-slate-800">
                <div className="col-span-2">
                  <input
                    type="text"
                    value={leg.level}
                    onChange={(e) => handleTargetChange(idx, 'level', e.target.value)}
                    className="w-full px-2 py-1.5 rounded glass-input font-bold"
                  />
                </div>
                <div className="col-span-3">
                  <input
                    type="number"
                    step="any"
                    value={leg.target_price || ''}
                    onChange={(e) => handleTargetChange(idx, 'target_price', parseFloat(e.target.value) || 0)}
                    placeholder="Price ₹"
                    className="w-full px-2 py-1.5 rounded glass-input"
                  />
                </div>
                <div className="col-span-3">
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      step="any"
                      value={leg.planned_qty_pct || ''}
                      onChange={(e) => handleTargetChange(idx, 'planned_qty_pct', parseFloat(e.target.value) || 0)}
                      placeholder="Qty %"
                      className="w-full px-2 py-1.5 rounded glass-input"
                    />
                    <span className="text-slate-400 text-[10px]">%</span>
                  </div>
                </div>
                {isEdit && (
                  <div className="col-span-3">
                    <select
                      value={leg.status}
                      onChange={(e) => handleTargetChange(idx, 'status', e.target.value)}
                      className="w-full px-2 py-1 rounded glass-input text-[11px]"
                    >
                      <option value="PENDING">PENDING</option>
                      <option value="HIT">HIT</option>
                      <option value="SKIPPED">SKIPPED</option>
                    </select>
                  </div>
                )}
                <div className="col-span-1 text-right">
                  {targets.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveLeg(idx)}
                      className="p-1 rounded text-slate-500 hover:text-rose-400"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Outcome selection on Edit */}
          {isEdit && (
            <div>
              <label className="block text-slate-400 font-medium mb-1">Trade Overall Status</label>
              <select
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                className="w-full px-3 py-2 rounded-xl glass-input font-semibold"
              >
                <option value="OPEN">OPEN</option>
                <option value="PARTIAL_EXIT">PARTIAL_EXIT</option>
                <option value="WIN">WIN</option>
                <option value="LOSS">LOSS</option>
                <option value="CLOSED">CLOSED</option>
                <option value="BREAKEVEN">BREAKEVEN</option>
                <option value="EXPIRED">EXPIRED</option>
                <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
              </select>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-slate-400 font-medium mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Analyst notes, strategy rationale..."
              className="w-full px-3 py-2 rounded-xl glass-input"
            />
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl glass-panel hover:bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || isOver100}
              className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-md shadow-indigo-600/30 disabled:opacity-50"
            >
              {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Trade'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
