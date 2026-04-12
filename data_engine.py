"""
Everest v8.0 — Data Engine (Enhanced)
Calculates all technical indicators including new features:
MACD, Bollinger Bands, Stochastic, session encoding, ATR ratio, volume.
"""
import pandas as pd
import numpy as np
import ta
from config import EMA_SECONDARY, PREDICTION_HORIZON


def _encode_session(hour):
    """
    Encode trading session based on UTC hour.
    Gold's prime time is the London-NY overlap (13:00-18.00 UTC).
    Returns: 0=Off-hours, 1=Asian, 2=London, 3=NY, 4=Overlap
    """
    if 0 <= hour < 7:      # Asian session (Tokyo 00:00-08.00 UTC)
        return 1
    elif 7 <= hour < 13:    # London session (08.00-13:00 UTC)
        return 2
    elif 13 <= hour < 17:   # London-NY overlap (13:00-18.00 UTC) — PRIME TIME
        return 4
    elif 17 <= hour < 22:   # NY session (18.00-22:00 UTC)
        return 3
    else:                   # Off-hours (22:00-00:00 UTC)
        return 0


def prepare_data(df):
    """
    Takes raw MT5 candlestick data and calculates all technical indicators.
    Returns a clean, formatted Pandas DataFrame ready for the AI to read.

    v8.0 Enhanced: 14+ features (up from 6)
    """
    # Standardize column names
    df.columns = [x.lower() for x in df.columns]
    df = df.copy()

    # ===================== CORE INDICATORS (V6.4) =====================

    # RSI (Relative Strength Index)
    df['RSI'] = ta.momentum.rsi(df['close'], window=14)

    # Moving Averages
    df['SMA_200'] = ta.trend.sma_indicator(df['close'], window=200)
    df['EMA_50'] = ta.trend.ema_indicator(df['close'], window=EMA_SECONDARY)
    df['dist_ema50'] = df['close'] - df['EMA_50']

    # ATR (Average True Range)
    df['ATR'] = ta.volatility.average_true_range(
        df['high'], df['low'], df['close'], window=14
    )

    # ADX (Average Directional Index)
    df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)

    # Time and Returns
    df['hour'] = df['time'].dt.hour
    df['return_1'] = df['close'].pct_change(1)
    df['rolling_return'] = df['close'].pct_change(PREDICTION_HORIZON)

    # ===================== NEW FEATURES (v8.0) =====================

    # --- MACD (Moving Average Convergence Divergence) ---
    macd = ta.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['MACD_diff'] = macd.macd_diff()           # Histogram (momentum direction)
    df['MACD_signal_dist'] = macd.macd() - macd.macd_signal()  # Distance from signal

    # --- Bollinger Bands ---
    bollinger = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['BB_pct'] = bollinger.bollinger_pband()     # %B: position within bands (0-1)
    df['BB_width'] = bollinger.bollinger_wband()   # Bandwidth: volatility measure

    # --- Stochastic Oscillator ---
    df['Stoch_K'] = ta.momentum.stoch(
        df['high'], df['low'], df['close'], window=14, smooth_window=3
    )

    # --- Session Encoding ---
    df['session'] = df['hour'].apply(_encode_session)

    # --- Day of Week (0=Mon, 4=Fri) ---
    df['day_of_week'] = df['time'].dt.dayofweek

    # --- ATR Ratio (current ATR vs 50-period ATR average) ---
    # Values > 1.0 = expanding volatility, < 1.0 = contracting
    atr_50 = df['ATR'].rolling(window=50).mean()
    df['ATR_ratio'] = df['ATR'] / atr_50

    # --- Volume (tick volume, normalized) ---
    if 'tick_volume' in df.columns:
        vol_col = 'tick_volume'
    elif 'real_volume' in df.columns:
        vol_col = 'real_volume'
    else:
        vol_col = None

    if vol_col and df[vol_col].sum() > 0:
        vol_ma = df[vol_col].rolling(window=20).mean()
        df['vol_ratio'] = df[vol_col] / vol_ma  # > 1.0 = above-average volume
    else:
        df['vol_ratio'] = 1.0  # Default if no volume data

    # --- Multi-period returns (momentum across timeframes) ---
    df['return_4'] = df['close'].pct_change(4)     # 2-hour momentum
    df['return_12'] = df['close'].pct_change(12)    # 6-hour momentum

    # --- Distance from SMA_200 (normalized) ---
    df['dist_sma200_pct'] = (df['close'] - df['SMA_200']) / df['SMA_200'] * 100

    # ===================== CLEANUP =====================

    # Drop rows with incomplete data (NaN) created by moving averages
    df.dropna(inplace=True)

    # Replace any infinities with 0
    df.replace([np.inf, -np.inf], 0, inplace=True)

    return df
