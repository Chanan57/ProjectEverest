"""
Everest v8.0 — Verification Script (Updated)
Tests all modules without requiring MetaTrader5.
"""
import sys

# Mock MetaTrader5 before anything imports config
class MockMT5:
    TIMEFRAME_M30 = 16385
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    def __getattr__(self, name):
        return 0

sys.modules['MetaTrader5'] = MockMT5()

from cache_manager import cache, CacheManager
from intelligence_aggregator import compute_conviction, format_conviction_summary
from macro_engine import _classify_regime

print("=" * 60)
print(" Everest v8.0 — MODULE VERIFICATION (ENHANCED)")
print("=" * 60)

# --- Test 1: Cache Manager ---
print("\n[1/6] Testing Cache Manager...")
c = CacheManager()
c.set("test_key", {"gold": "bullish"}, ttl_seconds=60)
assert c.get("test_key")["gold"] == "bullish"
c.invalidate("test_key")
assert c.get("test_key") is None
print("   ✅ Passed")

# --- Test 2: Config loads correctly ---
print("\n[2/6] Testing Config (v8.0 updated)...")
from config import (
    MAX_RISK_PERCENT_CAP, TP_RATIO, SL_ATR_MULT,
    ENSEMBLE_ENABLED, WEIGHT_TECHNICAL, WEIGHT_ML,
    WEIGHT_SENTIMENT, WEIGHT_NEWS, WEIGHT_MACRO,
    EQUITY_TARGET_PCT
)
assert MAX_RISK_PERCENT_CAP == 0.03, f"Expected 0.03, got {MAX_RISK_PERCENT_CAP}"
assert TP_RATIO == 4.0
assert SL_ATR_MULT == 1.2
assert ENSEMBLE_ENABLED == True
weights_sum = WEIGHT_TECHNICAL + WEIGHT_ML + WEIGHT_SENTIMENT + WEIGHT_NEWS + WEIGHT_MACRO
assert abs(weights_sum - 1.0) < 0.001, f"Weights sum to {weights_sum}, not 1.0"
assert EQUITY_TARGET_PCT == 0.10
print(f"   Risk cap: {MAX_RISK_PERCENT_CAP:.0%} | TP: {TP_RATIO}:1 | Ensemble: {ENSEMBLE_ENABLED}")
print("   ✅ Passed")

# --- Test 3: Intelligence Aggregator (Full Alignment) ---
print("\n[3/6] Testing Conviction (Full Alignment)...")
r = compute_conviction(
    signal="BUY", prob_up=0.68, prob_down=0.32, trend_up=True, trend_down=False,
    sentiment_data={"sentiment_score": 0.45, "bias": "bullish", "confidence": "high", "volume_trend": "rising"},
    news_data={"bias_score": 0.35, "overall_bias": "bullish", "impact_level": "medium"},
    macro_data={"gold_bias": "bullish", "confidence": 0.80, "market_regime": "risk_off",
                "risk_multiplier": 1.15, "do_not_trade": False}
)
print(f"   Conv: {r['conviction']:.0%} | Align: {r['alignment']} | Trade: {r['should_trade']}")
print(f"   Summary: {format_conviction_summary(r)}")
assert r["should_trade"], "Should trade in full alignment"
assert r["conviction"] > 0.5
print("   ✅ Passed")

# --- Test 4: Do-Not-Trade ---
print("\n[4/6] Testing Do-Not-Trade Mode...")
r2 = compute_conviction(
    signal="BUY", prob_up=0.70, prob_down=0.30, trend_up=True, trend_down=False,
    macro_data={"gold_bias": "bullish", "confidence": 0.9, "market_regime": "uncertainty",
                "risk_multiplier": 0.0, "do_not_trade": True}
)
assert not r2["should_trade"], "Should NOT trade in DNT"
print("   ✅ Passed")

# --- Test 5: Macro Classification ---
print("\n[5/6] Testing Macro Engine...")
regime = _classify_regime(
    sentiment_data={"sentiment_score": 0.5, "confidence": "high", "volume_trend": "spiking"},
    news_data={
        "impact_level": "high", "bias_score": -0.4,
        "top_events": [
            {"event_types": ["geopolitical"], "score": -0.8, "impact": "high"},
            {"event_types": ["geopolitical", "safe_haven"], "score": -0.6, "impact": "high"},
        ],
        "embargo_active": False
    },
    adx=28.0
)
print(f"   Regime: {regime['market_regime']} | Gold: {regime['gold_bias']} | "
      f"Conf: {regime['confidence']:.0%}")
assert regime["gold_bias"] == "bullish"
print("   ✅ Passed")

# --- Test 6: Data Engine Features ---
print("\n[6/6] Testing Data Engine Features...")
import pandas as pd
import numpy as np
from data_engine import prepare_data

# Generate synthetic OHLC data
np.random.seed(42)
n = 300
dates = pd.date_range("2024-01-01", periods=n, freq="30min")
close = 2000 + np.cumsum(np.random.randn(n) * 2)
high = close + np.abs(np.random.randn(n)) * 3
low = close - np.abs(np.random.randn(n)) * 3
open_ = close + np.random.randn(n) * 1

test_df = pd.DataFrame({
    "time": dates, "open": open_, "high": high, "low": low,
    "close": close, "tick_volume": np.random.randint(100, 5000, n),
    "spread": np.random.randint(10, 50, n), "real_volume": np.zeros(n)
})

result_df = prepare_data(test_df)

expected_cols = [
    'RSI', 'SMA_200', 'EMA_50', 'dist_ema50', 'ATR', 'ADX',
    'hour', 'return_1', 'MACD_diff', 'MACD_signal_dist',
    'BB_pct', 'BB_width', 'Stoch_K', 'session', 'day_of_week',
    'ATR_ratio', 'vol_ratio', 'return_4', 'return_12', 'dist_sma200_pct'
]
missing = [c for c in expected_cols if c not in result_df.columns]
if missing:
    print(f"   ❌ Missing columns: {missing}")
    assert False, "Missing columns"
else:
    print(f"   Features: {len(expected_cols)} verified ✓")
    print(f"   Rows: {len(result_df)} (from {n} input)")
    # Check no NaN or Inf
    assert not result_df[expected_cols].isnull().any().any(), "NaN detected"
    assert not np.isinf(result_df[expected_cols].values).any(), "Inf detected"
    print("   No NaN/Inf ✓")
print("   ✅ Passed")

# --- FINAL ---
print("\n" + "=" * 60)
print(" ✅ ALL v8.0 MODULES VERIFIED SUCCESSFULLY")
print("=" * 60)
print(" Files tested:")
print("   • config.py              — 3% risk cap, ensemble, dynamic target")
print("   • cache_manager.py       — TTL cache")
print("   • intelligence_aggregator — Conviction scoring")
print("   • macro_engine.py        — Market regime classification")
print("   • data_engine.py         — 20+ features (MACD, BB, Stoch, sessions)")
print(" Ready for backtest! Run: python Backtest_v8.py 🦅")

