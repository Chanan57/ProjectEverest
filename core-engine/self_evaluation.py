"""
self_evaluation.py
==================
Project Everest — Self-Evaluation & Cluster Learning Module

Continuously learns from losing trades by applying K-Means clustering.
1. Connects to SQLite logs (currently uses mock data injection).
2. Extracts losing trades from the past 7 days.
3. Groups trades based on features (RSI, ATR, Time of Day, Regime).
4. Auto-selects optimal 'k' using the silhouette score.
5. Generates and broadcasts a plain-text 'loss cluster' summary.
"""

import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Set up paths for cross-module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import importlib.util
def _import_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_notifier_mod = _import_from_path(
    "notifier", os.path.join(_PROJECT_ROOT, "telemetry", "notifier.py")
)
TelegramNotifier = _notifier_mod.TelegramNotifier

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "trades_mock.db")


# --------------------------------------------------------------------------- #
# Database Layer (Mocked)
# --------------------------------------------------------------------------- #
def _init_mock_db():
    """Builds a sterile SQLite database seeded with synthetic trading history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create unified trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket INTEGER,
            symbol TEXT,
            direction TEXT,
            entry_time TEXT,
            exit_time TEXT,
            atr_at_entry REAL,
            rsi_at_entry REAL,
            regime TEXT,
            r_multiple REAL
        )
    """)
    
    # Check if we already seeded it
    cursor.execute("SELECT COUNT(*) FROM trades")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    logger.info("Initializing mock database with synthetic historical trades...")
    
    import random
    
    # Generate 150 mock trades over the past 14 days
    now = datetime.now(timezone.utc)
    mock_data = []
    regimes = ["trending", "ranging", "volatile", "risk_on", "event_risk"]
    
    for i in range(150):
        days_ago = random.uniform(0, 14)
        entry_time = now - timedelta(days=days_ago)
        
        # Determine success (approx 40% win rate)
        is_win = random.random() < 0.40
        
        if is_win:
            # Winning trade profile
            r_multiple = random.uniform(0.5, 3.0)
            atr = random.uniform(0.0010, 0.0025)
            rsi = random.uniform(30.0, 70.0)
            regime = random.choices(regimes, weights=[0.4, 0.2, 0.1, 0.2, 0.1])[0]
        else:
            # Losing trade profile - introduce some synthetic clusters
            r_multiple = random.uniform(-1.2, -0.1)
            cluster_type = random.choice([1, 2, 3])
            
            if cluster_type == 1:
                # High volatility, event risk loss
                atr = random.uniform(0.0030, 0.0050)
                rsi = random.uniform(40.0, 60.0)
                regime = "event_risk"
            elif cluster_type == 2:
                # FOMO / Overbought ranging loss
                atr = random.uniform(0.0005, 0.0015)
                rsi = random.uniform(70.0, 85.0)
                regime = "ranging"
            else:
                # Choppy trending loss
                atr = random.uniform(0.0015, 0.0025)
                rsi = random.uniform(20.0, 45.0)
                regime = "trending"

        exit_time = entry_time + timedelta(hours=random.uniform(0.5, 4.0))
        
        mock_data.append((
            random.randint(10000000, 99999999), # ticket
            random.choice(["EURUSD", "GBPUSD", "XAUUSD"]), # symbol
            random.choice(["BUY", "SELL"]), # direction
            entry_time.isoformat(),
            exit_time.isoformat(),
            atr,
            rsi,
            regime,
            r_multiple
        ))

    cursor.executemany("""
        INSERT INTO trades (
            ticket, symbol, direction, entry_time, exit_time, 
            atr_at_entry, rsi_at_entry, regime, r_multiple
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, mock_data)
    
    conn.commit()
    conn.close()


def fetch_recent_losing_trades(days_lookback: int = 7) -> pd.DataFrame:
    """Fetch losing trades (r_multiple < 0) from the past N days."""
    _init_mock_db()
    conn = sqlite3.connect(DB_PATH)
    
    cutoff_time = (datetime.now(timezone.utc) - timedelta(days=days_lookback)).isoformat()
    
    query = f"""
        SELECT 
            entry_time, 
            atr_at_entry, 
            rsi_at_entry, 
            regime, 
            r_multiple
        FROM trades
        WHERE r_multiple < 0 AND entry_time >= '{cutoff_time}'
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        # Extract Time of Day (hour) as a feature
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['hour_of_day'] = df['entry_time'].dt.hour
    
    return df


# --------------------------------------------------------------------------- #
# Machine Learning Layer (Clustering)
# --------------------------------------------------------------------------- #
def cluster_losses(df: pd.DataFrame, max_k: int = 5) -> Tuple[KMeans, pd.DataFrame, ColumnTransformer]:
    """
    Applies K-Means clustering to the losing trades.
    Uses silhouette score to find the optimal 'k'.
    """
    # Define feature sets
    numeric_features = ['atr_at_entry', 'rsi_at_entry', 'hour_of_day']
    categorical_features = ['regime']
    
    # Preprocessing pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_features),
            ('cat', OneHotEncoder(sparse_output=False, handle_unknown='ignore'), categorical_features)
        ]
    )
    
    # Transform data
    X_scaled = preprocessor.fit_transform(df)
    
    # Determine optimal k using silhouette score
    best_k = 2
    best_score = -1.0
    best_model = None
    
    # Need at least k=2 for silhouette score. Max k is bounded by dataset size.
    max_k = min(max_k, len(df) - 1)
    if max_k < 2:
        max_k = 2
        
    for k in range(2, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        labels = kmeans.fit_predict(X_scaled)
        
        # Ensure we don't have a single giant cluster and many empty ones
        if len(np.unique(labels)) > 1:
            score = silhouette_score(X_scaled, labels)
            logger.debug(f"K-Means (k={k}) Silhouette Score: {score:.4f}")
            
            if score > best_score:
                best_score = score
                best_k = k
                best_model = kmeans

    # If we couldn't find a good model (e.g., too few samples), default to k=1
    if best_model is None:
        logger.warning("Could not optimize k. Defaulting to k=1.")
        best_model = KMeans(n_clusters=1, random_state=42, n_init='auto')
        df['cluster'] = best_model.fit_predict(X_scaled)
    else:
        logger.info(f"Optimal clusters identified: k={best_k} (score: {best_score:.4f})")
        df['cluster'] = best_model.predict(X_scaled)
        
    return best_model, df, preprocessor


def get_cluster_profiles(df: pd.DataFrame) -> List[Dict]:
    """Analyzes the raw data distributions within each cluster."""
    profiles = []
    
    for cluster_id in sorted(df['cluster'].unique()):
        cluster_data = df[df['cluster'] == cluster_id]
        
        profile = {
            'cluster_id': int(cluster_id) + 1,
            'count': len(cluster_data),
            'pct_of_losses': len(cluster_data) / len(df) * 100,
            'avg_rsi': cluster_data['rsi_at_entry'].mean(),
            'avg_atr': cluster_data['atr_at_entry'].mean(),
            'dominant_regime': cluster_data['regime'].mode()[0],
            'common_hours': cluster_data['hour_of_day'].mode().tolist()[:2],
            'avg_r_multiple': cluster_data['r_multiple'].mean()
        }
        profiles.append(profile)
        
    # Sort profiles by frequency (highest loss count first)
    profiles.sort(key=lambda x: x['count'], reverse=True)
    return profiles


# --------------------------------------------------------------------------- #
# Reporting Layer
# --------------------------------------------------------------------------- #
def generate_summary_text(profiles: List[Dict], total_losses: int) -> str:
    """Formats cluster profiles into a readable report."""
    
    lines = [
        "🔍 *Self-Evaluation: Weekly Loss Clustering*",
        "━━━━━━━━━━━━━━━━━━",
        f"Analyzed {total_losses} losing trades over the past 7 days.",
        ""
    ]
    
    for p in profiles:
        # Determine session based on common hours (UTC approximation)
        hours = p['common_hours']
        h_str = ", ".join([f"{h:02d}:00" for h in hours])
        
        if any(0 <= h <= 9 for h in hours):
            session = "Asian/Tokyo"
        elif any(8 <= h <= 16 for h in hours):
            session = "London"
        else:
            session = "New York"
            
        # Classify RSI
        if p['avg_rsi'] > 65:
            rsi_desc = "Overbought"
        elif p['avg_rsi'] < 35:
            rsi_desc = "Oversold"
        else:
            rsi_desc = "Neutral/Mid-range"
            
        # Build sentences
        lines.append(f"*Cluster {p['cluster_id']} ({p['count']} trades, {p['pct_of_losses']:.1f}%)*")
        lines.append(f"• Dominant Regime: `{p['dominant_regime'].capitalize()}`")
        lines.append(f"• Avg RSI: `{p['avg_rsi']:.1f}` ({rsi_desc})")
        lines.append(f"• Avg ATR: `{p['avg_atr']:.5f}`")
        lines.append(f"• Session Bias: `{session}` ({h_str} UTC)")
        lines.append(f"• Impact: `{p['avg_r_multiple']:.2f}R` avg loss\n")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("💡 *Actionable Insight:* Review the dominant cluster to adjust strategy logic.")
    
    return "\n".join(lines)


def run_evaluation_cycle():
    """Main entry point: fetches data, clusters, generates report, and broadcasts."""
    logger.info("Initializing Self-Evaluation cycle.")
    
    df = fetch_recent_losing_trades(days_lookback=7)
    if df.empty or len(df) < 5:
        logger.info("Not enough losing trades to perform clustering.")
        return
        
    logger.info(f"Extracting features from {len(df)} losing trades.")
    
    model, clustered_df, preprocessor = cluster_losses(df)
    profiles = get_cluster_profiles(clustered_df)
    report_text = generate_summary_text(profiles, len(df))
    
    logger.info("Evaluation report generated. Broadcasting to Telegram.")
    
    notifier = TelegramNotifier()
    notifier.send_message(report_text)


# --------------------------------------------------------------------------- #
# Standalone Execution (Mock test)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n=== Simulating Friday EOD Self-Evaluation ===\n")
    run_evaluation_cycle()
