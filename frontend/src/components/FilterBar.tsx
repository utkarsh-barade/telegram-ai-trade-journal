import React from 'react';
import { Filter, Search, RotateCcw, Calendar } from 'lucide-react';
import { FilterOptions, TradeFilterState } from '../types';

interface FilterBarProps {
  filters: TradeFilterState;
  options: FilterOptions;
  onChange: (newFilters: TradeFilterState) => void;
  onReset: () => void;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filters,
  options,
  onChange,
  onReset,
}) => {
  const updateField = (field: keyof TradeFilterState, value: string) => {
    onChange({ ...filters, [field]: value });
  };

  const handlePresetChange = (preset: string) => {
    onChange({
      ...filters,
      preset,
      start_date: '',
      end_date: '',
    });
  };

  return (
    <div className="glass-panel rounded-2xl p-5 mb-8 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-slate-300 font-semibold text-sm">
          <Filter className="w-4 h-4 text-indigo-400" />
          Filter & Analytics Controls
        </div>

        <button
          onClick={onReset}
          className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
        >
          <RotateCcw className="w-3 h-3" />
          Reset Filters
        </button>
      </div>

      {/* Preset period buttons */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {['all', 'today', 'yesterday', 'week', 'month'].map((p) => {
          const isActive = filters.preset === p && !filters.start_date;
          return (
            <button
              key={p}
              onClick={() => handlePresetChange(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {p === 'all' ? 'All Time' : p}
            </button>
          );
        })}
      </div>

      {/* Grid of Filter Selectors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {/* Custom Date Range */}
        <div className="sm:col-span-2 flex items-center gap-2">
          <div className="relative flex-1">
            <Calendar className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
            <input
              type="date"
              value={filters.start_date}
              onChange={(e) => updateField('start_date', e.target.value)}
              className="w-full pl-9 pr-2 py-1.5 rounded-xl glass-input text-xs"
              placeholder="Start Date"
            />
          </div>
          <span className="text-slate-500 text-xs">to</span>
          <div className="relative flex-1">
            <Calendar className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
            <input
              type="date"
              value={filters.end_date}
              onChange={(e) => updateField('end_date', e.target.value)}
              className="w-full pl-9 pr-2 py-1.5 rounded-xl glass-input text-xs"
              placeholder="End Date"
            />
          </div>
        </div>

        {/* Stock */}
        <div>
          <select
            value={filters.stock}
            onChange={(e) => updateField('stock', e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl glass-input text-xs"
          >
            <option value="">All Stocks</option>
            {options.stocks.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* CE/PE */}
        <div>
          <select
            value={filters.option_type}
            onChange={(e) => updateField('option_type', e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl glass-input text-xs"
          >
            <option value="">All Types (CE/PE)</option>
            <option value="CE">CE (Call)</option>
            <option value="PE">PE (Put)</option>
          </select>
        </div>

        {/* Outcome Status */}
        <div>
          <select
            value={filters.outcome}
            onChange={(e) => updateField('outcome', e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl glass-input text-xs"
          >
            <option value="">All Outcomes</option>
            {options.outcomes.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </div>

        {/* PnL Filter */}
        <div>
          <select
            value={filters.pnl_filter}
            onChange={(e) => updateField('pnl_filter', e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl glass-input text-xs"
          >
            <option value="">All P&L (Profit/Loss)</option>
            <option value="profit">Profitable Trades</option>
            <option value="loss">Losing Trades</option>
          </select>
        </div>

        {/* Analyst */}
        <div>
          <select
            value={filters.analyst_id}
            onChange={(e) => updateField('analyst_id', e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl glass-input text-xs"
          >
            <option value="">All Analysts</option>
            {options.analysts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="sm:col-span-2 lg:col-span-3 relative">
          <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            value={filters.search}
            onChange={(e) => updateField('search', e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-xl glass-input text-xs"
            placeholder="Search by Stock, Instrument, or Notes..."
          />
        </div>
      </div>
    </div>
  );
};
