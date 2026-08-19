import {
  ChartDataResponse,
  FilterOptions,
  OverviewMetrics,
  Trade,
  TradeFilterState,
  UserProfile,
} from '../types';

const API_BASE = '/api';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function buildQueryString(filters: TradeFilterState, extra: Record<string, any> = {}): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      params.append(key, String(val));
    }
  });
  Object.entries(extra).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      params.append(key, String(val));
    }
  });
  const str = params.toString();
  return str ? `?${str}` : '';
}

export const api = {
  // Auth
  async login(username: string, password: str) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed');
    }
    return res.json();
  },

  async getProfile(): Promise<UserProfile> {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Unauthenticated');
    return res.json();
  },

  // Filter Options
  async getFilterOptions(): Promise<FilterOptions> {
    const res = await fetch(`${API_BASE}/dashboard/filter-options`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load filter options');
    return res.json();
  },

  // Overview KPIs
  async getOverview(filters: TradeFilterState): Promise<OverviewMetrics> {
    const qs = buildQueryString(filters);
    const res = await fetch(`${API_BASE}/dashboard/overview${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load overview metrics');
    return res.json();
  },

  // Paginated Trades Table
  async getTrades(
    filters: TradeFilterState,
    page: number = 1,
    limit: number = 20,
    sortBy: string = 'trade_date',
    sortDir: string = 'desc'
  ): Promise<{ items: Trade[]; total_count: number; page: number; total_pages: number }> {
    const qs = buildQueryString(filters, { page, limit, sort_by: sortBy, sort_dir: sortDir });
    const res = await fetch(`${API_BASE}/dashboard/trades${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load trades list');
    return res.json();
  },

  // Single Trade Detail
  async getTradeDetail(id: number): Promise<Trade> {
    const res = await fetch(`${API_BASE}/dashboard/trade/${id}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load trade detail');
    return res.json();
  },

  // Create Historical Trade
  async createTrade(data: Partial<Trade>): Promise<Trade> {
    const res = await fetch(`${API_BASE}/dashboard/trade`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create trade');
    }
    return res.json();
  },

  // Update Trade / Target Legs
  async updateTrade(id: number, data: Partial<Trade>): Promise<Trade> {
    const res = await fetch(`${API_BASE}/dashboard/trade/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update trade');
    }
    return res.json();
  },

  // Delete Trade
  async deleteTrade(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/dashboard/trade/${id}`, {
      method: 'DELETE',
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to delete trade');
  },

  // Charts
  async getCharts(filters: TradeFilterState): Promise<ChartDataResponse> {
    const qs = buildQueryString(filters);
    const res = await fetch(`${API_BASE}/dashboard/charts${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load chart datasets');
    return res.json();
  },

  // Excel Export
  async exportExcel(filters: TradeFilterState, exportAll: boolean = false): Promise<void> {
    const qs = buildQueryString(filters, { export_all: exportAll });
    const res = await fetch(`${API_BASE}/dashboard/export${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to generate Excel export');
    
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade_journal_${new Date().toISOString().slice(0, 10)}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  // Phase 4 Analyst Evaluation
  async getAnalysts(filters: TradeFilterState): Promise<{ leaderboard: AnalystLeaderboardItem[]; disclaimer: string }> {
    const qs = buildQueryString(filters);
    const res = await fetch(`${API_BASE}/dashboard/analysts${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load analyst evaluation leaderboard');
    return res.json();
  },

  // Stock Analytics
  async getStockAnalytics(filters: TradeFilterState): Promise<StockAnalyticsItem[]> {
    const qs = buildQueryString(filters);
    const res = await fetch(`${API_BASE}/dashboard/stock-analytics${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load stock analytics');
    return res.json();
  },

  // Target Hit Rates
  async getTargetHitRates(filters: TradeFilterState): Promise<TargetHitRates> {
    const qs = buildQueryString(filters);
    const res = await fetch(`${API_BASE}/dashboard/target-hit-rates${qs}`, {
      headers: getAuthHeader(),
    });
    if (!res.ok) throw new Error('Failed to load target hit rates');
    return res.json();
  },
};
