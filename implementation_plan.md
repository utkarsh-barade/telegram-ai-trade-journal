# Phase 4 — Deep Analytics, Analyst Evaluation & End-of-Session Reporting

Build Phase 4 of the "Telegram AI Trade Journal Agent" to provide deep analyst evaluation, streak analytics, end-of-session Telegram reporting, stock & trend analytics, target hit-rate analytics, and hand-calculated multi-leg unit tests.

---

## 1. Analyst Evaluation Module (`services/analytics_eval.py`)
- Pure, unit-testable evaluation functions reusing existing weighted P&L math (`Trade.compute_derived_fields`).
- Mandatory framing disclaimer:
  > *"All analyst metrics are analytical indicators from historical data, not financial advice or a guarantee of future performance."*
- Metrics computed per analyst over selectable date ranges:
  - `trades_count`, `wins`, `losses`, `breakevens`, `open_count`, `partial_count`
  - `win_rate`: % of decided trades (WIN / (WIN + LOSS))
  - `avg_win_inr`, `avg_win_pct` (Option Premium Return %)
  - `avg_loss_inr`, `avg_loss_pct` (Option Premium Return %)
  - `gross_profit`, `gross_loss`
  - `profit_factor`: Gross Profit ₹ / Gross Loss ₹
  - `expectancy`: $(Win\% \times Avg\ Win) - (Loss\% \times Avg\ Loss)$, labeled `"Positive"`, `"Negative"`, `"Neutral"`
  - `planned_rr`, `achieved_rr`, `rr_delta` (`achieved_rr - planned_rr`)
  - `net_pnl_inr` (Position P&L ₹)
  - `capital_return_pct` (Capital Return %)
  - `max_drawdown_inr`, `max_drawdown_pct`
  - `longest_win_streak`, `longest_loss_streak`, `current_streak`
    *(Rule: PARTIAL_EXIT trades only count toward win-rate/streaks once fully resolved to WIN/LOSS/BREAKEVEN/CLOSED)*
  - `target_hit_rates`: TG1 hit rate %, TG2 hit rate %, FINAL hit rate %

---

## 2. Telegram Commands (`bot/handlers/commands.py`)
- `/report [optional date range]` (e.g. `/report`, `/report 7d`, `/report 30d`):
  Matches required format:
  ```text
  ANALYST PERFORMANCE
  Trades: 100
  Win Rate: 62%
  Average R:R: 1.80
  Profit Factor: 1.94
  Net P&L: +₹24,500
  Capital Return: +24.50%
  Max Drawdown: -7.20%
  Expectancy: Positive
  ```
- `/eos` (End-of-Session report):
  Matches required format:
  ```text
  📊 END OF SESSION
  Trades: 8
  Wins: 5
  Losses: 2
  Open: 1 (incl. 0 partial)
  Win Rate: 71.43%
  Gross Profit: ₹5,200
  Gross Loss: ₹950
  Net P&L: +₹4,250
  Average R:R: 1.72
  Capital Return: +4.25%
  ```

---

## 3. Dashboard REST Endpoints & React UI Additions
- **Endpoints (`api/dashboard.py`)**:
  - `GET /api/dashboard/analysts`
  - `GET /api/dashboard/stock-analytics`
  - `GET /api/dashboard/trends`
  - `GET /api/dashboard/target-hit-rates`
- **React Dashboard UI (`/frontend`)**:
  - **Analyst Leaderboard**: Sortable grid displaying all metrics per analyst with streak indicators and the mandatory Disclaimer banner.
  - **Stock Analytics Table**: Stock-wise performance table with trade count, win rate, net P&L, profit factor.
  - **Trend View**: Weekly/Monthly Win rate %, Net P&L ₹, Expectancy chart + table.
  - **Target Hit-Rate Chart**: TG1 vs TG2 vs Final target hit rates across all multi-target trades.
  - Explicit visual distinction & labeling for **Option Premium Return (%)**, **Position P&L (₹)**, and **Capital Return (%)**.

---

## 4. Hand-Calculated Seeded Dataset Unit Tests (`tests/test_analytics_eval.py`)
- Seeded test dataset with multi-leg trades (e.g. DLF 650 CE entry @ 20, TG1 25.5 (40% hit), FINAL 27 (60% hit) $\implies$ weighted exit = 26.4 $\implies$ +32% premium return $\implies$ WIN).
- Exact test assertions verifying weighted P&L, win rate, expectancy, drawdown, and streaks against manual calculations.

---

## Proposed Changes

### Backend Components

#### [NEW] [services/analytics_eval.py](file:///e:/AI-Trade-Journal/services/analytics_eval.py)
- Core analyst evaluation service, stock analytics, streak calculations, target hit-rate analytics, and end-of-session metrics.

#### [MODIFY] [services/analytics_service.py](file:///e:/AI-Trade-Journal/services/analytics_service.py)
- Integration with analytics_eval module.

#### [MODIFY] [api/dashboard.py](file:///e:/AI-Trade-Journal/api/dashboard.py)
- REST endpoints `/api/dashboard/analysts`, `/stock-analytics`, `/trends`, and `/target-hit-rates`.

#### [MODIFY] [bot/handlers/commands.py](file:///e:/AI-Trade-Journal/bot/handlers/commands.py)
- `/report` command with formatted analyst performance.
- `/eos` command for End-of-Session report.

#### [MODIFY] [bot/main.py](file:///e:/AI-Trade-Journal/bot/main.py)
- Register `/report` and `/eos` command handlers.

---

### Frontend Components

#### [MODIFY] [frontend/src/types/index.ts](file:///e:/AI-Trade-Journal/frontend/src/types/index.ts)
- Types for `AnalystPerformance`, `StockAnalytics`, `TrendPoint`, `TargetHitRates`.

#### [NEW] [frontend/src/components/AnalystLeaderboard.tsx](file:///e:/AI-Trade-Journal/frontend/src/components/AnalystLeaderboard.tsx)
- Sortable analyst comparison grid with streaks, disclaimer banner, and capital/premium/position return distinction.

#### [NEW] [frontend/src/components/StockAnalyticsTable.tsx](file:///e:/AI-Trade-Journal/frontend/src/components/StockAnalyticsTable.tsx)
- Stock-wise performance table.

#### [NEW] [frontend/src/components/TargetHitRateChart.tsx](file:///e:/AI-Trade-Journal/frontend/src/components/TargetHitRateChart.tsx)
- Visual target calibration chart for TG1 vs TG2 vs Final leg hit rates.

#### [MODIFY] [frontend/src/App.tsx](file:///e:/AI-Trade-Journal/frontend/src/App.tsx)
- Tabbed navigation and layout updates for Analyst Leaderboard, Stock Analytics, and Target Hit Rates.

---

### Test Suite

#### [NEW] [tests/test_analytics_eval.py](file:///e:/AI-Trade-Journal/tests/test_analytics_eval.py)
- Hand-calculated multi-leg seeded dataset testing win rate, expectancy, drawdown, streaks, target hit rates, and capital return.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest tests/ -v` to verify all tests (Phase 1 through Phase 4) pass 100%.

### Manual Verification
- Verify `/report` and `/eos` Telegram command outputs match required format exactly.
- Verify Dashboard UI displays analyst leaderboard, disclaimer banner, stock analytics, and target hit-rate charts cleanly.
