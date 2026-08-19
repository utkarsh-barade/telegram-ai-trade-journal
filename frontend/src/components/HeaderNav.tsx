import React from 'react';
import { LogOut, FileSpreadsheet, PlusCircle, TrendingUp, User } from 'lucide-react';
import { UserProfile } from '../types';

interface HeaderNavProps {
  user: UserProfile | null;
  onLogout: () => void;
  onExport: () => void;
  onAddTrade: () => void;
}

export const HeaderNav: React.FC<HeaderNavProps> = ({
  user,
  onLogout,
  onExport,
  onAddTrade,
}) => {
  return (
    <header className="glass-panel border-b border-slate-800 sticky top-0 z-30 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand logo & title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100 tracking-tight flex items-center gap-2">
              Trade Journal Agent
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
                Phase 2
              </span>
            </h1>
            <p className="text-xs text-slate-400">Telegram AI Journal & Analytics Engine</p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={onAddTrade}
            className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center gap-2 transition-all shadow-md shadow-indigo-600/20"
          >
            <PlusCircle className="w-4 h-4" />
            Add Trade
          </button>

          <button
            onClick={onExport}
            className="px-3.5 py-2 rounded-xl glass-panel hover:bg-slate-800 text-emerald-400 font-medium text-xs flex items-center gap-2 transition-all border border-emerald-500/30"
            title="Export 4-Sheet Excel Workbook"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Export Excel (4 Sheets)
          </button>

          {/* User profile & logout */}
          <div className="h-6 w-px bg-slate-800 mx-1"></div>

          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-300">
              <User className="w-4 h-4" />
            </div>
            <div className="hidden sm:block text-left">
              <p className="text-xs font-semibold text-slate-200">{user?.display_name || 'Analyst'}</p>
              <p className="text-[10px] text-slate-400 capitalize">{user?.role || 'Admin'}</p>
            </div>
          </div>

          <button
            onClick={onLogout}
            className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
