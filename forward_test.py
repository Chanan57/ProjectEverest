"""
Everest v8.0 — Forward Tester (Paper Trading Mode)
Runs the full v8.0 pipeline but simulates trades without sending real MT5 orders.
Logs every decision (entries, exits, blocks, conviction scores) to CSV.
Sends Telegram alerts marked as [PAPER].
Can run alongside the live bot for A/B comparison.

Usage: python forward_test.py
"""
import sys
import io
import os
import csv
import time
import threading
from datetime import datetime, timedelta
import pandas as pd
import MetaTrader5 as mt5

# --- IMPORT CORE MODULES ---
from config import *
import data_engine
import ai_oracle
import news_filter
from telegram_notifier import send_telegram_alert

# --- IMPORT v8.0 INTELLIGENCE MODULES ---
import sentiment_engine
import news_intelligence
import macro_engine
import intelligence_aggregator
from cache_manager import cache

# --- 0. WINDOWS CONSOLE FIX ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ======================================================================
#  PAPER TRADING STATE
# ======================================================================
paper_balance = 1000.00         # Starting paper balance ($1K realistic)
paper_peak = paper_balance
paper_positions = []            # List of dicts: {type, entry, sl, tp, lots, time}
paper_trades = []
paper_wins = 0
paper_losses = 0

LOG_FILE = os.path.join(os.path.dirname(__file__), "forward_test_log.csv")

# Thread-safe intelligence state
_intel_lock = threading.Lock()
_intel_data = {"sentiment": None, "news": None, "macro": None, "last_refresh": None}


def _refresh_intelligence(adx=None, atr=None):
    global _intel_data
    try:
        sent = sentiment_engine.get_sentiment()
        news = news_intelligence.get_news_analysis()
        macro = macro_engine.get_macro_regime(sentiment_data=sent, news_data=news, adx=adx, atr=atr)
        with _intel_lock:
            _intel_data["sentiment"] = sent
            _intel_data["news"] = news
            _intel_data["macro"] = macro
            _intel_data["last_refresh"] = datetime.now()
    except Exception as e:
        print(f"⚠️ [PAPER-INTEL] Refresh error: {e}", flush=True)


def _get_intel():
    with _intel_lock:
        return _intel_data["sentiment"], _intel_data["news"], _intel_data["macro"]


def _log_decision(timestamp, price, signal, decision, conviction, alignment,
                   regime, prob_up, prob_down, adx, rsi, atr, balance,
                   num_pos, pnl=0.0, exit_reason=""):
    """Log every decision to CSV for analysis."""
    try:
        file_exists = os.path.isfile(LOG_FILE)
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "Price", "Signal", "Decision", "Conviction",
                    "Alignment", "Regime", "Prob_Up", "Prob_Down", "ADX", "RSI",
                    "ATR", "Balance", "Open_Pos", "PnL", "Exit_Reason"
                ])
            writer.writerow([
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                f"{price:.2f}", signal or "", decision,
                f"{conviction:.4f}" if conviction else "",
                alignment or "", regime or "",
                f"{prob_up:.4f}", f"{prob_down:.4f}",
                f"{adx:.1f}", f"{rsi:.1f}", f"{atr:.2f}",
                f"{balance:.2f}", num_pos,
                f"{pnl:+.2f}" if pnl != 0 else "", exit_reason
            ])
    except Exception:
        pass


def paper_open(signal, price, sl_dist, lots, conviction, alignment, regime):
    """Simulate opening a trade (supporting stacking)."""
    global paper_positions

    sl = price - sl_dist if signal == "BUY" else price + sl_dist
    tp = price + (TP_RATIO * sl_dist) if signal == "BUY" else price - (TP_RATIO * sl_dist)

    trade = {
        "type": signal,
        "entry": price,
        "sl": sl,
        "tp": tp,
        "lots": lots,
        "time": datetime.now()
    }
    paper_positions.append(trade)

    risk_usd = lots * 100 * sl_dist
    stack_label = f" [Stack #{len(paper_positions)}]" if len(paper_positions) > 1 else ""

    print(f"\n📝 [PAPER] {'🟢 BUY' if signal == 'BUY' else '🔴 SELL'}{stack_label} @ {price:.2f} | "
          f"Lots: {lots} | Risk: ${risk_usd:.2f}", flush=True)
    print(f"   SL: {sl:.2f} | TP: {tp:.2f} | "
          f"Conv: {conviction:.0%} ({alignment}) | Regime: {regime}", flush=True)

    send_telegram_alert(
        f"📝 <b>[PAPER] NEW {signal}{stack_label}</b>\n"
        f"Price: {price:.2f}\n"
        f"Lots: {lots} | Risk: ~${risk_usd:.2f}\n"
        f"Conviction: {conviction:.0%} ({alignment})\n"
        f"Regime: {regime}"
    )


def paper_close_all(exit_price, reason):
    """Simulate closing all trades simultaneously."""
    global paper_positions, paper_balance, paper_peak
    global paper_wins, paper_losses

    total_net_pnl = 0.0
    num_closed = len(paper_positions)
    if num_closed == 0: return 0.0, None

    trade_type = paper_positions[0]["type"]
    contract_size = 100

    for trade in paper_positions:
        if trade["type"] == "BUY":
            pnl = (exit_price - trade["entry"]) * trade["lots"] * contract_size
        else:
            pnl = (trade["entry"] - exit_price) * trade["lots"] * contract_size

        commission = trade["lots"] * 8.00
        net_pnl = pnl - commission
        total_net_pnl += net_pnl

        if net_pnl > 0: paper_wins += 1
        else: paper_losses += 1

        paper_trades.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": trade["type"], "entry": trade["entry"], "exit": exit_price,
            "lots": trade["lots"], "pnl": round(net_pnl, 2), "reason": reason,
            "balance": round(paper_balance + total_net_pnl, 2),
            "hold_min": round((datetime.now() - trade["time"]).total_seconds() / 60, 1)
        })

    paper_balance += total_net_pnl
    if paper_balance > paper_peak: paper_peak = paper_balance

    total = paper_wins + paper_losses
    wr = (paper_wins / total * 100) if total > 0 else 0
    icon = "🟢" if total_net_pnl > 0 else "🔴"

    print(f"\n{icon} [PAPER] CLOSED {num_closed} POSITIONS | {reason} | "
          f"Total PnL: ${total_net_pnl:+.2f} | Bal: ${paper_balance:,.2f} | "
          f"WR: {wr:.0f}% ({paper_wins}W/{paper_losses}L)", flush=True)

    send_telegram_alert(
        f"{icon} <b>[PAPER] CLOSED ALL {trade_type}S</b>\n"
        f"Count: {num_closed}\n"
        f"Reason: {reason}\n"
        f"Total PnL: ${total_net_pnl:+.2f}\n"
        f"Balance: ${paper_balance:,.2f}\n"
        f"Win Rate: {wr:.0f}% ({total} trades)"
    )

    paper_positions = []
    return total_net_pnl, trade_type


def run_paper_pipeline(model_pack, predictors, is_new_candle=True):
    """Paper trading pipeline (v8.0 Stacking-aware)."""
    global paper_positions, paper_balance

    tick = mt5.symbol_info_tick(SYMBOL)
    symbol_info = mt5.symbol_info(SYMBOL)
    if not tick or not symbol_info: return

    live_rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 300)
    if live_rates is None: return

    live_df = data_engine.prepare_data(
        pd.DataFrame(live_rates).assign(time=lambda x: pd.to_datetime(x['time'], unit='s'))
    )
    last_row = live_df.iloc[-1]
    price = last_row['close']
    sma, ema, adx = last_row['SMA_200'], last_row['EMA_50'], last_row['ADX']
    rsi, atr = last_row['RSI'], last_row['ATR']
    trend_up = (price > sma) and (price > ema)
    trend_down = (price < sma) and (price < ema)

    prob_up = ai_oracle.predict_proba(model_pack, pd.DataFrame([last_row]))
    prob_down = 1 - prob_up

    sentiment_data, news_data, macro_data = _get_intel()
    regime_name = macro_data.get("market_regime", "n/a") if macro_data else "n/a"
    do_not_trade = macro_data.get("do_not_trade", False) if macro_data else False

    num_positions = len(paper_positions)
    current_pos_type = paper_positions[0]["type"] if num_positions > 0 else None

    signal = None
    decision = "WATCHING"
    conviction_val = 0.0
    alignment = ""

    # --- STEP 1: EXIT CHECK (for all open positions) ---
    if num_positions > 0:
        current_price = tick.ask if current_pos_type == "SELL" else tick.bid
        exit_triggered = False
        exit_reason = ""
        exit_price = 0.0

        # Check SL/TP for EACH position
        for trade in paper_positions:
            if trade["type"] == "BUY":
                if current_price <= trade["sl"]:
                    exit_triggered, exit_reason, exit_price = True, "SL Hit", trade["sl"]
                    break
                elif current_price >= trade["tp"]:
                    exit_triggered, exit_reason, exit_price = True, "TP Hit", trade["tp"]
                    break
            else:
                if current_price >= trade["sl"]:
                    exit_triggered, exit_reason, exit_price = True, "SL Hit", trade["sl"]
                    break
                elif current_price <= trade["tp"]:
                    exit_triggered, exit_reason, exit_price = True, "TP Hit", trade["tp"]
                    break

        # Check AI Reversal (closes entire stack)
        if not exit_triggered:
            if current_pos_type == "BUY" and prob_down > CONFIDENCE_REVERSAL and price < ema:
                exit_triggered, exit_reason, exit_price = True, "AI Reversal", price
            elif current_pos_type == "SELL" and prob_up > CONFIDENCE_REVERSAL and price > ema:
                exit_triggered, exit_reason, exit_price = True, "AI Reversal", price

        if exit_triggered:
            pnl, _ = paper_close_all(exit_price, exit_reason)
            _log_decision(datetime.now(), exit_price, "CLOSE", exit_reason, 0, "",
                          regime_name, prob_up, prob_down, adx, rsi, atr,
                          paper_balance, 0, pnl, exit_reason)
            return

    # --- STEP 2: ENTRY / STACK CHECK ---
    is_embargo, news_title = news_filter.is_news_embargo()
    guardian_ok = (paper_balance > 0) # Placeholder for paper guardian

    if do_not_trade: decision = f"BLOCKED (Macro DNT)"
    elif is_embargo: decision = f"BLOCKED (Embargo: {news_title})"
    elif adx < ADX_THRESHOLD: decision = f"WAITING (ADX {adx:.1f})"
    elif num_positions >= 3: decision = f"MAX STACK (3 reached)"
    else:
        # Strategy Logic
        if num_positions == 0:
            if prob_up > CONFIDENCE_ENTRY and trend_up and rsi < 70: signal = "BUY"
            elif prob_down > CONFIDENCE_ENTRY and trend_down and rsi > 30: signal = "SELL"
        else:
            # Stacking Logic (same direction only)
            if current_pos_type == "BUY" and prob_up > CONFIDENCE_ENTRY and trend_up and rsi < 70: signal = "BUY"
            elif current_pos_type == "SELL" and prob_down > CONFIDENCE_ENTRY and trend_down and rsi > 30: signal = "SELL"

        if signal:
            conv = intelligence_aggregator.compute_conviction(
                signal=signal, prob_up=prob_up, prob_down=prob_down,
                trend_up=trend_up, trend_down=trend_down,
                sentiment_data=sentiment_data, news_data=news_data,
                macro_data=macro_data
            )
            conviction_val = conv["conviction"]
            alignment = conv["alignment"]

            if not conv["should_trade"]:
                reasons = ", ".join(conv["block_reasons"])
                decision = f"INTEL BLOCK ({reasons})"
                signal = None
            else:
                sl_dist = max(SL_ATR_MULT * atr, SL_MIN_DISTANCE)
                max_risk_usd = paper_balance * MAX_RISK_PERCENT_CAP
                risk_cash = paper_balance * RISK_PERCENT
                risk_mult = conv["risk_multiplier"]
                eff_mult = max(0.25, min(1.50, risk_mult))
                adjusted_risk = risk_cash * eff_mult

                lots = round(adjusted_risk / (sl_dist * 100), 2)
                if lots < 0.01: lots = 0.01

                actual_risk = lots * 100 * sl_dist
                if actual_risk > max_risk_usd:
                    lots = round(max_risk_usd / (100 * sl_dist), 2)

                if lots >= 0.01:
                    p = tick.ask if signal == "BUY" else tick.bid
                    paper_open(signal, p, sl_dist, lots,
                               conviction_val, alignment, regime_name)
                    decision = f"OPENED {signal} (Stack #{len(paper_positions)})"
                else:
                    decision = "BLOCKED (lots < 0.01)"
                    signal = None
        else:
            decision = f"HUNTING (prob: {max(prob_up, prob_down):.2f})" if num_positions == 0 else f"MANAGING {num_positions} POS"

    # Periodic Dashboard / Logging
    if is_new_candle:
        _log_decision(datetime.now(), price, signal, decision, conviction_val,
                      alignment, regime_name, prob_up, prob_down, adx, rsi, atr,
                      paper_balance, len(paper_positions))

        dd = paper_peak - paper_balance
        total = paper_wins + paper_losses
        wr = (paper_wins / total * 100) if total > 0 else 0

        print(f"\n{'─'*60}", flush=True)
        print(f" 📝 [PAPER] {datetime.now().strftime('%H:%M:%S')} | "
              f"${paper_balance:,.2f} | DD: ${dd:,.2f} | "
              f"WR: {wr:.0f}% ({total}T)", flush=True)
        print(f"    Positions: {len(paper_positions)} | ADX: {adx:.1f} | "
              f"AI: ↑{prob_up:.1%} ↓{prob_down:.1%}", flush=True)
        print(f"    Decision: {decision}", flush=True)
        print(f"{'─'*60}", flush=True)


# ======================================================================
#  MAIN LOOP
# ======================================================================
if __name__ == "__main__":
    if not mt5.initialize():
        print("❌ MT5 Failed.")
        sys.exit()

    mt5.symbol_select(SYMBOL, True)

    print("=" * 60)
    print(" 📝 Everest v8.0 FORWARD TESTER (PAPER MODE)")
    print("=" * 60)
    print(f" Starting Balance: ${paper_balance:,.2f}")
    print(f" Symbol: {SYMBOL} | Timeframe: M30")
    print(f" Log: {LOG_FILE}")
    print("=" * 60)

    send_telegram_alert(
        "📝 <b>[PAPER] Forward Tester ONLINE</b>\n"
        f"Balance: ${paper_balance:,.2f}\n"
        f"Symbol: {SYMBOL}"
    )

    # Initial intelligence sweep
    print("\n🌐 Loading intelligence...", flush=True)
    _refresh_intelligence()
    print("✅ Ready.\n", flush=True)

    # Train model
    model_pack, predictors = ai_oracle.train_model()
    if model_pack is None:
        sys.exit()

    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 1)
    last_candle_time = rates[0]['time'] if rates is not None else 0
    last_day = datetime.now().day
    last_intel_refresh = datetime.now()

    # Initial run
    run_paper_pipeline(model_pack, predictors, is_new_candle=True)

    while True:
        try:
            now = datetime.now()

            # Intelligence refresh (15 min)
            if (now - last_intel_refresh) >= timedelta(minutes=15):
                thread = threading.Thread(target=_refresh_intelligence, daemon=True)
                thread.start()
                last_intel_refresh = now

            # Daily retrain
            if now.day != last_day and now.hour == 9:
                model_pack, predictors = ai_oracle.train_model()
                last_day = now.day

            rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 1)
            is_new_candle = (
                rates is not None and len(rates) > 0
                and rates[0]['time'] != last_candle_time
            )

            if is_new_candle:
                last_candle_time = rates[0]['time']
                run_paper_pipeline(model_pack, predictors, is_new_candle=True)
            elif paper_position is not None:
                # Check SL/TP every 5 seconds when in a position
                run_paper_pipeline(model_pack, predictors, is_new_candle=False)

            time.sleep(5)

        except KeyboardInterrupt:
            print("\n\n📝 [PAPER] Shutting down...")
            total = paper_wins + paper_losses
            net = paper_balance - 10000.00
            wr = (paper_wins / total * 100) if total > 0 else 0
            print(f" Final Balance: ${paper_balance:,.2f} | Net: ${net:+,.2f}")
            print(f" Trades: {total} | WR: {wr:.0f}%")
            print(f" Log saved: {LOG_FILE}")
            break
        except Exception as e:
            print(f"⚠️ [PAPER] Error: {e}", flush=True)
            time.sleep(10)

