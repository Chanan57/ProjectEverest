"""
optimizer.py
============
Project Everest — Parameter Optimization Engine (OpenClaw)

Performs a grid search across the OpenClaw strategy parameter space,
evaluates each combination using Walk-Forward Optimization (60/40 IS/OOS),
and applies strict curve-fitting filters to identify robust parameter sets.

Filtering Rules (hard-coded, non-negotiable):
  1. OOS Sharpe must be >= 0.8
  2. IS Sharpe / OOS Sharpe ratio must be <= 2.0  (anti curve-fitting)

Output:
  Top 5 surviving parameter sets, sorted by OOS Sharpe, saved to CSV.
"""

import itertools
import logging
import os
import time
from dataclasses import asdict
from typing import List, Dict

import numpy as np
import pandas as pd

from strategy import OpenClawStrategy, StrategyParams
from backtester import RobustBacktester

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Parameter Grid Definition
# --------------------------------------------------------------------------- #
PARAM_GRID = {
    "rsi_oversold":      list(range(20, 41, 5)),     # 20, 25, 30, 35, 40
    "rsi_overbought":    list(range(60, 81, 5)),     # 60, 65, 70, 75, 80
    "sl_atr_multiplier": [round(x, 1) for x in np.arange(1.0, 2.1, 0.5)],  # 1.0, 1.5, 2.0
    "tp_atr_multiplier": [round(x, 1) for x in np.arange(1.5, 3.1, 0.5)],  # 1.5, 2.0, 2.5, 3.0
}


def _build_combinations() -> List[Dict]:
    """Explodes the parameter grid into a flat list of dicts."""
    keys = list(PARAM_GRID.keys())
    values = list(PARAM_GRID.values())
    combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
    logger.info(f"Parameter grid: {len(combos)} total combinations.")
    return combos


# --------------------------------------------------------------------------- #
# Core Optimization Loop
# --------------------------------------------------------------------------- #
def optimize_strategy(
    df_raw: pd.DataFrame,
    split_ratio: float = 0.6,
    min_oos_sharpe: float = 0.8,
    max_sharpe_ratio: float = 2.0,
    top_n: int = 5,
) -> pd.DataFrame:
    """
    Runs every parameter combination through the WFO pipeline.

    Args:
        df_raw:          Raw OHLCV DataFrame (from data_fetcher / CSV).
        split_ratio:     IS/OOS split (default 60/40).
        min_oos_sharpe:  Minimum OOS Sharpe to survive filtering.
        max_sharpe_ratio: Maximum IS/OOS Sharpe ratio (curve-fitting cap).
        top_n:           Number of top results to return.

    Returns:
        DataFrame of the top surviving parameter sets, sorted by OOS Sharpe.
    """
    combos = _build_combinations()
    backtester = RobustBacktester()
    results = []

    total = len(combos)
    t_start = time.time()

    for i, params_dict in enumerate(combos, 1):
        params = StrategyParams(**params_dict)
        strategy = OpenClawStrategy(params=params)

        try:
            # Generate signals for this parameter set
            df_signals = strategy.generate_signals(df_raw.copy())

            if df_signals['entry_long'].sum() + df_signals['entry_short'].sum() < 5:
                logger.debug(f"[{i}/{total}] Skipping — too few signals.")
                continue

            # Run Walk-Forward Optimization
            split_idx = int(len(df_signals) * split_ratio)
            df_is  = df_signals.iloc[:split_idx]
            df_oos = df_signals.iloc[split_idx:]

            # In-Sample portfolio
            pf_is = backtester.run_portfolio(df_is)
            stats_is = backtester.calculate_statistics(pf_is)

            # Out-of-Sample portfolio
            pf_oos = backtester.run_portfolio(df_oos)
            stats_oos = backtester.calculate_statistics(pf_oos)

            is_sharpe  = stats_is.get("Sharpe Ratio", 0.0)
            oos_sharpe = stats_oos.get("Sharpe Ratio", 0.0)

            # --- Filtering Logic ---
            # Rule 1: OOS Sharpe floor
            if oos_sharpe < min_oos_sharpe:
                continue

            # Rule 2: Curve-fitting ratio cap
            if oos_sharpe > 0 and is_sharpe / oos_sharpe > max_sharpe_ratio:
                continue

            # Survived both filters — record the result
            row = {
                **params_dict,
                "IS_WinRate":       stats_is["Win Rate"],
                "IS_ProfitFactor":  stats_is["Profit Factor"],
                "IS_Sharpe":        is_sharpe,
                "IS_MaxDD":         stats_is["Max Drawdown (%)"],
                "IS_Trades":        stats_is["Total Trades"],
                "OOS_WinRate":      stats_oos["Win Rate"],
                "OOS_ProfitFactor": stats_oos["Profit Factor"],
                "OOS_Sharpe":       oos_sharpe,
                "OOS_MaxDD":        stats_oos["Max Drawdown (%)"],
                "OOS_Trades":       stats_oos["Total Trades"],
                "OOS_AvgR":         stats_oos["Avg R-Multiple"],
                "Sharpe_Ratio_IS_OOS": round(is_sharpe / oos_sharpe, 3) if oos_sharpe > 0 else np.inf,
            }
            results.append(row)
            logger.info(
                f"[{i}/{total}] ✅ SURVIVED — "
                f"RSI({params.rsi_oversold}/{params.rsi_overbought}) "
                f"SL×{params.sl_atr_multiplier} TP×{params.tp_atr_multiplier} "
                f"| IS Sharpe: {is_sharpe:.2f} | OOS Sharpe: {oos_sharpe:.2f}"
            )

        except Exception as e:
            logger.warning(f"[{i}/{total}] Error with params {params_dict}: {e}")
            continue

        # Progress logging every 25 combos
        if i % 25 == 0:
            elapsed = time.time() - t_start
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            logger.info(f"Progress: {i}/{total} ({rate:.1f} combos/s, ETA: {eta:.0f}s)")

    elapsed_total = time.time() - t_start
    logger.info(f"Optimization complete: {len(results)} survived out of {total} in {elapsed_total:.1f}s.")

    if not results:
        logger.warning("No parameter sets survived the filters. Consider relaxing constraints.")
        return pd.DataFrame()

    # Build results DataFrame and sort by OOS Sharpe
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("OOS_Sharpe", ascending=False).head(top_n)
    results_df = results_df.reset_index(drop=True)

    return results_df


def save_results(results_df: pd.DataFrame, filename: str = "optimized_parameters.csv"):
    """Persists the top parameter sets to CSV in the /data/ directory."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    filepath = os.path.join(data_dir, filename)
    results_df.to_csv(filepath, index=False)
    logger.info(f"Results saved to: {filepath}")


# --------------------------------------------------------------------------- #
# Standalone Execution
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    csv_path = os.path.join(os.path.dirname(__file__), "data", "xauusd_15m_historical.csv")

    if not os.path.exists(csv_path):
        print(f"❌ Historical data not found at: {csv_path}")
        print("   Run data_fetcher.py first to pull XAUUSD M15 data.")
    else:
        print("=" * 60)
        print("  PROJECT EVEREST — OPENCLAW PARAMETER OPTIMIZER")
        print("=" * 60)
        print(f"\nLoading data from: {csv_path}")

        df = pd.read_csv(csv_path, parse_dates=True, index_col=0)
        print(f"Dataset: {len(df)} candles loaded.\n")

        print("Parameter Grid:")
        for key, vals in PARAM_GRID.items():
            print(f"  {key}: {vals}")
        print()

        top_params = optimize_strategy(df)

        if top_params.empty:
            print("\n⚠️  No parameter sets survived the strict filtering.")
        else:
            save_results(top_params)
            print("\n" + "=" * 60)
            print("  TOP SURVIVING PARAMETER SETS (by OOS Sharpe)")
            print("=" * 60)
            print(top_params.to_string(index=False))
            print()
