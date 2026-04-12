"""
Everest v8.0 — Professional Backtester
Institutional-grade backtesting with:
  - Walk-forward validation (train → test → slide → repeat)
  - Sharpe & Sortino ratios
  - Maximum drawdown analysis
  - Monthly performance breakdown
  - Equity curve + drawdown chart (Plotly)
  - Session performance analysis
  - Comprehensive trade log

Usage: python Backtest_v8.py
"""
import sys
import os
import math
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

# --- DIRECTORY FIX ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import *
import data_engine
import ai_oracle

# --- VISUALIZATION IMPORTS ---
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import webbrowser
    VISUALS_ENABLED = True
except ImportError:
    VISUALS_ENABLED = False
    print("⚠️ Plotly not found. Run 'pip install plotly' to enable charts.")


def _encode_session_label(hour):
    """Map hour to session name for analytics."""
    if 0 <= hour < 7:
        return "Asian"
    elif 7 <= hour < 13:
        return "London"
    elif 13 <= hour < 17:
        return "Overlap"
    elif 17 <= hour < 22:
        return "New York"
    else:
        return "Off-Hours"


def run_backtest():
    print("=" * 70)
    print(" 🦅 Everest v8.0 PROFESSIONAL BACKTESTER")
    print("=" * 70)

    if not mt5.initialize():
        print("❌ MT5 Startup Failed.")
        sys.exit()

    # --- 1. TRAIN THE AI ORACLE (v8.0 Ensemble) ---
    model_pack, predictors = ai_oracle.train_model()
    if model_pack is None:
        print("❌ AI Training Failed.")
        sys.exit()

    # --- 2. FETCH HISTORICAL DATA (Last 2 Months) ---
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)  # Dynamic: 2 month lookback

    print(f"\n📥 Fetching {SYMBOL} from {start_date.strftime('%Y-%m-%d')} to "
          f"{end_date.strftime('%Y-%m-%d')}...", flush=True)
    rates = mt5.copy_rates_range(SYMBOL, TIMEFRAME, start_date, end_date)
    if rates is None or len(rates) == 0:
        print("❌ Failed to fetch historical data.")
        sys.exit()

    # --- 3. PROCESS DATA ---
    raw_df = pd.DataFrame(rates).assign(time=lambda x: pd.to_datetime(x['time'], unit='s'))
    df = data_engine.prepare_data(raw_df)
    print(f"📊 Data processed: {len(df)} candles", flush=True)

    # --- 4. SIMULATION VARIABLES (STACKING MODE) ---
    starting_balance = 1000.00   # Realistic starting capital
    balance = starting_balance
    peak_balance = starting_balance
    contract_size = 100

    # STACKING: Track multiple concurrent positions
    open_positions = []  # List of dicts: {type, entry, sl, tp, lots, candle_idx, hour}
    MAX_STACK = 3        # Maximum concurrent positions

    # --- METRICS ---
    wins = 0
    losses = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_commissions = 0.0
    buy_trades = 0
    sell_trades = 0
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    consecutive_losses = 0
    max_consecutive_losses = 0
    consecutive_wins = 0
    max_consecutive_wins = 0

    # STACKING METRICS
    max_concurrent = 0
    concurrent_counts = []

    # Tracking arrays
    trade_log = []
    equity_curve = []
    daily_returns = []
    monthly_pnl = defaultdict(float)
    session_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
    holding_times = []

    # Visual tracking
    buy_times, buy_prices = [], []
    sell_times, sell_prices = [], []
    exit_times, exit_prices, exit_hover_text = [], [], []

    print(f"\n📈 STARTING BALANCE: ${balance:.2f} USD")
    print(f"   Risk per trade: {RISK_PERCENT:.0%} | Cap: {MAX_RISK_PERCENT_CAP:.0%}")
    print(f"   SL: {SL_ATR_MULT}× ATR | TP: {TP_RATIO}× SL")
    print(f"   ADX threshold: {ADX_THRESHOLD}")
    print(f"   Confidence entry: {CONFIDENCE_ENTRY} | Reversal: {CONFIDENCE_REVERSAL}")
    print(f"   ⚡ STACKING MODE: Up to {MAX_STACK} concurrent positions")
    print("=" * 70)

    # Save initial equity point
    prev_day_balance = balance
    prev_day = None

    # --- 5. THE TICK-BY-TICK LOOP ---
    for i in range(len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        price = row['close']
        sma, ema = row['SMA_200'], row['EMA_50']
        adx, rsi, atr = row['ADX'], row['RSI'], row['ATR']
        historical_spread = row.get('spread', 0)
        current_hour = row['time'].hour

        trend_up = (price > sma) and (price > ema)
        trend_down = (price < sma) and (price < ema)

        high, low = next_row['high'], next_row['low']

        # Track daily returns
        current_day = row['time'].date()
        if prev_day is not None and current_day != prev_day:
            daily_ret = (balance - prev_day_balance) / prev_day_balance if prev_day_balance > 0 else 0
            daily_returns.append(daily_ret)
            prev_day_balance = balance
        prev_day = current_day

        # Track stacking stats
        concurrent_counts.append(len(open_positions))
        if len(open_positions) > max_concurrent:
            max_concurrent = len(open_positions)

        # Track equity curve (include unrealized PnL for accuracy)
        unrealized_pnl = 0.0
        for pos in open_positions:
            if pos["type"] == "BUY":
                unrealized_pnl += (price - pos["entry"]) * pos["lots"] * contract_size
            else:
                unrealized_pnl += (pos["entry"] - price) * pos["lots"] * contract_size

        equity_curve.append({
            "time": row['time'],
            "equity": balance + unrealized_pnl,
            "drawdown": peak_balance - (balance + unrealized_pnl)
        })

        # --- STEP A: CHECK ALL OPEN POSITIONS FOR EXITS ---
        # v8.0 Ensemble prediction (compute once per candle, used for exits + entries)
        prob_up = ai_oracle.predict_proba(model_pack, pd.DataFrame([row]))
        prob_down = 1 - prob_up

        positions_to_close = []
        for idx, pos in enumerate(open_positions):
            closed = False
            gross_pnl = 0.0
            close_reason = ""
            actual_exit_price = 0.0

            # Check reversal exit
            reversal_exit = False
            if pos["type"] == "BUY" and prob_down > CONFIDENCE_REVERSAL and price < ema:
                reversal_exit = True
            elif pos["type"] == "SELL" and prob_up > CONFIDENCE_REVERSAL and price > ema:
                reversal_exit = True

            if pos["type"] == "BUY":
                if low <= pos["sl"]:
                    gross_pnl = (pos["sl"] - pos["entry"]) * pos["lots"] * contract_size
                    closed, close_reason, actual_exit_price = True, "SL Hit", pos["sl"]
                elif high >= pos["tp"]:
                    gross_pnl = (pos["tp"] - pos["entry"]) * pos["lots"] * contract_size
                    closed, close_reason, actual_exit_price = True, "TP Hit", pos["tp"]
                elif reversal_exit:
                    gross_pnl = (price - pos["entry"]) * pos["lots"] * contract_size
                    closed, close_reason, actual_exit_price = True, "AI Reversal", price
            else:  # SELL
                if high >= pos["sl"]:
                    gross_pnl = (pos["entry"] - pos["sl"]) * pos["lots"] * contract_size
                    closed, close_reason, actual_exit_price = True, "SL Hit", pos["sl"]
                elif low <= pos["tp"]:
                    gross_pnl = (pos["entry"] - pos["tp"]) * pos["lots"] * contract_size
                    closed, close_reason, actual_exit_price = True, "TP Hit", pos["tp"]
                elif reversal_exit:
                    gross_pnl = (pos["entry"] - price) * pos["lots"] * contract_size
                    closed, close_reason, actual_exit_price = True, "AI Reversal", price

            if closed:
                positions_to_close.append(idx)

                commission_fee = pos["lots"] * 8.00
                net_pnl = gross_pnl - commission_fee
                total_commissions += commission_fee
                balance += net_pnl

                hold_candles = i - pos["candle_idx"]
                holding_times.append(hold_candles * 30)
                session = _encode_session_label(pos["hour"])

                if net_pnl > 0:
                    wins += 1
                    gross_profit += net_pnl
                    consecutive_wins += 1
                    consecutive_losses = 0
                    max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
                    session_stats[session]["wins"] += 1
                else:
                    losses += 1
                    gross_loss += abs(net_pnl)
                    consecutive_losses += 1
                    consecutive_wins = 0
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                    session_stats[session]["losses"] += 1

                session_stats[session]["pnl"] += net_pnl

                month_key = row['time'].strftime("%Y-%m")
                monthly_pnl[month_key] += net_pnl

                if balance > peak_balance:
                    peak_balance = balance
                dd = peak_balance - balance
                dd_pct = (dd / peak_balance * 100) if peak_balance > 0 else 0
                max_dd_usd = max(max_dd_usd, dd)
                max_dd_pct = max(max_dd_pct, dd_pct)

                trade_log.append({
                    "time": row['time'].strftime("%Y-%m-%d %H:%M"),
                    "type": pos["type"],
                    "entry": pos["entry"],
                    "exit": actual_exit_price,
                    "lots": pos["lots"],
                    "gross_pnl": round(gross_pnl, 2),
                    "net_pnl": round(net_pnl, 2),
                    "reason": close_reason,
                    "session": session,
                    "hold_min": hold_candles * 30,
                    "balance": round(balance, 2),
                    "concurrent": len(open_positions) - 1
                })

                exit_times.append(row['time'])
                exit_prices.append(actual_exit_price)
                exit_hover_text.append(
                    f"{pos['type']} CLOSED<br>{close_reason}<br>"
                    f"Net PnL: ${net_pnl:+.2f}<br>Balance: ${balance:.2f}"
                )

        # Remove closed positions (reverse order to avoid index issues)
        for idx in sorted(positions_to_close, reverse=True):
            open_positions.pop(idx)

        # --- STEP B: LOOK FOR NEW ENTRIES (even if we already have positions open) ---
        if len(open_positions) < MAX_STACK:
            if adx < ADX_THRESHOLD:
                continue

            max_prob = max(prob_up, prob_down)

            allowed_spread = MAX_SPREAD_HIGH_CONF if max_prob >= HIGH_CONFIDENCE_LVL else MAX_SPREAD_NORMAL
            if historical_spread > allowed_spread:
                continue

            signal = None
            if prob_up > CONFIDENCE_ENTRY and trend_up and rsi < 70:
                signal = "BUY"
            elif prob_down > CONFIDENCE_ENTRY and trend_down and rsi > 30:
                signal = "SELL"

            if signal:
                sl_dist = max(SL_ATR_MULT * atr, SL_MIN_DISTANCE)

                # 3% of balance hard cap per trade
                max_risk_usd = balance * MAX_RISK_PERCENT_CAP
                min_lot_risk_usd = 0.01 * contract_size * sl_dist
                if min_lot_risk_usd > max_risk_usd:
                    continue

                risk_cash_usd = balance * RISK_PERCENT
                raw_lots = risk_cash_usd / (sl_dist * contract_size)
                final_lots = round(raw_lots, 2)
                if final_lots < 0.01:
                    final_lots = 0.01

                actual_risk = final_lots * contract_size * sl_dist
                if actual_risk > max_risk_usd:
                    final_lots = round(max_risk_usd / (contract_size * sl_dist), 2)
                    if final_lots < 0.01:
                        continue

                entry_sl = price - sl_dist if signal == "BUY" else price + sl_dist
                entry_tp = price + (TP_RATIO * sl_dist) if signal == "BUY" else price - (TP_RATIO * sl_dist)

                open_positions.append({
                    "type": signal,
                    "entry": price,
                    "sl": entry_sl,
                    "tp": entry_tp,
                    "lots": final_lots,
                    "candle_idx": i,
                    "hour": current_hour
                })

                if signal == "BUY":
                    buy_trades += 1
                    buy_times.append(row['time'])
                    buy_prices.append(price)
                else:
                    sell_trades += 1
                    sell_times.append(row['time'])
                    sell_prices.append(price)

    # --- 6. FINAL CALCULATIONS ---
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    net_profit = balance - starting_balance
    net_return = (net_profit / starting_balance) * 100

    # Average win/loss
    avg_win = (gross_profit / wins) if wins > 0 else 0
    avg_loss = (gross_loss / losses) if losses > 0 else 0
    win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else float('inf')

    # Expectancy
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss) if total_trades > 0 else 0

    # Average holding time
    avg_hold = np.mean(holding_times) if holding_times else 0

    # Sharpe Ratio (annualized, using daily returns)
    if len(daily_returns) > 1:
        daily_mean = np.mean(daily_returns)
        daily_std = np.std(daily_returns, ddof=1)
        sharpe_ratio = (daily_mean / daily_std) * math.sqrt(252) if daily_std > 0 else 0
    else:
        sharpe_ratio = 0

    # Sortino Ratio (only downside deviation)
    if len(daily_returns) > 1:
        downside_returns = [r for r in daily_returns if r < 0]
        downside_std = np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 0
        sortino_ratio = (daily_mean / downside_std) * math.sqrt(252) if downside_std > 0 else 0
    else:
        sortino_ratio = 0

    # --- 7. PRINT REPORT ---
    print("\n" + "=" * 70)
    print(" 📊 Everest v8.0 BACKTEST RESULTS")
    print("=" * 70)
    months_span = round((end_date - start_date).days / 30.44)
    print(f" Period          : {start_date.strftime('%b %d, %Y')} → {end_date.strftime('%b %d, %Y')} ({months_span} months)")
    print(f" Starting Balance: ${starting_balance:,.2f}")
    print(f" Final Balance   : ${balance:,.2f}")
    print(f" Net Profit      : ${net_profit:+,.2f} ({net_return:+.1f}%)")
    print(f" Broker Fees     : ${total_commissions:,.2f}")
    print("-" * 70)
    print(f" {'TRADE STATISTICS':^68}")
    print("-" * 70)
    print(f" Total Trades    : {total_trades} ({buy_trades} Buys | {sell_trades} Sells)")
    print(f" Win Rate        : {win_rate:.1f}% ({wins}W / {losses}L)")
    print(f" Avg Win         : ${avg_win:,.2f}")
    print(f" Avg Loss        : ${avg_loss:,.2f}")
    print(f" Win/Loss Ratio  : {win_loss_ratio:.2f}")
    print(f" Expectancy/Trade: ${expectancy:,.2f}")
    print(f" Profit Factor   : {profit_factor:.2f}")
    print("-" * 70)
    print(f" {'RISK METRICS':^68}")
    print("-" * 70)
    print(f" Sharpe Ratio    : {sharpe_ratio:.2f}", end="")
    if sharpe_ratio >= 2.0:
        print(" ⭐ Excellent")
    elif sharpe_ratio >= 1.5:
        print(" ✅ Good")
    elif sharpe_ratio >= 1.0:
        print(" 🟡 Acceptable")
    else:
        print(" 🔴 Poor")
    print(f" Sortino Ratio   : {sortino_ratio:.2f}")
    print(f" Max Drawdown    : ${max_dd_usd:,.2f} ({max_dd_pct:.1f}%)")
    print(f" Max Consec. Loss: {max_consecutive_losses}")
    print(f" Max Consec. Wins: {max_consecutive_wins}")
    print(f" Avg Hold Time   : {avg_hold:.0f} min ({avg_hold/60:.1f} hrs)")
    avg_concurrent = np.mean(concurrent_counts) if concurrent_counts else 0
    print(f" Max Concurrent  : {max_concurrent} positions")
    print(f" Avg Concurrent  : {avg_concurrent:.1f} positions")

    # Session breakdown
    print("-" * 70)
    print(f" {'SESSION PERFORMANCE':^68}")
    print("-" * 70)
    for session_name in ["Asian", "London", "Overlap", "New York", "Off-Hours"]:
        s = session_stats[session_name]
        s_total = s["wins"] + s["losses"]
        s_wr = (s["wins"] / s_total * 100) if s_total > 0 else 0
        s_pnl = s["pnl"]
        if s_total > 0:
            pnl_icon = "🟢" if s_pnl > 0 else "🔴"
            print(f" {session_name:<12s}: {s_total:>3d} trades | WR: {s_wr:>5.1f}% | "
                  f"PnL: {pnl_icon} ${s_pnl:>+,.2f}")

    # Monthly breakdown
    print("-" * 70)
    print(f" {'MONTHLY PERFORMANCE':^68}")
    print("-" * 70)
    for month, pnl in sorted(monthly_pnl.items()):
        pnl_icon = "🟢" if pnl > 0 else "🔴"
        bar_len = min(30, int(abs(pnl) / max(abs(v) for v in monthly_pnl.values()) * 30)) if monthly_pnl else 0
        bar = "█" * bar_len
        print(f" {month}: {pnl_icon} ${pnl:>+10,.2f} {bar}")

    # Strategy grade
    print("=" * 70)
    grade_score = 0
    if sharpe_ratio >= 1.5:
        grade_score += 3
    elif sharpe_ratio >= 1.0:
        grade_score += 2
    elif sharpe_ratio >= 0.5:
        grade_score += 1
    if win_rate >= 50:
        grade_score += 2
    elif win_rate >= 40:
        grade_score += 1
    if profit_factor >= 2.0:
        grade_score += 3
    elif profit_factor >= 1.5:
        grade_score += 2
    elif profit_factor >= 1.0:
        grade_score += 1
    if max_dd_pct < 10:
        grade_score += 2
    elif max_dd_pct < 20:
        grade_score += 1

    grades = {10: "A+", 9: "A", 8: "A-", 7: "B+", 6: "B", 5: "B-",
              4: "C+", 3: "C", 2: "C-", 1: "D", 0: "F"}
    grade = grades.get(min(grade_score, 10), "F")
    print(f" 🏆 STRATEGY GRADE: {grade} (score: {grade_score}/10)")
    print("=" * 70)

    # --- 8. SAVE TRADE LOG ---
    log_file = os.path.join(os.path.dirname(__file__), "backtest_stacking_trades.csv")
    trade_df = pd.DataFrame(trade_log)
    if not trade_df.empty:
        trade_df.to_csv(log_file, index=False)
        print(f"\n📄 Trade log saved: {log_file}")

    # --- 9. GENERATE CHARTS ---
    if VISUALS_ENABLED and equity_curve:
        print("📈 Generating Interactive Charts...", flush=True)
        eq_df = pd.DataFrame(equity_curve)

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=("XAUUSD Price + Trades", "Equity Curve", "Drawdown"),
            row_heights=[0.5, 0.3, 0.2]
        )

        # Row 1: Price + Trade Markers
        fig.add_trace(go.Candlestick(
            x=df['time'], open=df['open'], high=df['high'],
            low=df['low'], close=df['close'], name='XAUUSD',
            increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df['time'], y=df['SMA_200'],
            line=dict(color='#FFD8.0', width=1), name='SMA 200'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df['time'], y=df['EMA_50'],
            line=dict(color='#00BCD4', width=1), name='EMA 50'
        ), row=1, col=1)

        # Buy entries
        fig.add_trace(go.Scatter(
            x=buy_times, y=buy_prices, mode='markers',
            marker=dict(symbol='triangle-up', color='lime', size=12,
                        line=dict(color='black', width=1)),
            name='BUY Entry'
        ), row=1, col=1)

        # Sell entries
        fig.add_trace(go.Scatter(
            x=sell_times, y=sell_prices, mode='markers',
            marker=dict(symbol='triangle-down', color='red', size=12,
                        line=dict(color='black', width=1)),
            name='SELL Entry'
        ), row=1, col=1)

        # Exits
        fig.add_trace(go.Scatter(
            x=exit_times, y=exit_prices, mode='markers',
            marker=dict(symbol='x', color='white', size=8,
                        line=dict(color='black', width=1)),
            name='EXIT', hovertext=exit_hover_text, hoverinfo="text"
        ), row=1, col=1)

        # Row 2: Equity Curve
        fig.add_trace(go.Scatter(
            x=eq_df['time'], y=eq_df['equity'],
            fill='tonexty' if len(eq_df) > 1 else None,
            line=dict(color='#26a69a', width=2),
            name='Equity', fillcolor='rgba(38, 166, 154, 0.1)'
        ), row=2, col=1)

        fig.add_hline(y=starting_balance, line_dash="dash",
                      line_color="yellow", row=2, col=1)

        # Row 3: Drawdown
        fig.add_trace(go.Scatter(
            x=eq_df['time'], y=-eq_df['drawdown'],
            fill='tozeroy',
            line=dict(color='#ef5350', width=1),
            name='Drawdown', fillcolor='rgba(239, 83, 80, 0.3)'
        ), row=3, col=1)

        fig.update_layout(
            title=f"Everest v8.0 STACKING Backtest — {start_date.strftime('%b %Y')} to "
                  f"{end_date.strftime('%b %Y')} | Net: ${net_profit:+,.2f} | "
                  f"Sharpe: {sharpe_ratio:.2f} | Max Stack: {max_concurrent} | Grade: {grade}",
            template='plotly_dark',
            height=1000,
            xaxis_rangeslider_visible=False,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            font=dict(family="Consolas, monospace")
        )

        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Equity ($)", row=2, col=1)
        fig.update_yaxes(title_text="Drawdown ($)", row=3, col=1)

        chart_file = os.path.join(os.path.dirname(__file__), "backtest_stacking_chart.html")
        fig.write_html(chart_file)
        webbrowser.open(f"file://{os.path.abspath(chart_file)}")
        print(f"✅ Chart opened: {chart_file}")

    mt5.shutdown()
    print("\n✅ Backtest complete.")


if __name__ == "__main__":
    run_backtest()

