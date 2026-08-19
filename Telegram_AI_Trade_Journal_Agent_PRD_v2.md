# Telegram AI Trade Journal Agent — PRD

## 1. Product Overview
A Telegram-based trade journal and analyst-performance system. The user sends trades in simple text, the system parses and stores them, supports current or custom historical dates, tracks outcomes, calculates P&L/capital impact, provides a browser dashboard, and exports Excel reports.

The product is a **trade tracking and analysis system**, not an order-execution or investment-advice system.

## 2. Core Workflow
```text
Telegram Message
      ↓
Trade Parser + Validation
      ↓
Database
      ↓
┌──────────────┬─────────────────┐
│              │                 │
▼              ▼                 ▼
Telegram    Web Dashboard    Market Monitor
Reports     Analytics        Target/SL
│              │                 │
└──────────────┴─────────────────┘
               ↓
        Excel / Reports
```

## 3. Trade Entry
Example:
`DLF 650 CE at 24 BUY SL 22 TG 27`

Bot response:
```text
✅ TRADE SAVED
Trade #001
DLF 650 CE
Entry: ₹24
SL: ₹22
Target: ₹27
Status: OPEN
```

## 4. Custom / Historical Trade Date
The user can explicitly specify a historical date.

Supported examples:
- `DLF 650 CE on 15 Aug 2026 at 24 BUY SL 22 TG 27`
- `15/08/2026 DLF 650 CE @24 BUY SL22 TG27`
- Multi-line trade with `Date: 15-08-2026`

**Rule:** an explicitly supplied trade date takes priority over the Telegram message timestamp. If no date is supplied, use the message date/time.

## 5. Supported Trade Formats
Examples:
- `DLF 650 CE at 24 buy SL 22 TG 27`
- `Buy DLF 650 CE 24 SL 22 Target 27`
- `DLF 650 CE BUY @24 SL22 TGT27`
- `15 Aug DLF 650 CE @24 BUY SL22 TG27`

All formats normalize into one structured trade object.

## 6. Trade Data Model
- Trade ID
- Stock
- Instrument
- Strike
- Option Type (CE/PE)
- Expiry
- Direction (BUY/SELL)
- Entry Price
- Stop Loss
- Target
- Trade Date
- Entry Time
- Exit Price
- Exit Date/Time
- Outcome
- P&L ₹
- P&L %
- Capital
- Capital P&L %
- Risk ₹
- Risk %
- Planned R:R
- Achieved R:R
- Analyst
- Original Telegram message
- Notes
- Created/Updated timestamps

## 7. Trade Lifecycle
```text
NEW → VALIDATING → OPEN
                    ├→ TARGET HIT → WIN
                    ├→ SL HIT → LOSS
                    ├→ MANUAL EXIT → CLOSED
                    ├→ BREAKEVEN
                    └→ EXPIRY → EXPIRED
```

## 8. Market Monitoring
For OPEN trades, the system may monitor market prices through a replaceable market-data adapter.

For options, exact identification must include:
- Underlying
- Strike
- CE/PE
- Expiry

The system must not guess when multiple contracts are possible. Missing information becomes `NEEDS REVIEW`.

Target/SL monitoring:
```text
OPEN TRADE
   ↓
Fetch price
   ↓
Compare Target / SL
   ├→ Target reached → WIN
   ├→ SL reached → LOSS
   └→ Otherwise → OPEN
```

Market-data failures must never automatically mark a trade as WIN/LOSS.

## 9. Telegram Commands
- `/start`
- `/help`
- `/trades`
- `/today`
- `/report`
- `/excel`
- `/capital 100000`
- `/close`
- `/delete`
- `/dashboard`

Manual updates can also be sent naturally, e.g.:
`DLF 650 CE target hit`
or
`Close Trade #001 at 25.50`

## 10. Browser Dashboard
A browser dashboard is required.

### Overview
Show:
- Total Trades
- Open Trades
- Wins
- Losses
- Breakevens
- Win Rate
- Net P&L
- Capital Return
- Average P&L
- Average R:R
- Maximum Drawdown
- Expectancy

### Trade Table
Columns:
`Date | Stock | Instrument | Entry | SL | Target | Exit | Outcome | P&L | P&L %`

Features:
- Search
- Sort
- Pagination
- View
- Edit
- Delete
- Status filtering

### Filters
- Custom date range
- Today / Yesterday
- Week / Month
- Stock
- CE / PE
- Strike
- Analyst
- WIN / LOSS / OPEN / BREAKEVEN
- Profit / Loss

### Charts
- Daily/weekly/monthly P&L
- Cumulative P&L
- Win/Loss
- Drawdown
- Stock-wise performance
- Analyst-wise performance
- Planned vs achieved R:R

## 11. Dashboard Add/Edit Trade
The dashboard must support manual historical trade entry.

Fields:
- Trade Date
- Stock
- Strike
- CE/PE
- Expiry
- Direction
- Entry
- Stop Loss
- Target
- Capital
- Analyst
- Notes

Users can edit all trade fields, with an `updated_at` timestamp and audit history.

## 12. Excel Export
`/excel` and the dashboard generate `.xlsx`.

### Sheet 1 — Trade Journal
Columns:
`Trade ID, Trade Date, Entry Time, Stock, Instrument, Strike, Option Type, Expiry, Direction, Entry, Stop Loss, Target, Exit, Exit Date, Exit Time, Outcome, P&L ₹, P&L %, Capital, Capital P&L %, Risk ₹, Risk %, Planned R:R, Achieved R:R, Analyst, Notes`

### Sheet 2 — Performance Summary
- Total trades
- Win rate
- Net P&L
- Capital return
- Average P&L
- Average R:R
- Profit factor
- Expectancy
- Maximum drawdown
- Best/Worst trade

### Sheet 3 — Daily Summary
- Date
- Number of trades
- Wins
- Losses
- Win rate
- Net P&L
- Capital return

## 13. Capital & P&L
The system supports configurable capital.

Example:
- Capital = ₹1,00,000
- P&L = +₹2,500
- Capital return = +2.50%

The system should distinguish:
- Option premium return
- Position P&L
- Capital-level return

## 14. Analyst Evaluation
Do not evaluate an analyst only by win rate.

Metrics:
- Win rate
- Average win/loss
- Profit factor
- Expectancy
- Planned/achieved R:R
- Net P&L
- Capital return
- Maximum drawdown
- Number of trades
- Winning/losing streaks

Example:
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

The result is an analytical indicator, not financial advice.

## 15. End-of-Session Report
```text
📊 END OF SESSION
Trades: 8
Wins: 5
Losses: 2
Open: 1
Win Rate: 71.43%
Gross Profit: ₹5,200
Gross Loss: ₹950
Net P&L: +₹4,250
Average R:R: 1.72
Capital Return: +4.25%
```

## 16. Free-First Technical Stack
- Telegram Bot API
- Python
- FastAPI
- Rule-based parser + optional local/free AI for ambiguous messages
- SQLite for MVP; PostgreSQL later
- openpyxl for Excel
- APScheduler/background worker
- React/Next.js or lightweight Python dashboard
- Free-tier hosting where suitable
- Replaceable market-data adapter

## 17. Security
- Restrict Telegram access to authorized user IDs.
- Authenticate dashboard.
- Store secrets in environment variables.
- Never hardcode bot/API keys.
- Use HTTPS.
- Protect database credentials.
- Do not expose trade data publicly.

## 18. Error Handling
The system must never silently guess.

Examples:
- Missing expiry → ask for expiry.
- Missing SL → ask for SL.
- Ambiguous instrument → ask user to resend.
- Duplicate trade → show existing trade and ask whether to update or create new.
- Market-data failure → keep trade OPEN/UNKNOWN.

## 19. Data Integrity
Store:
- Unique trade ID
- Original message
- Parsed values
- Explicit/custom trade date
- System timestamps
- Outcome history
- Market-data timestamps
- Price observations
- Manual edit/audit history

## 20. MVP Roadmap

### Phase 1 — Trade Journal
- Telegram bot
- Trade parser
- Custom dates
- SQLite
- Trade CRUD
- Manual outcome updates
- Excel export
- Basic reports

### Phase 2 — Browser Dashboard
- Authentication
- Overview cards
- Trade table
- Search/filters
- Add/Edit/Delete
- Charts
- Dashboard Excel export

### Phase 3 — Market Monitoring
- Market-data adapter
- Exact option contract mapping
- LTP monitoring
- Target/SL detection
- Notifications

### Phase 4 — Advanced Analytics
- Analyst comparison
- Drawdown
- Expectancy
- Profit factor
- Streak analysis
- Stock/strategy-wise analytics
- Monthly/weekly analytics

## 21. Success Criteria
The product is successful when the user can:
1. Send a trade to Telegram.
2. Enter a current or historical date.
3. Have it automatically parsed.
4. Store it persistently.
5. Edit it through Telegram or dashboard.
6. Monitor open trades when reliable market data is available.
7. Detect Target/SL outcomes when supported.
8. View all trades in a browser.
9. Filter and analyze trades.
10. Generate Excel reports.
11. Calculate capital-level performance.
12. Evaluate analyst performance from historical data.

## 22. Final Product Definition

**Telegram AI Trade Journal Agent + Browser Analytics Dashboard**

> Send the trade once. The system maintains the journal, supports historical dates, tracks outcomes, calculates performance, provides a browser dashboard, and exports the complete Excel report.
