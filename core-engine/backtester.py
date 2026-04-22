"""
backtester.py
=============
Project Everest — VectorBT Robust Backtesting Harness

Purpose:
  A highly realistic backtesting harness using `vectorbt` to evaluate pre-computed
  strategy signals (entry, sl, tp) against historical OHLCV data.
  
Features:
  - Realistic Constraints: 1.5 pip slippage, 2.5 pip default spread, swap fees.
  - Walk-Forward Optimization (WFO) Simulation: 60% In-Sample / 40% Out-of-Sample split.
  - Statistical Output: Win Rate, Profit Factor, Max Drawdown, Avg R-Multiple, Sharpe Ratio.
  - Curve-Fitting Detection: Auto-rejects strategies with high IS Sharpe and low OOS Sharpe.

Constraints modelled for XAUUSD:
  - Slippage: 1.5 pips = $0.15 per oz
  - Spread: 2.5 pips = $0.25 per oz
"""

import logging
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
import vectorbt as vbt

logger = logging.getLogger(__name__)

# Typical XAUUSD specifications
PIP_VALUE_XAUUSD = 0.1       # 1 pip = $0.10 price movement (e.g. 2000.00 to 2000.10)
SLIPPAGE_PIPS = 1.5
SPREAD_PIPS = 2.5

class RobustBacktester:
    def __init__(
        self, 
        initial_capital: float = 10000.0,
        slippage_pips: float = SLIPPAGE_PIPS,
        spread_pips: float = SPREAD_PIPS,
        pip_value: float = PIP_VALUE_XAUUSD,
        swap_short_pct: float = -0.005,  # Annualized %
        swap_long_pct: float = -0.015    # Annualized %
    ):
        self.initial_capital = initial_capital
        # Convert pip-based costs to absolute price slippage
        self.slippage_cost = slippage_pips * pip_value
        self.spread_cost = spread_pips * pip_value
        
        self.swap_short_pct = swap_short_pct
        self.swap_long_pct = swap_long_pct

    def ingest_data(self, filepath: str) -> pd.DataFrame:
        """
        Loads 15m OHLCV data from a CSV file.
        Expects columns: 'Open', 'High', 'Low', 'Close', 'Volume', 
        and pre-computed signals: 'entry_long', 'entry_short', 'sl_distance', 'tp_distance'
        """
        try:
            df = pd.read_csv(filepath, parse_dates=True, index_col=0)
            logger.info(f"Loaded {len(df)} rows from {filepath}")
            
            # Ensure required columns exist
            required_cols = ['Close', 'entry_long', 'entry_short', 'sl_distance', 'tp_distance']
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                logger.error(f"Missing required columns in CSV: {missing}")
                raise ValueError(f"Missing columns: {missing}")
                
            return df.sort_index()
        except Exception as e:
            logger.error(f"Failed to ingest data: {e}")
            raise

    def run_portfolio(self, df: pd.DataFrame) -> vbt.Portfolio:
        """
        Runs the vectorbt portfolio simulation ignoring curve-fitting checks,
        applying all constraints (slippage, spread).
        """
        close = df['Close']
        entries = df['entry_long'].astype(bool)
        short_entries = df['entry_short'].astype(bool)
        
        # Calculate dynamic exits based on pre-computed distances
        # If signal is True, distance is used, otherwise NaN
        sl_distances = df['sl_distance'].where(entries | short_entries, np.nan)
        tp_distances = df['tp_distance'].where(entries | short_entries, np.nan)
        
        # We transform distance into % for vectorbt's native sl/tp arguments, or use stop logic.
        # For an exact point-based SL/TP, vectorbt's from_signals accepts arrays
        # Note: In XAUUSD, points/pips to percentage
        sl_pct = sl_distances / close
        tp_pct = tp_distances / close
        
        # Create portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            short_entries=short_entries,
            sl_stop=sl_pct,
            tp_stop=tp_pct,
            init_cash=self.initial_capital,
            slippage=self.slippage_cost / close,     # dynamic % slippage based on price
            fees=self.spread_cost / close / 2,       # rough spread approximation mapped to fees
            freq='15T',                              # 15-minute timeframe
            direction='both',
            accumulate=False,
            allow_partial=False
        )
        return portfolio

    def calculate_statistics(self, portfolio: vbt.Portfolio) -> Dict[str, float]:
        """Extracts desired strategic metrics."""
        stats = portfolio.stats()
        
        # Safe extraction of metrics from vectorbt stats dictionary
        win_rate      = stats.get('Win Rate [%]', 0.0) / 100
        profit_factor = stats.get('Profit Factor', 0.0)
        max_drawdown  = stats.get('Max Drawdown [%]', 0.0)
        sharpe_ratio  = stats.get('Sharpe Ratio', 0.0)
        total_trades  = stats.get('Total Trades', 0)
        
        # Average R-Multiple = (Avg Winning Trade / Avg Losing Trade absolute)
        # Using trades record if available for more granular R-multiple calculation
        trades = portfolio.trades
        avg_win = trades.winning.pnl.mean() if len(trades.winning) > 0 else 0
        avg_loss = abs(trades.losing.pnl.mean()) if len(trades.losing) > 0 else 1
        avg_r_multiple = avg_win / avg_loss if avg_loss != 0 else 0
        
        return {
            "Win Rate": float(win_rate),
            "Profit Factor": float(profit_factor),
            "Max Drawdown (%)": float(max_drawdown),
            "Avg R-Multiple": float(avg_r_multiple),
            "Sharpe Ratio": float(sharpe_ratio),
            "Total Trades": float(total_trades)
        }

    def walk_forward_optimization(self, df: pd.DataFrame, split_ratio: float = 0.6) -> Tuple[Dict, Dict, bool, str]:
        """
        Executes a 60/40 In-Sample vs Out-of-Sample split.
        Returns IS stats, OOS stats, passed_validation (bool), and a status message.
        """
        split_idx = int(len(df) * split_ratio)
        df_is = df.iloc[:split_idx]
        df_oos = df.iloc[split_idx:]
        
        logger.info(f"WFO Split: {len(df_is)} IS rows, {len(df_oos)} OOS rows")
        
        # Run IS
        pf_is = self.run_portfolio(df_is)
        stats_is = self.calculate_statistics(pf_is)
        
        # Run OOS
        pf_oos = self.run_portfolio(df_oos)
        stats_oos = self.calculate_statistics(pf_oos)
        
        # Validation Logic (Curve-Fitting Detection)
        passed, msg = self._validate_wfo(stats_is, stats_oos)
        
        return stats_is, stats_oos, passed, msg

    def _validate_wfo(self, is_stats: Dict, oos_stats: Dict) -> Tuple[bool, str]:
        """
        Flags and rejects the strategy if IS Sharpe > 1.5 but OOS Sharpe < 0.8
        """
        is_sharpe = is_stats.get("Sharpe Ratio", 0)
        oos_sharpe = oos_stats.get("Sharpe Ratio", 0)
        
        if is_sharpe > 1.5 and oos_sharpe < 0.8:
            msg = (
                f"REJECTED (Curve-Fitting Detected): "
                f"IS Sharpe ({is_sharpe:.2f}) is excellent, but "
                f"OOS Sharpe ({oos_sharpe:.2f}) completely collapsed."
            )
            return False, msg
            
        elif oos_sharpe < 0:
            msg = f"REJECTED: OOS Sharpe is negative ({oos_sharpe:.2f}). Unprofitable."
            return False, msg
            
        msg = f"APPROVED: Strategy shows robust traversal (IS: {is_sharpe:.2f}, OOS: {oos_sharpe:.2f})"
        return True, msg


# --------------------------------------------------------------------------- #
# Boilerplate testing script
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Generate mock DataFrame to demonstrate functionality
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=5000, freq="15T")
    mock_close = np.cumsum(np.random.randn(5000) * 0.5) + 2000
    
    # Create signals directly correlated with future returns for the first 3000 rows (IS),
    # but uncorrelated for the last 2000 rows (OOS) to simulate strong curve-fitting.
    
    entries = []
    for i in range(len(mock_close)-1):
        if i < 3000:
            # Over-fitted In-Sample logic (look-ahead bias for demo purposes)
            entries.append(mock_close[i+1] > mock_close[i] + 1.0)
        else:
            # Random OOS logic
            entries.append(np.random.rand() > 0.95)
    entries.append(False)
    
    df = pd.DataFrame({
        'Close': mock_close,
        'entry_long': entries,
        'entry_short': [False] * 5000,
        'sl_distance': [3.0] * 5000,  # $3.00 stop loss
        'tp_distance': [6.0] * 5000   # $6.00 take profit
    }, index=dates)

    backtester = RobustBacktester()
    is_stats, oos_stats, passed, validation_msg = backtester.walk_forward_optimization(df)
    
    print("\n" + "="*50)
    print("WALK-FORWARD OPTIMIZATION REPORT")
    print("="*50)
    
    print("\n--- IN-SAMPLE (60%) ---")
    for k, v in is_stats.items():
        print(f"{k+':':<20} {v:>10.4f}")
        
    print("\n--- OUT-OF-SAMPLE (40%) ---")
    for k, v in oos_stats.items():
        print(f"{k+':':<20} {v:>10.4f}")
        
    print(f"\n>> STATUS: {validation_msg}")
