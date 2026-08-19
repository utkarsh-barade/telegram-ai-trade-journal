import React, { useState, useEffect, useCallback } from 'react';
import { LoginView } from './components/LoginView';
import { HeaderNav } from './components/HeaderNav';
import { FilterBar } from './components/FilterBar';
import { OverviewCards } from './components/OverviewCards';
import { ChartsSection } from './components/ChartsSection';
import { TradeTable } from './components/TradeTable';
import { AddEditTradeModal } from './components/AddEditTradeModal';
import { TradeDetailModal } from './components/TradeDetailModal';
import { AnalystLeaderboard } from './components/AnalystLeaderboard';
import { StockAnalyticsTable } from './components/StockAnalyticsTable';
import { TargetHitRateChart } from './components/TargetHitRateChart';
import { api } from './services/api';
import {
  AnalystLeaderboardItem,
  ChartDataResponse,
  FilterOptions,
  OverviewMetrics,
  StockAnalyticsItem,
  TargetHitRates,
  Trade,
  TradeFilterState,
  UserProfile,
} from './types';

const DEFAULT_FILTERS: TradeFilterState = {
  preset: 'all',
  start_date: '',
  end_date: '',
  stock: '',
  option_type: '',
  strike: '',
  analyst_id: '',
  outcome: '',
  pnl_filter: '',
  search: '',
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loadingAuth, setLoadingAuth] = useState<boolean>(true);

  // Filters & Filter options
  const [filters, setFilters] = useState<TradeFilterState>(DEFAULT_FILTERS);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    stocks: [],
    strikes: [],
    analysts: [],
    outcomes: [],
  });

  // Data states
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [charts, setCharts] = useState<ChartDataResponse | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [totalTrades, setTotalTrades] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(20);
  const [sortBy, setSortBy] = useState<string>('trade_date');
  const [sortDir, setSortDir] = useState<string>('desc');

  // Modals
  const [isAddEditOpen, setIsAddEditOpen] = useState<boolean>(false);
  const [editingTrade, setEditingTrade] = useState<Trade | null>(null);
  const [detailTrade, setDetailTrade] = useState<Trade | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);

  // Phase 4 states
  const [activeTab, setActiveTab] = useState<'overview' | 'analysts' | 'stocks' | 'calibration'>('overview');
  const [analystsData, setAnalystsData] = useState<{ leaderboard: AnalystLeaderboardItem[]; disclaimer: string }>({ leaderboard: [], disclaimer: '' });
  const [stockAnalytics, setStockAnalytics] = useState<StockAnalyticsItem[]>([]);
  const [targetHitRates, setTargetHitRates] = useState<TargetHitRates | null>(null);

  // Check auth status on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setLoadingAuth(false);
        return;
      }
      try {
        const profile = await api.getProfile();
        setUser(profile);
        setIsAuthenticated(true);
      } catch (err) {
        localStorage.removeItem('access_token');
        setIsAuthenticated(false);
      } finally {
        setLoadingAuth(false);
      }
    };
    checkAuth();
  }, []);

  // Fetch filter options when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    api.getFilterOptions().then(setFilterOptions).catch(console.error);
  }, [isAuthenticated]);

  const filterKey = JSON.stringify(filters);

  // Load Dashboard Data
  const loadDashboardData = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [ovData, chartData, tableData] = await Promise.all([
        api.getOverview(filters),
        api.getCharts(filters),
        api.getTrades(filters, page, limit, sortBy, sortDir),
      ]);
      setOverview(ovData);
      setCharts(chartData);
      setTrades(tableData.items);
      setTotalTrades(tableData.total_count);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    }
  }, [isAuthenticated, filterKey, page, limit, sortBy, sortDir]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Load Phase 4 Analytics
  const loadPhase4Data = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [anData, stData, tgData] = await Promise.all([
        api.getAnalysts(filters),
        api.getStockAnalytics(filters),
        api.getTargetHitRates(filters),
      ]);
      setAnalystsData(anData);
      setStockAnalytics(stData);
      setTargetHitRates(tgData);
    } catch (err) {
      console.error('Failed to load Phase 4 analytics:', err);
    }
  }, [isAuthenticated, filterKey]);

  useEffect(() => {
    loadPhase4Data();
  }, [loadPhase4Data]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setIsAuthenticated(false);
    setUser(null);
  };

  const handleFilterReset = () => {
    setFilters(DEFAULT_FILTERS);
    setPage(1);
  };

  const handleSortChange = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
  };

  const handleExport = async () => {
    try {
      await api.exportExcel(filters, false);
    } catch (err) {
      alert('Failed to generate Excel export');
    }
  };

  const handleSaveTrade = async (data: Partial<Trade>) => {
    if (editingTrade) {
      await api.updateTrade(editingTrade.id, data);
    } else {
      await api.createTrade(data);
    }
    await loadDashboardData();
    // Refresh filter options if new stock/analyst added
    api.getFilterOptions().then(setFilterOptions).catch(console.error);
  };

  const handleDeleteTrade = async (id: number) => {
    if (!window.confirm(`Are you sure you want to delete Trade #${id}?`)) return;
    try {
      await api.deleteTrade(id);
      await loadDashboardData();
    } catch (err) {
      alert('Failed to delete trade');
    }
  };

  const handleViewDetail = async (t: Trade) => {
    try {
      const fullDetail = await api.getTradeDetail(t.id);
      setDetailTrade(fullDetail);
      setIsDetailOpen(true);
    } catch (err) {
      setDetailTrade(t);
      setIsDetailOpen(true);
    }
  };

  const handleOpenEdit = (t: Trade) => {
    setEditingTrade(t);
    setIsAddEditOpen(true);
  };

  const handleOpenAdd = () => {
    setEditingTrade(null);
    setIsAddEditOpen(true);
  };

  if (loadingAuth) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">
        Authenticating session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <LoginView
        onSuccess={() => {
          setIsAuthenticated(true);
          api.getProfile().then(setUser).catch(console.error);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Navbar */}
      <HeaderNav
        user={user}
        onLogout={handleLogout}
        onExport={handleExport}
        onAddTrade={handleOpenAdd}
      />

      {/* Main Content Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {/* Filter Bar */}
        <FilterBar
          filters={filters}
          options={filterOptions}
          onChange={(newF) => {
            setFilters(newF);
            setPage(1);
          }}
          onReset={handleFilterReset}
        />

        {/* Tab Selector */}
        <div className="flex items-center gap-2 mb-6 border-b border-slate-800 pb-3 overflow-x-auto text-xs">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all ${
              activeTab === 'overview'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                : 'glass-panel text-slate-400 hover:text-slate-200'
            }`}
          >
            📊 Overview & Journal
          </button>
          <button
            onClick={() => setActiveTab('analysts')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all ${
              activeTab === 'analysts'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                : 'glass-panel text-slate-400 hover:text-slate-200'
            }`}
          >
            🏆 Analyst Leaderboard
          </button>
          <button
            onClick={() => setActiveTab('stocks')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all ${
              activeTab === 'stocks'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                : 'glass-panel text-slate-400 hover:text-slate-200'
            }`}
          >
            📦 Stock Analytics
          </button>
          <button
            onClick={() => setActiveTab('calibration')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all ${
              activeTab === 'calibration'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                : 'glass-panel text-slate-400 hover:text-slate-200'
            }`}
          >
            🎯 Target Calibration
          </button>
        </div>

        {activeTab === 'overview' && (
          <>
            {/* Overview KPIs */}
            <OverviewCards metrics={overview} />

            {/* Interactive Charts Section */}
            <ChartsSection data={charts} />

            {/* Paginated Trades Table */}
            <TradeTable
              trades={trades}
              totalCount={totalTrades}
              page={page}
              limit={limit}
              sortBy={sortBy}
              sortDir={sortDir}
              onPageChange={setPage}
              onSortChange={handleSortChange}
              onView={handleViewDetail}
              onEdit={handleOpenEdit}
              onDelete={handleDeleteTrade}
            />
          </>
        )}

        {activeTab === 'analysts' && (
          <AnalystLeaderboard
            leaderboard={analystsData.leaderboard}
            disclaimer={analystsData.disclaimer}
          />
        )}

        {activeTab === 'stocks' && (
          <StockAnalyticsTable items={stockAnalytics} />
        )}

        {activeTab === 'calibration' && targetHitRates && (
          <TargetHitRateChart rates={targetHitRates} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        Telegram AI Trade Journal Agent · Phase 2 Dashboard & Analytics Engine
      </footer>

      {/* Modals */}
      <AddEditTradeModal
        isOpen={isAddEditOpen}
        trade={editingTrade}
        onClose={() => setIsAddEditOpen(false)}
        onSave={handleSaveTrade}
      />

      <TradeDetailModal
        isOpen={isDetailOpen}
        trade={detailTrade}
        onClose={() => setIsDetailOpen(false)}
      />
    </div>
  );
}
