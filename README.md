# 🦅 Everest v8.0 — The Unbreakable Trading Fortress

> *"Your system has a verified edge. Your only job is to leave the machine alone."*
> — Mark Douglas (adapted for algorithmic execution)

**Everest v8.0** is an institutional-grade, fully autonomous XAUUSD (Gold) trading engine. It combines machine learning, real-time sentiment analysis, global macro narratives, and an aggressive self-discipline enforcement layer that physically prevents human intervention during market hours.

This is not a trading bot. This is a **discipline-enforced execution engine** designed to remove the human element from trade execution entirely.

---

## Table of Contents

1. [System Architecture](#-system-architecture)
2. [Signal Flow — How a Trade Happens](#-signal-flow--how-a-trade-happens)
3. [Core Modules](#-core-modules)
4. [Guardian System](#️-guardian-system)
5. [Kiosk Mode — OS-Level Lockout](#-kiosk-mode--os-level-lockout)
6. [Dead-Man's Switch (Heartbeat Fail-Safe)](#-dead-mans-switch-heartbeat-fail-safe)
7. [Psychology Module](#-psychology-module)
8. [Ctrl+C Exit Protection](#-ctrlc-exit-protection)
9. [Stacking Strategy](#-stacking-strategy)
10. [Telegram Notifications](#-telegram-notifications)
11. [Configuration Reference](#️-configuration-reference)
12. [Project Structure](#-project-structure)
13. [Installation & Setup](#️-installation--setup)
14. [Usage](#-usage)
15. [Maintenance Playbook](#-maintenance-playbook)
16. [Backtesting Guide](#-backtesting-guide)
17. [Troubleshooting](#-troubleshooting)
18. [Known Limitations](#-known-limitations)
19. [Risk Disclaimer](#️-risk-disclaimer)

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Everest v8.0 ENGINE                         │
├──────────────────┬───────────────────┬───────────────────────────┤
│  AI ORACLE       │  INTELLIGENCE     │  GUARDIAN SYSTEM           │
│  (ML Ensemble)   │  (Multi-Modal)    │  (Self-Discipline)         │
│                  │                   │                            │
│  RandomForest    │  Reddit/VADER     │  500ms Trade Sniper        │
│  GradientBoost   │  NewsAPI/RSS      │  Circuit Breakers (5%/15%) │
│  Walk-Forward    │  Macro Regime     │  Violation Tracker         │
│  14 Features     │  Conviction Score │  Withdrawal Detection      │
├──────────────────┴───────────────────┴───────────────────────────┤
│                   MARKET HOURS UTILITY                            │
│  Unified market-status source of truth (US/Eastern anchor)       │
├──────────────────────────────────────────────────────────────────┤
│                   KIOSK MODE (OS LOCKOUT)                         │
│  Full-screen overlay • 24/5 lock • Dead-Man's Switch (60s)       │
│  Psychology conditioning • Zero PnL visibility                   │
├──────────────────────────────────────────────────────────────────┤
│                   METATRADER 5 BRIDGE                             │
│  Live execution • IOC/FOK fallback • Position management         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Signal Flow — How a Trade Happens

Every **30 minutes** (on each new M30 candle), Everest executes the following pipeline:

```
1. GATHER DATA
   └→ Pull 300 candles from MT5 → Compute 14 technical indicators (data_engine.py)

2. AI PREDICTION
   └→ Feed the latest candle into the RF+GBC ensemble → Get P(Bullish) probability

3. MARKET STATE CHECK
   └→ Evaluate: SMA/EMA alignment, RSI level, ADX strength, live spread

4. INTELLIGENCE FUSION (every 15 min, background thread)
   └→ Reddit sentiment (VADER NLP)
   └→ News headlines (NewsAPI + RSS)
   └→ Macro regime classification (Trending / Ranging / High-Vol)
   └→ Forex Factory embargo check

5. GUARDIAN CHECK
   └→ Is the system locked? Any circuit breakers tripped?
   └→ Are we under the 3-position concurrent limit?

6. CONVICTION SCORING
   └→ Intelligence Aggregator fuses all signals into a conviction score
   └→ If conviction < 30% → BLOCK trade
   └→ If signals conflict → HALVE position size

7. SPREAD FILTER
   └→ Normal confidence: spread must be < 50 points
   └→ High confidence (≥65%): spread allowed up to < 100 points

8. ENTRY EXECUTION
   └→ Calculate lot size (2% risk, 3% hard cap, ATR-based SL)
   └→ Guardian validates lot size (max 10.0 lots)
   └→ Submit order via MT5 (IOC fill, FOK fallback)
   └→ Log trade + Send Telegram alert

9. EXIT MONITORING (every 5 seconds while in trade)
   └→ If AI detects reversal (prob > 60%) AND price breaks EMA → Close all positions
```

---

## 🧠 Core Modules

### 1. AI Oracle (`ai_oracle.py`)
The predictive brain of the system.
- **Engine**: Scikit-learn RandomForest + GradientBoosting ensemble (55/45 blend).
- **Features**: 14 technical indicators — ADX, ATR, ATR Ratio, Bollinger %B, Bollinger Width, RSI, MACD, MACD Signal, Stochastic K, SMA/EMA distance, session encoding, day of week, volume ratio, and multi-period returns.
- **Training Data**: 15,000 most recent M30 candles (~312 trading days).
- **Label Logic**: 4-candle forward return against an ATR-relative threshold (0.15% base).
- **Validation**: Walk-forward out-of-sample validation (80/20 split) with class-balanced weighting.
- **Retraining**: Automatic daily retraining at 09:00 local time on fresh candle data.
- **Output**: `P(Bullish)` probability from 0.0 to 1.0.

### 2. Data Engine (`data_engine.py`)
Ingests raw OHLCV data from MetaTrader 5 and computes all technical indicators consumed by the AI Oracle and the decision pipeline. Preserves the `spread` column from MT5 for live spread filtering.

**Indicators computed:**
| Indicator | Window | Description |
|:---|:---|:---|
| SMA_200 | 200 | Long-term trend reference |
| EMA_50 | 50 | Medium-term trend reference |
| RSI | 14 | Momentum oscillator |
| MACD + Signal | 12/26/9 | Trend momentum |
| ADX | 14 | Trend strength |
| ATR | 14 | Volatility measure |
| Bollinger %B + Width | 20/2σ | Price position in volatility bands |
| Stochastic K | 14/3 | Momentum oscillator |
| ATR Ratio | 50 | Current ATR vs. 50-period average |
| Volume Ratio | 20 | Tick volume vs. 20-period average |
| Multi-period returns | 4, 12 | 2-hour and 6-hour momentum |
| Dist from SMA_200 (%) | — | Normalized distance |

### 3. Intelligence Aggregator (`intelligence_aggregator.py`)
The central nervous system that fuses all intelligence sources into a single conviction score.

**Conviction Weights (must sum to 1.0):**
| Source | Weight | Description |
|:---|:---:|:---|
| Technical (SMA/EMA/RSI) | 40% | Price structure and trend alignment |
| Machine Learning | 30% | AI Oracle probability |
| Social Sentiment | 15% | Reddit/VADER crowd analysis |
| News Headlines | 10% | Event detection and headline NLP |
| Macro Regime | 5% | Market environment classification |

**Risk Multiplier Output:**
| Alignment | Multiplier | Effect |
|:---|:---:|:---|
| Strong (all agree) | 1.15× | Slight position size increase |
| Partial (most agree) | 1.00× | Normal sizing |
| Conflicting | 0.50× | Position halved |
| Do-Not-Trade | 0.00× | Trade blocked entirely |

### 4. Sentiment Engine (`sentiment_engine.py`)
- **Source**: Reddit (r/Gold, r/WallStreetBets, r/Forex, r/stocks, r/economy).
- **NLP**: VADER (Valence Aware Dictionary and sEntiment Reasoner) for real-time social sentiment extraction.
- **Keywords**: 25 gold/macro terms (gold, xauusd, inflation, fed, war, recession, etc.).
- **Posts per sub**: 25 (configurable).
- **Caching**: 15-minute TTL to avoid API rate limiting.
- **Output**: Bias direction (bullish/bearish/neutral), post volume classification, and confidence scoring.
- **Graceful Degradation**: If Reddit API keys are missing or the API is down, sentiment returns `None` and is excluded from the conviction calculation without interrupting trading.

### 5. News Intelligence (`news_intelligence.py`)
- **Sources**: NewsAPI (7 domains: Reuters, Bloomberg, CNBC, WSJ, FT, BBC) + RSS feeds.
- **NLP**: Headline sentiment analysis with urgency detection.
- **Event Detection**: Identifies geopolitical events, rate decisions, and economic data releases.
- **Caching**: 30-minute TTL.
- **Output**: Overall bias, event flags, and headline summaries.

### 6. News Filter (`news_filter.py`)
Pre-trade filter that enforces a trading embargo around high-impact USD economic events sourced from Forex Factory. When active, all new entries are blocked until the embargo window passes. Existing positions are managed normally.

### 7. Macro Engine (`macro_engine.py`)
- **Regime Classification**: Identifies TRENDING, RANGING, HIGH-VOLATILITY, or NORMAL market conditions based on ADX, ATR, sentiment skew, and news confluence.
- **Gold Bias**: Computes directional bias for gold based on macro narratives.
- **Do-Not-Trade Signal**: Triggers when conflicting macro signals create an unclear environment.
- **Caching**: 60-minute TTL.

### 8. Risk Manager (`risk_manager.py`)
- **Base Risk**: 2% of account balance per trade (`RISK_PERCENT = 0.02`).
- **Hard Cap**: 3% of balance absolute maximum (`MAX_RISK_PERCENT_CAP = 0.03`).
- **Lot Sizing**: `lots = (balance × risk% × intel_multiplier) / (SL_distance × contract_size)`.
- **Intelligence Adjustment**: Conviction result scales position size between 0.25× and 1.50×.
- **Margin Check**: Validates free margin before order submission.
- **Position Limit**: Maximum 3 concurrent stacked positions (validated by backtest).

### 9. Execution Engine (`execution.py`)
- **Order Types**: Market orders with IOC (Immediate or Cancel) filling mode.
- **Fallback**: Automatic retry with FOK (Fill or Kill) if the broker rejects IOC.
- **Magic Number**: All orders tagged with `888080` for the Guardian to identify.
- **Trade Comments**: Tagged with `V6.4 Confirmed` for audit trail.
- **Failure Handling**: Rejected orders are logged with broker error messages. The bot continues operating.

### 10. Cache Manager (`cache_manager.py`)
Thread-safe, in-memory caching layer for intelligence data. Prevents redundant API calls during the 15-minute intelligence refresh cycle. Each data source has its own configurable TTL (Time-To-Live).

### 11. Market Hours Utility (`market_hours.py`)
**Unified source of truth** for the XAUUSD market schedule. Used by both `main.py` and `kiosk.py` to ensure consistent behavior.

| Period | NY Time | Status |
|:---|:---|:---|
| Sunday 18:00 → Friday 16:57 | Market Open | Kiosk LOCKED, Exit ritual ENFORCED |
| Friday 16:57 → Sunday 18:00 | Market Closed | Kiosk WITHDRAWN, Clean exit allowed |
| Saturday (all day) | Closed | Full maintenance access |

### 12. Logger & Dashboard (`logger.py`)
Renders a live terminal dashboard on every new candle and every 5-second exit check. Includes:
- Current price, spread, and account status.
- AI Oracle probabilities with enhanced reasoning.
- Intelligence indicators (sentiment, news, macro).
- Conviction score and alignment status.
- Mark Douglas psychology quote (rotates every cycle).
- Decision status and risk notes.

Logs all trades to `Everest_Trades_v8.csv` and brain activity to `Everest_Brain_v8.csv` for post-session analysis.

---

## 🛡️ Guardian System (`guardian.py`)

The Guardian is the self-discipline enforcement layer. It runs as a background **daemon thread** inside the main loop, scanning every **500 milliseconds**.

| Rule | Enforcement |
|:---|:---|
| **Unauthorized Trade Detection** | Scans every 500ms for trades with Magic Number ≠ `888080` |
| **Instant Closure** | Automatically closes any manually opened position within ~500ms |
| **Harsh Reality Check** | Prints a psychological confrontation message to the console on every violation |
| **Daily Loss Limit** | Halts all trading if equity drops **5%** below the day's starting balance |
| **Max Drawdown** | **Emergency shutdown** if equity drops **15%** from peak balance |
| **Violation Tracker** | Counts unauthorized trade attempts per session |
| **24-Hour Lockdown** | Triggers full trading suspension after **3** violations in a day |
| **Max Lot Size Cap** | Clamps any individual order to a maximum of **10.0 lots** |
| **Broker Compatibility** | Uses `mt5.symbol_select()`, IOC/FOK fallbacks, and strict typecasting |

### Withdrawal & Deposit Detection

The Guardian monitors MT5 deal history using a **3-day lookback window** (to avoid Windows local timezone vs. MT5 broker timezone mismatches). When it detects a non-trading deal (deposit, withdrawal, credit, charge), it:

1. Adjusts `daily_start_balance` by the exact amount.
2. Adjusts `peak_balance` by the exact amount.
3. Adjusts `starting_balance` by the exact amount.
4. Sends a Telegram alert confirming the adjustment.

This prevents withdrawals from being misinterpreted as trading losses, which would falsely trip the circuit breakers.

---

## 🔒 Kiosk Mode — OS-Level Lockout (`kiosk.py`)

The Kiosk is a full-screen, always-on-top Tkinter overlay that physically blocks the user from interacting with the Windows desktop or MetaTrader 5 during market hours.

### Behaviour

| State | Condition | Action |
|:---|:---|:---|
| **LOCKED** | Market is open AND bot is alive | Full-screen black wall, always-on-top, refreshed every 1 second |
| **WITHDRAWN** | Market is closed (weekend) | Overlay hidden, full desktop access |
| **WITHDRAWN** | Bot heartbeat stale > 60 seconds | Overlay hidden for system repair |

### Properties
- **Alt+F4 disabled**: `WM_DELETE_WINDOW` event is intercepted and discarded.
- **No escape key sequence**: There is no secret key combination to dismiss the Kiosk.
- **24/5 continuous lock**: No mid-week maintenance breaks.
- **Psychology conditioning**: Cycles Mark Douglas quotes every 30 seconds.
- **Status display**: Shows operational status and system health.

---

## 💓 Dead-Man's Switch (Heartbeat Fail-Safe)

The bot writes a Unix timestamp to `kiosk_heartbeat.tmp` at **three strategic points** to guarantee server access in all failure scenarios:

1. **Before the main loop begins** — Seeds the file immediately after AI training completes.
2. **Top of every loop iteration** — Proves the bot entered a new cycle.
3. **Bottom of every loop iteration** — Proves the bot completed the full cycle.

The Kiosk checks this file every **1 second** (when visible) or **5 seconds** (when hidden). If the timestamp is older than **60 seconds**, the Kiosk automatically withdraws.

### Failure Scenarios

| Scenario | Result | Server Access Time |
|:---|:---|:---:|
| Bot crashes (unhandled exception) | Heartbeat goes stale → Kiosk drops | ≤ 60 seconds |
| Bot freezes (API hang) | Heartbeat goes stale → Kiosk drops | ≤ 60 seconds |
| Bot enters error loop | Exception handler skips heartbeat → Kiosk drops | ≤ 60 seconds |
| Kiosk process crashes | No overlay blocking desktop | Immediate |
| Both crash simultaneously | Nothing blocking the desktop | Immediate |
| Weekend / Market closed | Kiosk withdraws by market schedule | Immediate |
| Bot recovers after temporary glitch | Heartbeat resumes → Kiosk re-deploys | ≤ 5 seconds |

---

## 🧘 Psychology Module (`psychology.py`)

Inspired by Mark Douglas's *"Trading in the Zone"*, this module provides psychological conditioning to reinforce trust in the algorithmic system.

- **Content**: 21 curated quotes focused exclusively on probabilistic thinking, trusting the machine, accepting statistical outcomes, and emotional detachment.
- **Display**: Quotes cycle every 30 seconds on both the Kiosk overlay and the terminal dashboard.
- **Philosophy**: Zero references to manual trading skill. Every quote reinforces the message: *"Let the bot work."*

**Example quotes:**
- *"A loss is simply the statistical cost of finding out if the edge was going to work this time. It is a business expense."*
- *"Intervening in the system means you have stopped trusting the verified mathematical edge and started trusting your own fear."*
- *"The goal isn't to make money on this specific trade. The goal is flawless, emotionless execution over a series of 100 trades."*

---

## 🚫 Ctrl+C Exit Protection (`main.py`)

Pressing `Ctrl+C` triggers a **context-aware** response:

### During Market Hours (Sunday 18:00 → Friday 16:57 EST)
1. The user is presented with a **337-character sentence** they must type **exactly** to exit.
2. A hidden timer measures input speed. If completed in under **35 seconds**, the system detects copy-paste and **rejects the exit**.
3. On rejection or incorrect input, the bot resumes the automated trading loop.

### During Market Close (Weekend)
The bot recognizes the market is closed and allows an **immediate, clean shutdown** without the psychological barrier. This enables routine maintenance without friction.

---

## 📊 Stacking Strategy

Everest v8.0 supports **position stacking** — opening additional positions in the same direction during strong trends:

- **Maximum Concurrent Positions**: 3 (configurable in `guardian.py`).
- **Stacking Conditions**: Same direction, AI confidence > 55%, trend alignment confirmed, RSI not overbought (for buys) or oversold (for sells).
- **Compounding**: Each new stack entry uses the current equity for lot calculation, naturally scaling with account growth.
- **Unified Exit**: All stacked positions are closed simultaneously if the AI Oracle detects a reversal signal (P(opposite) > 60% AND price breaks EMA_50).

### Entry / Exit Rules Summary

| Parameter | Value | Description |
|:---|:---|:---|
| Entry Confidence | > 55% | AI Oracle must confirm direction |
| Reversal Exit Confidence | > 60% | Higher bar to prevent premature exits |
| ADX Gate | > 20.0 | Only trade when a trend is mathematically present |
| TP:SL Ratio | 4:1 | Take-profit = 4× the stop-loss distance |
| SL Distance | 1.2× ATR | Dynamic, volatility-adjusted stop-loss |
| SL Minimum | $0.50 | Absolute floor to prevent micro-stops |

---

## 📡 Telegram Notifications (`telegram_notifier.py`)

The bot communicates via Telegram in a deliberately obfuscated format:

### Heartbeat (Every 4 Hours)
```
⏱️ Everest v8.0 Status Report
Status: Operational & Scanning
Guardian: Active - System Secured
No manual intervention permitted.
```
**No balance, equity, PnL, or trade details are disclosed.** This is intentional — seeing numbers causes emotional reactions.

### Trade Execution Alerts
New entries and exits are reported with conviction details but **no running account totals**.

### System Alerts
- Guardian violations (unauthorized trade detected and closed).
- Circuit breaker trips (daily loss or max drawdown).
- Deposit/Withdrawal detection (with adjusted limits confirmation).
- System startup and shutdown notifications.

---

## ⚙️ Configuration Reference (`config.py`)

All tunable parameters live in `config.py`. Sensitive values are loaded from the `.env` file.

### Trading Core
| Parameter | Default | Description |
|:---|:---|:---|
| `SYMBOL` | `XAUUSD` | Trading instrument |
| `TIMEFRAME` | `M30` | 30-minute candles |
| `RISK_PERCENT` | `0.02` | 2% of balance per trade |
| `MAGIC_NUMBER` | `888080` | v8.0 order identifier |
| `MAX_SPREAD_NORMAL` | `50` | Max spread (points) for standard entries |
| `MAX_SPREAD_HIGH_CONF` | `100` | Max spread for high-confidence entries (≥65%) |

### Strategy Settings
| Parameter | Default | Description |
|:---|:---|:---|
| `ADX_THRESHOLD` | `20.0` | Minimum trend strength to enter |
| `TP_RATIO` | `4.0` | Take-profit = 4× SL distance |
| `SL_ATR_MULT` | `1.2` | Stop-loss = 1.2× ATR |
| `SL_MIN_DISTANCE` | `0.50` | Absolute minimum SL in price units |

### AI & Strategy
| Parameter | Default | Description |
|:---|:---|:---|
| `CONFIDENCE_ENTRY` | `0.55` | Minimum AI probability to enter |
| `CONFIDENCE_REVERSAL` | `0.60` | Minimum probability to trigger exit |
| `HIGH_CONFIDENCE_LVL` | `0.65` | Threshold for high-confidence spread rules |
| `TRAINING_SIZE` | `15000` | Number of candles for AI training |
| `PREDICTION_HORIZON` | `4` | Look-ahead candles for label generation |
| `ENSEMBLE_RF_WEIGHT` | `0.55` | RandomForest weight in ensemble |
| `ENSEMBLE_GBC_WEIGHT` | `0.45` | GradientBoosting weight in ensemble |

### Risk & Guardian
| Parameter | Default | Description |
|:---|:---|:---|
| `MAX_RISK_PERCENT_CAP` | `0.03` | 3% absolute max risk per trade |
| `DAILY_LOSS_LIMIT_PCT` | `0.05` | 5% daily loss → circuit breaker |
| `MAX_DRAWDOWN_PCT` | `0.15` | 15% peak drawdown → emergency shutdown |
| `MAX_CONCURRENT_POSITIONS` | `3` | Maximum stacked positions |
| `MAX_LOT_SIZE` | `10.0` | Absolute lot size ceiling |
| `SCAN_INTERVAL_SECONDS` | `0.5` | Guardian scan frequency |

### Intelligence Weights
| Parameter | Default | Description |
|:---|:---|:---|
| `WEIGHT_TECHNICAL` | `0.40` | SMA/EMA/RSI contribution |
| `WEIGHT_ML` | `0.30` | AI Oracle contribution |
| `WEIGHT_SENTIMENT` | `0.15` | Reddit sentiment contribution |
| `WEIGHT_NEWS` | `0.10` | News headline contribution |
| `WEIGHT_MACRO` | `0.05` | Macro regime contribution |

### Cache TTLs
| Parameter | Default | Description |
|:---|:---|:---|
| `SENTIMENT_CACHE_TTL` | `900` | 15 min |
| `NEWS_CACHE_TTL` | `1800` | 30 min |
| `MACRO_CACHE_TTL` | `3600` | 60 min |

---

## 📁 Project Structure

```
Everest_Bot/
├── main.py                    # Master orchestrator (entry point)
├── config.py                  # All configuration constants & environment variables
├── ai_oracle.py               # ML ensemble (RandomForest + GradientBoosting)
├── data_engine.py             # Technical indicator computation (14 features)
├── intelligence_aggregator.py # Multi-modal conviction scoring engine
├── sentiment_engine.py        # Reddit/VADER social sentiment analysis
├── news_intelligence.py       # NewsAPI/RSS headline analysis & event detection
├── macro_engine.py            # Market regime classification & gold bias
├── news_filter.py             # Forex Factory economic calendar embargo
├── risk_manager.py            # Position sizing, risk caps & intelligence scaling
├── execution.py               # MT5 order execution bridge (IOC/FOK fallback)
├── guardian.py                # Self-discipline watchdog, circuit breakers & withdrawal detection
├── kiosk.py                   # Full-screen OS lockout overlay (24/5 lock)
├── market_hours.py            # Unified market schedule source of truth (US/Eastern)
├── psychology.py              # Mark Douglas conditioning quotes (21 quotes)
├── logger.py                  # Live terminal dashboard & CSV trade/brain logs
├── telegram_notifier.py       # Telegram status alerts (HTML parse mode)
├── cache_manager.py           # Thread-safe intelligence data caching
├── forward_test.py            # Paper trading / forward test mode
├── Backtest_v8.py             # Historical backtester with stacking support
├── verify_v8.py               # System verification & diagnostics
├── requirements.txt           # Python dependencies (14 packages)
├── .env                       # API keys & secrets (NEVER committed)
└── .gitignore                 # Git exclusions (.env, logs, CSVs, cache)
```

### Generated Files (Runtime)
| File | Description |
|:---|:---|
| `Everest_Trades_v8.csv` | All executed trades with timestamps, prices, and AI context |
| `Everest_Brain_v8.csv` | Every decision cycle's state (probabilities, indicators, decisions) |
| `kiosk_heartbeat.tmp` | Dead-Man's Switch timestamp (written every 5 seconds) |
| `backtest_stacking_trades.csv` | Backtest trade log |
| `backtest_stacking_chart.html` | Interactive Plotly equity curve |

---

## 🛠️ Installation & Setup

### Prerequisites
- **OS**: Windows 10 or 11
- **Python**: 3.10+ (3.13 recommended)
- **MetaTrader 5**: Installed and connected to a live or demo broker account
- **XAUUSD**: Must be available on your broker

### 1. Clone the Repository
```bash
git clone https://github.com/Chanan57/XAUUSD_Everestv8.git
cd XAUUSD_Everestv8
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Download NLTK Data (First Time Only)
```bash
python -c "import nltk; nltk.download('vader_lexicon')"
```

### 4. Configure Secrets
Create a `.env` file in the root directory:
```ini
# === Everest v8.0 Environment Variables ===

# --- Telegram Notifications ---
TELEGRAM_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_personal_chat_id

# --- Reddit API (Optional — register at https://www.reddit.com/prefs/apps) ---
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=EverestBot/8.0 by YourUsername

# --- NewsAPI (Free tier — register at https://newsapi.org/register) ---
NEWSAPI_KEY=your_newsapi_key
```

> **Note**: Reddit API keys are optional. If omitted, the sentiment engine gracefully degrades and sentiment data is excluded from the conviction calculation.

### 5. Pre-Flight Checklist
- [ ] MetaTrader 5 is open and connected to broker
- [ ] **Algo Trading** button in MT5 toolbar is **Green** (enabled)
- [ ] XAUUSD is visible in Market Watch
- [ ] `.env` is populated with Telegram token + chat ID at minimum
- [ ] Virtual environment is activated (`.venv`)

---

## 🚀 Usage

### Live Trading (Full Autonomous Mode)
```bash
python main.py
```
This activates: AI Training → Intelligence Sweep → Guardian → Kiosk Lockout → Trading Loop.

**⚠️ Warning**: The screen will be locked immediately during market hours. You will not regain desktop access until the weekend (or unless the bot crashes, in which case the Dead-Man's Switch unlocks within 60 seconds).

### Forward Testing (Paper Trading)
```bash
python forward_test.py
```
Runs the full pipeline without sending real orders. Logs all hypothetical signals and decisions to `forward_test_log.csv`.

### System Diagnostics
```bash
python verify_v8.py
```
Validates MT5 connectivity, symbol availability, API keys, module imports, and basic system health.

### Backtesting
```bash
python Backtest_v8.py
```
See the [Backtesting Guide](#-backtesting-guide) section for details.

---

## 🔧 Maintenance Playbook

### Weekly Maintenance Window
**Friday 16:57 EST → Sunday 18:00 EST** (~49 hours of full access)

During this window:
- The Kiosk automatically withdraws.
- `Ctrl+C` exits the bot immediately (no typing penalty).
- Full desktop and MT5 access is available.

### Recommended Weekend Tasks
1. **Check `Everest_Trades_v8.csv`** — Review the week's executed trades.
2. **Check `Everest_Brain_v8.csv`** — Review decision quality.
3. **Run Windows Updates** — Ensure the OS is patched.
4. **Verify MT5 Connection** — Sometimes brokers perform weekend maintenance.
5. **Git Pull Updates** — If you've pushed changes from another machine: `git pull origin main`.

### Adjusting Account Balance (Deposits / Withdrawals)
You can deposit or withdraw from your trading account at any time. The Guardian automatically detects these via MT5's deal history and adjusts all internal limits (daily start, peak balance, starting balance) accordingly. You will receive a Telegram confirmation.

### Restarting After a Crash
If the bot crashes during market hours:
1. The Kiosk will automatically withdraw within 60 seconds.
2. Open a terminal in the project directory.
3. Activate the venv: `.\.venv\Scripts\activate`
4. Restart: `python main.py`

---

## 📈 Backtesting Guide

### Running a Backtest
```bash
python Backtest_v8.py
```

### Configuring the Backtest Window
Edit line 72 in `Backtest_v8.py`:
```python
# Dynamic 2-month lookback (default)
start_date = end_date - timedelta(days=60)

# Fixed date range (example)
# start_date = datetime(2026, 1, 1)
```

### What the Backtest Simulates
| Feature | Simulated? | Notes |
|:---|:---:|:---|
| ADX Filter (ADX > 20) | ✅ | Uses computed ADX from historical data |
| Spread Filter | ✅ | Uses historical broker spread from MT5 |
| SMA/EMA Trend Gates | ✅ | Full SMA_200 + EMA_50 alignment |
| RSI Overbought/Oversold | ✅ | RSI < 70 for buys, > 30 for sells |
| 4:1 TP:SL Ratio | ✅ | Exact same calculation as live |
| ATR-based Stop Loss | ✅ | 1.2× ATR with $0.50 minimum |
| Position Stacking | ✅ | Up to 3 concurrent positions |
| Commission | ✅ | $7 per lot round-trip |
| AI Ensemble Predictions | ✅ | Walk-forward retrained model |
| Slippage | ❌ | Uses candle close price (no slippage model) |
| Live Swap Fees | ❌ | Overnight swap costs not modelled |
| Intelligence Layer | ❌ | No historical sentiment/news/macro replay |

### Backtest Output
- **Console**: Full performance report with profit factor, win rate, max drawdown.
- **CSV**: `backtest_stacking_trades.csv` — Every trade with entry/exit/PnL.
- **Chart**: `backtest_stacking_chart.html` — Interactive Plotly equity curve with trade markers.

### Interpreting Results
> **Important**: Expect live performance to be **30–50% worse** than backtest results due to slippage, live spread variability, and swap costs. A backtest profit factor above 1.5 is a strong indicator of a tradeable edge.

---

## 🔍 Troubleshooting

### Bot won't start — "MT5 Startup Failed"
- Ensure MetaTrader 5 is open and logged in.
- Ensure the **Algo Trading** button is green.
- Try restarting MT5.

### Bot won't start — "Failed to select XAUUSD"
- Your broker may use a different symbol name (e.g., `XAUUSDm`, `GOLD`).
- Add the symbol to Market Watch manually, or update `SYMBOL` in `config.py`.

### Kiosk won't appear on startup
- This is normal during the initial AI training phase (20-30 seconds).
- The Kiosk checks for the heartbeat file. Once the main loop starts writing it, the Kiosk will deploy.

### Kiosk disappears during the week
- The bot likely crashed or entered a continuous error loop.
- Check the terminal for error messages.
- Restart with `python main.py`.

### Circuit breaker tripped falsely
- This was historically caused by deposits/withdrawals being misinterpreted as losses.
- **Fix applied**: The Guardian now uses a 3-day deal lookback and catches all non-trading deal types.
- If the issue persists, restart the bot to re-seed the balance trackers.

### Telegram notifications not working
- Verify `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.
- Test manually: `python -c "from telegram_notifier import send_telegram_alert; send_telegram_alert('Test')"`.
- Telegram failures are silent — they never crash the bot.

### Empty sentiment data
- Reddit API keys may be missing or invalid in `.env`.
- This is non-fatal — the conviction score simply excludes sentiment and adjusts weights.

---

## ⚠️ Known Limitations

1. **Backtest-to-Live Gap**: The backtester does not model slippage, swap fees, or live spread variability. Live results will underperform backtest results.
2. **AI Accuracy**: The ML ensemble achieves ~52-53% out-of-sample accuracy. The edge comes primarily from the trend filters and 4:1 TP:SL ratio, not from highly predictive AI.
3. **Gold Trend Dependency**: The strategy is a trend-following system. Performance degrades significantly during prolonged ranging/choppy markets.
4. **Single Instrument**: Everest is designed exclusively for XAUUSD. It has not been validated on other instruments.
5. **Single Timeframe**: All logic runs on M30. No multi-timeframe confirmation is used.
6. **Windows Only**: The Kiosk lockout, MT5 bridge, and process management are Windows-specific.
7. **No Cloud Redundancy**: The bot runs on a single local machine. If the machine loses power or network, trading stops.

---

## ⚠️ Risk Disclaimer

Trading gold on leverage involves **significant risk of loss** and is not suitable for all investors. The Guardian system and Kiosk lockout are designed to enforce discipline but **do not guarantee profitability**. Past performance (backtests) is **not indicative of future results**. Market conditions change, edges decay, and drawdowns are mathematically inevitable.

**Never trade with money you cannot afford to lose.**

---

**Author**: Chanan Guragain
**Version**: 8.0 (Multi-Modal Intelligence + Discipline Enforcement)
**Repository**: [github.com/Chanan57/XAUUSD_Everestv8](https://github.com/Chanan57/XAUUSD_Everestv8)
**Philosophy**: *Trust the math. Trust the edge. Let the probabilities play out.*

