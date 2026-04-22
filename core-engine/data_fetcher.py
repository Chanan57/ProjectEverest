"""
data_fetcher.py
===============
Project Everest — Historical Data Ingestion

Pulls exactly 2 years of 15-minute (M15) OHLCV data for XAUUSD from MetaTrader5.
Converts timestamps to timezone-aware UTC and persists to CSV for backtesting.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import MetaTrader5 as mt5

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def fetch_historical_data(symbol: str = "XAUUSD", years: int = 2, timeframe: int = mt5.TIMEFRAME_M15) -> pd.DataFrame:
    """
    Connects to MT5 and pulls historical OHLCV data.
    Returns a cleaned pandas DataFrame with UTC timezone-aware datetimes.
    """
    logger.info("Initializing MetaTrader5 connection...")
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        sys.exit(1)

    logger.info(f"Checking if symbol '{symbol}' is available...")
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"Symbol '{symbol}' not found or inaccessible in MT5.")
        mt5.shutdown()
        sys.exit(1)

    if not symbol_info.visible:
        logger.info(f"Symbol '{symbol}' is not visible. Attempting to select...")
        if not mt5.symbol_select(symbol, True):
            logger.error(f"Failed to select symbol '{symbol}'.")
            mt5.shutdown()
            sys.exit(1)

    # Calculate date range (2 years back from today)
    utc_now = datetime.now(timezone.utc)
    # Approximate 2 years as 365.25 * 2 days
    start_date = utc_now - timedelta(days=730.5)
    
    logger.info(f"Requesting '{symbol}' {timeframe} data from {start_date.date()} to {utc_now.date()}...")
    
    # Request data from MT5
    # mt5.copy_rates_range expects python datetime objects
    # Note: Depending on the broker's server time timezone, the returned 'time' is usually 
    # either UTC or the broker's local time. We assume UTC based on standard best practices,
    # or at least we treat it as UTC for explicit coercion.
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, utc_now)

    if rates is None or len(rates) == 0:
        logger.error(f"Failed to fetch data for '{symbol}'. Result is empty. Error: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    logger.info(f"Successfully retrieved {len(rates)} candles.")
    mt5.shutdown()

    # Convert to pandas DataFrame
    df = pd.DataFrame(rates)

    # Convert POSIX timestamps to timezone-aware UTC datetimes
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['time'] = df['time'].dt.tz_localize('UTC')

    # Drop unnecessary columns (spread, real_volume)
    columns_to_keep = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
    df = df[columns_to_keep]

    # Set time as index
    df.set_index('time', inplace=True)

    return df

def save_to_csv(df: pd.DataFrame, filename: str = "xauusd_15m_historical.csv"):
    """
    Saves the DataFrame to a CSV in the /data/ directory relative to this script.
    """
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        logger.info(f"Creating directory: {data_dir}")
        os.makedirs(data_dir)

    filepath = os.path.join(data_dir, filename)
    df.to_csv(filepath)
    logger.info(f"Data successfully saved to: {filepath}")

if __name__ == "__main__":
    logger.info("Starting data extraction...")
    historical_df = fetch_historical_data("XAUUSD", years=2, timeframe=mt5.TIMEFRAME_M15)
    save_to_csv(historical_df, "xauusd_15m_historical.csv")
    logger.info("Extraction complete.")
