import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ScatterChart,
  Scatter,
} from 'recharts';
import { ChartDataResponse } from '../types';

interface ChartsSectionProps {
  data: ChartDataResponse | null;
}

export const ChartsSection: React.FC<ChartsSectionProps> = ({ data }) => {
  const [activeTab, setActiveTab] = useState<'daily' | 'cumulative' | 'winloss' | 'drawdown' | 'stock' | 'analyst' | 'rr'>('daily');

  if (!data) {
    return (
      <div className="glass-panel h-80 rounded-2xl mb-8 flex items-center justify-center text-slate-500">
        Loading chart analytics...
      </div>
    );
  }

  const tabs = [
    { id: 'daily', label: 'Daily P&L' },
    { id: 'cumulative', label: 'Cumulative P&L' },
    { id: 'winloss', label: 'Win/Loss Ratio' },
    { id: 'drawdown', label: 'Drawdown' },
    { id: 'stock', label: 'Stock Performance' },
    { id: 'analyst', label: 'Analyst Performance' },
    { id: 'rr', label: 'Planned vs Achieved R:R' },
  ];

  return (
    <div className="glass-panel rounded-2xl p-6 mb-8 shadow-xl">
      {/* Tab Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-slate-200">Interactive Analytics Charts</h2>
        <div className="flex flex-wrap items-center gap-1.5 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Display Area */}
      <div className="h-80 w-full">
        {activeTab === 'daily' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.daily_pnl}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                formatter={(value: any) => [`₹${value.toLocaleString()}`, 'P&L']}
              />
              <Bar dataKey="pnl" fill="#6366f1" radius={[6, 6, 0, 0]}>
                {data.daily_pnl.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'cumulative' && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.cumulative_pnl}>
              <defs>
                <linearGradient id="cumPnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                formatter={(value: any) => [`₹${value.toLocaleString()}`, 'Cumulative P&L']}
              />
              <Area type="monotone" dataKey="cum_pnl" stroke="#10b981" fillOpacity={1} fill="url(#cumPnlGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'winloss' && (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data.win_loss_distribution}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={5}
                dataKey="value"
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
              >
                {data.win_loss_distribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
              />
            </PieChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'drawdown' && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.drawdown_series}>
              <defs>
                <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                formatter={(value: any) => [`-₹${value.toLocaleString()}`, 'Drawdown']}
              />
              <Area type="monotone" dataKey="drawdown" stroke="#f59e0b" fillOpacity={1} fill="url(#ddGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'stock' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.stock_performance} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#64748b" fontSize={11} />
              <YAxis type="category" dataKey="stock" stroke="#64748b" fontSize={11} width={80} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                formatter={(value: any) => [`₹${value.toLocaleString()}`, 'Net P&L']}
              />
              <Bar dataKey="net_pnl" fill="#3b82f6" radius={[0, 6, 6, 0]}>
                {data.stock_performance.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.net_pnl >= 0 ? '#10b981' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'analyst' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.analyst_performance}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="analyst" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
              />
              <Bar dataKey="net_pnl" fill="#8b5cf6" radius={[6, 6, 0, 0]} name="Net P&L ₹" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'rr' && (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="planned_rr" name="Planned R:R" stroke="#64748b" fontSize={11} unit="R" />
              <YAxis dataKey="achieved_rr" name="Achieved R:R" stroke="#64748b" fontSize={11} unit="R" />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                cursor={{ strokeDasharray: '3 3' }}
              />
              <Scatter name="Trades R:R" data={data.planned_vs_achieved_rr} fill="#38bdf8" />
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
