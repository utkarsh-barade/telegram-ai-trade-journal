# Telegram AI Trade Journal Agent — Phase 1, 2 & 3

> Send a trade once via Telegram or enter it on the Browser Dashboard. The system parses, stores, tracks partial target exits, monitors live market prices, triggers target/SL hits automatically, provides real-time browser analytics, and exports a 4-sheet Excel report — no auto-trading, no broker API.

---

## Table of Contents

1. [Features](#features)
2. [Project Architecture](#project-architecture)
3. [Prerequisites](#prerequisites)
4. [Setup & Running](#setup--running)
5. [Market Data & Live Monitoring (Phase 3)](#market-data--live-monitoring-phase-3)
6. [Dashboard Access & Auth](#dashboard-access--auth)
7. [Excel Export (4 Sheets)](#excel-export-4-sheets)
8. [Multi-Target (Partial Exit) Syntax](#multi-target-partial-exit-syntax)
9. [Supported Trade Formats](#supported-trade-formats)
10. [Trade Commands & Natural Language](#trade-commands--natural-language)
11. [Running Tests](#running-tests)
12. [Database Migrations](#database-migrations)

---

## Features

- **Robust Trade Parser**: Multi-format rule-based parser handling implicit/explicit dates, option strikes, and multi-target leg levels.
- **Staggered Multi-Target (Partial Exit) Support**: Supports `TG1`, `TG2`, and `Final TG` with custom or even-split allocation (`TG1 25.5 (40%) TG2 26.5 (30%) TG 27 (30%)`).
- **Weighted P&L Engine**: Calculates weighted exit prices and realized P&L across partial exit legs and final exits.
- **Automated Market Data Monitoring (Phase 3)**:
  - Background worker polling open trades against live market prices.
  - Per-leg target hit detection (`TG1` hit $\rightarrow$ `PARTIAL_EXIT`, `FINAL` hit $\rightarrow$ `WIN`).
  - Stop Loss hit detection ($\rightarrow$ closes all remaining pending legs at SL price $\rightarrow$ `LOSS`).
  - Strict contract identification (Stock + Strike + CE/PE + Expiry). Missing/ambiguous fields flag trade as `NEEDS_REVIEW` and exclude from polling.
  - Zero-guess data failure safety: network/API fetch timeouts update status to `DATA_UNAVAILABLE` without ever mutating trade state.
  - Configurable market hours (`09:15` to `15:30` IST) and poll intervals (`POLL_INTERVAL_SECONDS`).
- **Protected Browser Analytics Dashboard**: React + Vite frontend with glassmorphic dark theme, gated by JWT token authentication (`POST /api/auth/login`).
- **12 Overview KPI Metrics**: Total Trades, Open Trades, Wins, Losses, Breakevens, Win Rate %, Net P&L ₹, Capital Return %, Avg P&L ₹, Avg R:R, Max Drawdown ₹/%, Expectancy ₹, Profit Factor, Best/Worst trade.
- **7 Interactive Analytics Charts**: Daily/Weekly P&L, Cumulative Equity Curve, Win/Loss Donut, Drawdown Area, Stock Performance, Analyst Performance, Planned vs Achieved R:R.
- **4-Sheet Excel Export**: `Trade Journal`, `Performance Summary`, `Daily Summary`, `Target Legs Detail`.

---

## Project Architecture

```
AI-Trade-Journal/
├── api/
│   ├── auth.py              # Login & JWT authentication endpoints
│   └── dashboard.py         # Dashboard REST endpoints (Overview, Trades, Charts, Export)
│
├── bot/
│   ├── handlers/
│   │   ├── commands.py      # /start /help /trades /today /capital /close /delete /excel /dashboard
│   │   ├── messages.py      # Free-text trade entry & natural-language update parser
│   │   └── callbacks.py     # Inline keyboard callbacks
│   ├── middlewares/
│   │   └── auth.py          # Telegram user whitelist enforcement
│   └── main.py              # FastAPI app + Telegram bot lifecycle + Dashboard static file server
│
├── db/
│   ├── models.py            # Trade, TradeTarget, OutcomeHistory, UserCapital, UserSession
│   ├── session.py           # DB engine factory
│   └── migrations/          # Alembic migrations (0001_initial.py, 0002_multi_target.py)
│
├── frontend/                # React + Vite TypeScript Dashboard
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx          # Main application container
│   │   ├── components/      # LoginView, HeaderNav, FilterBar, OverviewCards, ChartsSection, TradeTable, Modals
│   │   ├── services/        # API client wrapper
│   │   └── types/           # TypeScript definitions
│   └── dist/                # Production build assets served by FastAPI
│
├── parser/
│   ├── trade_parser.py      # Multi-target trade parser & date rule
│   ├── date_parser.py       # Explicit date extraction
│   └── update_parser.py     # Natural language updates ("TG1 hit", "close remaining at X")
│
├── services/
│   ├── auth_service.py      # JWT encoding/decoding & password hashing
│   ├── analytics_service.py # Overview KPIs & 7 chart datasets engine
│   ├── trade_service.py     # State machine, partial target hits, weighted P&L, multi-filter search
│   ├── capital_service.py   # Capital tracking
│   └── export_service.py    # 4-Sheet Excel export generator
│
├── tests/
│   ├── test_parser.py       # Parser tests
│   ├── test_multi_target_parser.py  # Multi-target parsing tests
│   ├── test_multi_target_service.py # Partial hit & weighted P&L math tests
│   ├── test_analytics.py    # Overview & chart analytics tests
│   ├── test_dashboard_api.py# Auth & REST API tests
│   └── test_export_v2.py    # 4-sheet Excel export tests
│
├── .env.example
├── alembic.ini
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm 9+

---

## Setup & Running

### 1. Environment Setup

```bash
# Clone/navigate to codebase
cd e:\AI-Trade-Journal

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
```

Set credentials in `.env`:
```env
BOT_TOKEN=your_telegram_bot_token
ALLOWED_USER_IDS=123456789
DATABASE_URL=sqlite:///./trade_journal.db
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=admin123
JWT_SECRET=super-secret-key-change-this-in-production
```

### 2. Build Frontend Dashboard

```bash
cd frontend
npm install
npm run build
cd ..
```

### 3. Run FastAPI Backend & Telegram Bot

```bash
python -m bot.main
```
Or via uvicorn directly:
```bash
uvicorn bot.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Dashboard Web UI**: `http://localhost:8000/` or `http://localhost:8000/dashboard`
- **FastAPI Swagger API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

---

## Dashboard Access & Auth

- The dashboard is **gated by authentication**.
- Default login:
  - **Username**: `admin` (or `DASHBOARD_USERNAME` in `.env`)
  - **Password**: `admin123` (or `DASHBOARD_PASSWORD` in `.env`)
- Returns a JWT Bearer token valid for 24 hours.

---

## Excel Export (4 Sheets)

The `/excel` Telegram command and the Dashboard **"Export Excel"** button generate a formatted `.xlsx` workbook containing:

1. **Sheet 1 — Trade Journal**: Complete log of trades with target leg breakdown, weighted exit price, outcome, P&L ₹/%, Risk ₹/%, R:R, and analyst notes.
2. **Sheet 2 — Performance Summary**: Key metrics including Total Trades, Win Rate, Net P&L, Capital Return, Profit Factor, Expectancy, Max Drawdown, and Best/Worst Trade.
3. **Sheet 3 — Daily Summary**: Daily breakdown of trade count, wins, losses, win rate %, and net P&L.
4. **Sheet 4 — Target Legs Detail**: Line-by-line audit table of every individual target leg (`Trade ID`, `Level`, `Target Price`, `Qty %`, `Status`, `Exit Price`, `Exit DateTime`).

---

## Multi-Target (Partial Exit) Syntax

Send staggered targets in Telegram:
- **Implicit even split**: `DLF 650 CE @24 BUY SL 22 TG1 25.5 TG2 26.5 TG 27` (splits remaining qty evenly: 33/33/34%)
- **Explicit percentage allocation**: `DLF 650 CE @24 BUY SL 22 TG1 25.5 (40%) TG2 26.5 (30%) TG 27 (30%)`

Update partial target hits in Telegram:
- `DLF 650 CE TG1 hit` → Marks TG1 hit (40% exited at ₹25.5), updates status to `PARTIAL_EXIT`.
- `Close Trade #001 remaining at 26.80` → Closes remaining 60% position at ₹26.80 and calculates weighted exit price.

---

## Running Tests

Run the full pytest suite (95 tests covering parser, service, multi-target math, analytics engine, REST API, and 4-sheet Excel export):

```bash
.venv\Scripts\python -m pytest tests/ -v
```

---

*Telegram AI Trade Journal Agent — Phase 1 & 2 Complete*
