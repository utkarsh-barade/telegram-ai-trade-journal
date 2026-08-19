import React from 'react';
import { TargetHitRates } from '../types';
import { Target } from 'lucide-react';

interface Props {
  rates: TargetHitRates;
}

export const TargetHitRateChart: React.FC<Props> = ({ rates }) => {
  return (
    <div className="glass-panel rounded-2xl p-6 shadow-xl border border-slate-800 mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-indigo-400" />
          <h3 className="font-bold text-slate-100 text-sm tracking-wide">Multi-Target Hit Rate Calibration</h3>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          Based on {rates.total_trades_with_targets} multi-target trades
        </span>
      </div>

      <p className="text-xs text-slate-400 mb-6">
        Calibration metrics showing how frequently TG1, TG2, and Final Target levels are achieved across historical trades.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* TG1 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-emerald-400 font-mono">TG1 (Leg 1)</span>
            <span className="text-xs text-slate-400 font-mono">Partial Exit</span>
          </div>
          <div className="text-3xl font-extrabold font-mono text-slate-100 mb-2">
            {rates.tg1_rate}%
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div className="bg-emerald-400 h-2 rounded-full" style={{ width: `${rates.tg1_rate}%` }}></div>
          </div>
        </div>

        {/* TG2 */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-amber-400 font-mono">TG2 (Leg 2)</span>
            <span className="text-xs text-slate-400 font-mono">Partial Exit</span>
          </div>
          <div className="text-3xl font-extrabold font-mono text-slate-100 mb-2">
            {rates.tg2_rate}%
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div className="bg-amber-400 h-2 rounded-full" style={{ width: `${rates.tg2_rate}%` }}></div>
          </div>
        </div>

        {/* FINAL */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-cyan-400 font-mono">FINAL TARGET</span>
            <span className="text-xs text-slate-400 font-mono">Full Exit (Win)</span>
          </div>
          <div className="text-3xl font-extrabold font-mono text-slate-100 mb-2">
            {rates.final_rate}%
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div className="bg-cyan-400 h-2 rounded-full" style={{ width: `${rates.final_rate}%` }}></div>
          </div>
        </div>
      </div>
    </div>
  );
};
