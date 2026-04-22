"""
strategy.py
===========
Project Everest — OpenClaw Strategy Signal Generator

Produces entry_long, entry_short, sl_distance, and tp_distance columns
from raw OHLCV data and configurable indicator parameters.

This module is the ONLY place where strategy logic lives.
The backtester and optimizer consume its output — they never define signals.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StrategyParams:
    """Tunable parameters for the OpenClaw strategy."""
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    atr_period: int = 14
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 2.0


class OpenClawStrategy:
    """
    RSI + ATR-based mean-reversion / momentum strategy for XAUUSD.

    Signal Logic:
      - LONG  when RSI crosses below oversold threshold (mean reversion buy).
      - SHORT when RSI crosses above overbought threshold (mean reversion sell).
      - SL = ATR * sl_atr_multiplier
      - TP = ATR * tp_atr_multiplier
    """

    def __init__(self, params: StrategyParams = None):
        self.params = params or StrategyParams()

    def _compute_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Compute RSI using exponential moving average of gains/losses."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def _compute_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Compute Average True Range."""
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
        return atr

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Accepts a DataFrame with at minimum: 'open', 'high', 'low', 'close'
        (case-insensitive).  Returns the same DataFrame augmented with:
          - entry_long, entry_short (bool)
          - sl_distance, tp_distance (float)
          - rsi (float, for downstream analytics)
        """
        # Normalize column names to lowercase for resilience
        col_map = {c: c.lower() for c in df.columns}
        work = df.rename(columns=col_map).copy()

        close = work['close']
        high = work.get('high', close)
        low = work.get('low', close)

        p = self.params

        # Indicators
        rsi = self._compute_rsi(close, p.rsi_period)
        atr = self._compute_atr(high, low, close, p.atr_period)

        # Signals — cross-based (value enters the zone this bar)
        prev_rsi = rsi.shift(1)
        entry_long  = (rsi <= p.rsi_oversold) & (prev_rsi > p.rsi_oversold)
        entry_short = (rsi >= p.rsi_overbought) & (prev_rsi < p.rsi_overbought)

        # Stop / Target distances (absolute price units)
        sl_distance = atr * p.sl_atr_multiplier
        tp_distance = atr * p.tp_atr_multiplier

        # Attach to original DataFrame (preserve original column casing)
        out = df.copy()
        out['Close']       = close.values   # ensure a 'Close' column exists for backtester
        out['entry_long']  = entry_long.values
        out['entry_short'] = entry_short.values
        out['sl_distance'] = sl_distance.values
        out['tp_distance'] = tp_distance.values
        out['rsi']         = rsi.values
        out['atr']         = atr.values

        # Drop warm-up rows where indicators are NaN
        warmup = max(p.rsi_period, p.atr_period) + 1
        out = out.iloc[warmup:]

        logger.info(
            f"Signals generated: {entry_long.sum()} longs, {entry_short.sum()} shorts "
            f"(RSI {p.rsi_oversold}/{p.rsi_overbought}, "
            f"SL×{p.sl_atr_multiplier}, TP×{p.tp_atr_multiplier})"
        )
        return out


# --------------------------------------------------------------------------- #
# Standalone test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)

    csv_path = os.path.join(os.path.dirname(__file__), "data", "xauusd_15m_historical.csv")
    if not os.path.exists(csv_path):
        print(f"Historical data not found at {csv_path}. Run data_fetcher.py first.")
    else:
        df = pd.read_csv(csv_path, parse_dates=True, index_col=0)
        strategy = OpenClawStrategy()
        result = strategy.generate_signals(df)
        print(f"\nDataset: {len(result)} rows")
        print(f"Long entries:  {result['entry_long'].sum()}")
        print(f"Short entries: {result['entry_short'].sum()}")
        print(result[['Close', 'rsi', 'atr', 'entry_long', 'entry_short', 'sl_distance', 'tp_distance']].tail(10))
