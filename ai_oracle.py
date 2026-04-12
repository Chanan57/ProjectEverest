"""
Everest v8.0 — AI Oracle (Enhanced)
Ensemble prediction engine: RandomForest + GradientBoosting.
Walk-forward validation, class weighting, feature importance tracking.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from config import *
from data_engine import prepare_data


# v8.0 EXPANDED PREDICTOR SET (14 features)
PREDICTORS_v8 = [
    # Core V6.4
    'RSI', 'dist_ema50', 'ATR', 'hour', 'return_1', 'ADX',
    # New v8.0
    'MACD_diff', 'MACD_signal_dist',    # MACD momentum
    'BB_pct', 'BB_width',               # Bollinger Bands
    'Stoch_K',                           # Stochastic
    'session',                           # Trading session
    'ATR_ratio',                         # Volatility expansion/contraction
    'return_4',                          # 2-hour momentum
]


def _compute_dynamic_threshold(df):
    """
    Scale the minimum horizon return threshold with current ATR.
    Higher ATR → higher threshold (demanding larger moves in volatile markets).
    """
    if not USE_ATR_RELATIVE_THRESHOLD:
        return MIN_HORIZON_RETURN

    # Use median ATR of the last 200 candles as reference
    recent_atr = df['ATR'].iloc[-200:].median() if len(df) >= 200 else df['ATR'].median()
    recent_price = df['close'].iloc[-200:].median() if len(df) >= 200 else df['close'].median()

    # ATR as percentage of price (typically 0.3-0.8% for gold)
    atr_pct = recent_atr / recent_price

    # Scale threshold: use 20% of ATR% as minimum meaningful move
    dynamic_threshold = max(MIN_HORIZON_RETURN, atr_pct * 0.20)

    return round(dynamic_threshold, 6)


def train_model():
    """
    Downloads historical data and trains the ensemble AI model.

    v8.0 Enhancements:
    - 14 features (up from 6)
    - Walk-forward validation (80/20 split)
    - Class-balanced weighting
    - RandomForest + GradientBoosting ensemble
    - Feature importance reporting
    - Dynamic horizon threshold
    """
    print(f"\n🧠 [ORACLE] Training on {TRAINING_SIZE} candles...", flush=True)
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, TRAINING_SIZE)
    if rates is None or len(rates) < 500:
        print("❌ [ORACLE] Insufficient data for training.", flush=True)
        return None, None

    # Prepare data with all v8.0 features
    df = prepare_data(
        pd.DataFrame(rates).assign(time=lambda x: pd.to_datetime(x['time'], unit='s'))
    )

    # Dynamic horizon threshold
    threshold = _compute_dynamic_threshold(df)
    print(f"   Horizon threshold: {threshold:.4%} "
          f"(ATR-relative: {'ON' if USE_ATR_RELATIVE_THRESHOLD else 'OFF'})", flush=True)

    # Define target
    future_close = df['close'].shift(-PREDICTION_HORIZON)
    future_return = (future_close - df['close']) / df['close']

    df['Target'] = -1
    df.loc[future_return > threshold, 'Target'] = 1   # Bullish
    df.loc[future_return < -threshold, 'Target'] = 0   # Bearish
    clean_df = df[df['Target'] != -1].copy()

    if len(clean_df) < 200:
        print("❌ [ORACLE] Too few labeled samples after filtering.", flush=True)
        return None, None

    # Check which v8.0 features are available
    predictors = [p for p in PREDICTORS_v8 if p in clean_df.columns]
    missing = [p for p in PREDICTORS_v8 if p not in clean_df.columns]
    if missing:
        print(f"   ⚠️ Missing features (skipped): {missing}", flush=True)

    # ==================== WALK-FORWARD SPLIT ====================
    split_idx = int(len(clean_df) * 0.80)
    train_df = clean_df.iloc[:split_idx]
    test_df = clean_df.iloc[split_idx:]

    X_train = train_df[predictors]
    y_train = train_df['Target']
    X_test = test_df[predictors]
    y_test = test_df['Target']

    # Class distribution
    class_counts = y_train.value_counts()
    print(f"   Train: {len(train_df)} samples | Test: {len(test_df)} samples", flush=True)
    print(f"   Classes → Bullish: {class_counts.get(1, 0)} | "
          f"Bearish: {class_counts.get(0, 0)}", flush=True)

    # ==================== TRAIN MODELS ====================

    # Model 1: RandomForest
    rf = RandomForestClassifier(
        n_estimators=200,
        min_samples_split=20,
        max_depth=12,
        class_weight="balanced",
        random_state=1,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)

    # Model 2: GradientBoosting (if ensemble enabled)
    gbc = None
    if ENSEMBLE_ENABLED:
        gbc = GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=5,
            min_samples_split=20,
            subsample=0.8,
            random_state=1
        )
        gbc.fit(X_train, y_train)

    # ==================== VALIDATION ====================
    rf_pred = rf.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    print(f"\n   📊 WALK-FORWARD VALIDATION:", flush=True)
    print(f"   RandomForest OOS Accuracy: {rf_acc:.1%}", flush=True)

    if gbc is not None:
        gbc_pred = gbc.predict(X_test)
        gbc_acc = accuracy_score(y_test, gbc_pred)
        print(f"   GradientBoost OOS Accuracy: {gbc_acc:.1%}", flush=True)

        # Ensemble prediction
        rf_proba = rf.predict_proba(X_test)
        gbc_proba = gbc.predict_proba(X_test)
        ensemble_proba = (ENSEMBLE_RF_WEIGHT * rf_proba + ENSEMBLE_GBC_WEIGHT * gbc_proba)
        ensemble_pred = ensemble_proba.argmax(axis=1)
        ensemble_acc = accuracy_score(y_test, ensemble_pred)
        print(f"   Ensemble OOS Accuracy:     {ensemble_acc:.1%} ← ACTIVE", flush=True)

    # ==================== FEATURE IMPORTANCE ====================
    importances = rf.feature_importances_
    feat_imp = sorted(zip(predictors, importances), key=lambda x: x[1], reverse=True)
    print(f"\n   🏆 TOP FEATURES:", flush=True)
    for feat, imp in feat_imp[:7]:
        bar = "█" * int(imp * 50)
        print(f"      {feat:<20s} {imp:.3f} {bar}", flush=True)

    # Retrain on FULL dataset for production
    rf.fit(clean_df[predictors], clean_df['Target'])
    if gbc is not None:
        gbc.fit(clean_df[predictors], clean_df['Target'])

    print(f"\n✅ [ORACLE] Model trained. {len(predictors)} features | "
          f"Ensemble: {'ON' if gbc else 'OFF'}", flush=True)

    # Pack models
    model_pack = {"rf": rf, "gbc": gbc, "predictors": predictors}
    return model_pack, predictors


def predict_proba(model_pack, row_df):
    """
    Get ensemble prediction probability.

    Args:
        model_pack: dict with 'rf', 'gbc', 'predictors'
        row_df: DataFrame with a single row of features

    Returns:
        prob_up (float): probability of bullish outcome
    """
    predictors = model_pack["predictors"]
    rf = model_pack["rf"]
    gbc = model_pack.get("gbc")

    rf_proba = rf.predict_proba(row_df[predictors])[0]

    if gbc is not None and ENSEMBLE_ENABLED:
        gbc_proba = gbc.predict_proba(row_df[predictors])[0]
        ensemble = ENSEMBLE_RF_WEIGHT * rf_proba + ENSEMBLE_GBC_WEIGHT * gbc_proba
        return ensemble[1]  # prob_up
    else:
        return rf_proba[1]  # prob_up


def get_brain_reason(prob_up, prob_down, rsi, dist_ema, atr, adx):
    """Translates the raw AI probabilities into plain English for the dashboard."""
    if adx < ADX_THRESHOLD:
        return "Market Chopping (Low ADX)"

    if prob_up >= CONFIDENCE_ENTRY:
        if rsi < 40:
            return "Sniper Entry (Dip in Uptrend)"
        if rsi > 70:
            return "Overbought (Caution)"
        return "Bullish Momentum"
    elif prob_down >= CONFIDENCE_ENTRY:
        if rsi > 60:
            return "Sniper Entry (Rally in Downtrend)"
        if rsi < 30:
            return "Oversold (Caution)"
        return "Bearish Momentum"
    else:
        return "Uncertain / Waiting"


def get_enhanced_reason(prob_up, prob_down, rsi, dist_ema, atr, adx,
                         sentiment_data=None, news_data=None, macro_data=None):
    """
    v8.0: Enhanced reasoning that includes intelligence context.
    Returns a tuple: (short_reason, detailed_context)
    """
    base_reason = get_brain_reason(prob_up, prob_down, rsi, dist_ema, atr, adx)

    context_parts = [base_reason]

    if sentiment_data:
        bias = sentiment_data.get("bias", "n/a")
        vol = sentiment_data.get("volume_trend", "n/a")
        context_parts.append(f"Social: {bias} ({vol})")

    if news_data:
        news_bias = news_data.get("overall_bias", "n/a")
        impact = news_data.get("impact_level", "n/a")
        context_parts.append(f"News: {news_bias} (impact: {impact})")

    if macro_data:
        regime = macro_data.get("market_regime", "n/a")
        gold_bias = macro_data.get("gold_bias", "n/a")
        context_parts.append(f"Macro: {regime} (gold: {gold_bias})")

    detailed = " | ".join(context_parts)
    return base_reason, detailed
