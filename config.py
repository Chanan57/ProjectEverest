import os
from dotenv import load_dotenv
import MetaTrader5 as mt5

# --- Load secrets from .env file ---
load_dotenv()

# =====================================================================
#  Everest v8.0 CONFIGURATION
# =====================================================================

# --- 1. TRADING CORE ---
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M30
RISK_PERCENT = 0.02           # 2% Risk per trade
MAGIC_NUMBER = 888080         # v8.0 Magic Number
MAX_SPREAD_NORMAL = 50
MAX_SPREAD_HIGH_CONF = 100

# --- 2. STRATEGY SETTINGS ---
ADX_THRESHOLD = 20.0          # Minimum trend strength (blocks chop)
TP_RATIO = 4.0                # Take-profit distance = TP_RATIO × SL distance
SL_ATR_MULT = 1.2             # Stop-loss distance = SL_ATR_MULT × ATR
SL_MIN_DISTANCE = 0.50        # Absolute minimum SL distance in price units

# --- 3. RISK LIMITS ---
MAX_RISK_PERCENT_CAP = 0.03   # Iron-clad 3% of balance hard cap per trade

# --- 4. AI & STRATEGY ---
CONFIDENCE_ENTRY = 0.55
CONFIDENCE_REVERSAL = 0.60
HIGH_CONFIDENCE_LVL = 0.65
EMA_SECONDARY = 50
TRAINING_SIZE = 15000

# --- 5. ORACLE HORIZON ---
PREDICTION_HORIZON = 4
MIN_HORIZON_RETURN = 0.0015
USE_ATR_RELATIVE_THRESHOLD = True  # Scale horizon threshold with ATR

# --- 6. TELEGRAM NOTIFICATIONS ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- 7. DASHBOARD ---
EQUITY_TARGET_PCT = 0.10      # 10% growth target from starting equity

# =====================================================================
#  v8.0 INTELLIGENCE LAYER SETTINGS
# =====================================================================

# --- 8. SENTIMENT ENGINE ---
SENTIMENT_MODE = "lightweight"    # "lightweight" = VADER only, "full" = VADER + FinBERT
ENABLE_TWITTER = False            # Disabled — X API too expensive

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "EverestBot/8.0")

SENTIMENT_SUBREDDITS = ["forex", "Gold", "wallstreetbets", "stocks", "economy"]
SENTIMENT_KEYWORDS = [
    "gold", "xauusd", "xau", "usd", "dollar", "inflation", "rate hike",
    "fed", "federal reserve", "interest rate", "war", "recession",
    "safe haven", "treasury", "yields", "cpi", "ppi", "jobs",
    "nonfarm", "non-farm", "unemployment", "gdp", "sanctions"
]
SENTIMENT_POSTS_PER_SUB = 25      # Posts to fetch per subreddit

# --- 9. NEWS INTELLIGENCE ---
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
NEWS_KEYWORDS = "gold OR XAUUSD OR \"interest rate\" OR inflation OR \"federal reserve\" OR war"
NEWS_DOMAINS = "reuters.com,bloomberg.com,cnbc.com,wsj.com,ft.com,bbc.co.uk"
NEWS_RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/topNews",
]

# --- 10. CACHE TTL (seconds) ---
SENTIMENT_CACHE_TTL = 900         # 15 minutes
NEWS_CACHE_TTL = 1800             # 30 minutes
MACRO_CACHE_TTL = 3600            # 60 minutes

# --- 11. INTELLIGENCE WEIGHTS (must sum to 1.0) ---
WEIGHT_TECHNICAL = 0.40
WEIGHT_ML = 0.30
WEIGHT_SENTIMENT = 0.15
WEIGHT_NEWS = 0.10
WEIGHT_MACRO = 0.05

# --- 12. RISK MULTIPLIER BOUNDS ---
RISK_MULT_ALIGNED = 1.15         # All signals agree → slight risk increase
RISK_MULT_PARTIAL = 1.00         # Most signals agree → normal risk
RISK_MULT_CONFLICTING = 0.50     # Signals disagree → halve position
RISK_MULT_DNT = 0.00             # Do-not-trade mode → zero risk

# --- 13. CONVICTION THRESHOLDS ---
MIN_CONVICTION_TO_TRADE = 0.30   # Below this → skip trade entirely

# --- 14. AI ENSEMBLE ---
ENSEMBLE_ENABLED = True           # Use RF + GradientBoosting ensemble
ENSEMBLE_RF_WEIGHT = 0.55         # RandomForest weight in ensemble
ENSEMBLE_GBC_WEIGHT = 0.45        # GradientBoosting weight in ensemble

# =====================================================================
#  v9.0 LLM INTELLIGENCE LAYER SETTINGS
# =====================================================================

# --- 15. LLM ENGINE (Groq API = Primary, Ollama = Fallback) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"      # Free-tier model on Groq
OLLAMA_MODEL = "qwen2.5:7b"                 # Local fallback model
OLLAMA_HOST = "http://localhost:11434"       # Ollama server address
LLM_TIMEOUT_SECONDS = 10                    # Max wait for LLM response
LLM_CACHE_TTL = 900                         # 15 min cache for LLM results
LLM_ENABLED = True                          # Master switch for LLM layer

# --- 16. LLM ADVISORY WEIGHTS ---
# Start at 0.0 (shadow mode) — LLM results are logged but don't affect trades
# Increase to 0.05-0.10 after validating against live performance
WEIGHT_LLM_ADVISORY = 0.00                  # LLM influence on conviction score
LLM_MAX_CONFIDENCE_ADJUSTMENT = 0.10        # Max ±adjustment the LLM can apply
