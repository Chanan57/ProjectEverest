"""
Everest v8.0 — Main Orchestrator
Multi-Modal Intelligence Trading Engine
Combines: Technical Analysis + ML Ensemble + Social Sentiment + News + Macro Awareness

Architecture:
  - Signal generation → every 30 minutes (with intelligence refresh)
  - Risk monitoring → every 5 seconds (exits only)
  - Intelligence refresh → every 15 minutes (background thread)
"""
import sys
import io
import time
import threading
import subprocess
from datetime import datetime, timedelta
import pandas as pd
import MetaTrader5 as mt5

# --- IMPORT CORE MODULES ---
from config import *
import logger
import data_engine
import ai_oracle
import risk_manager
import execution
import news_filter
from market_hours import is_market_open
from telegram_notifier import send_telegram_alert

# --- IMPORT v8.0 INTELLIGENCE MODULES ---
import sentiment_engine
import news_intelligence
import macro_engine
import intelligence_aggregator
from cache_manager import cache

# --- IMPORT GUARDIAN (Self-Discipline System) ---
import guardian

# --- 0. WINDOWS CONSOLE FIX ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- Thread-safe intelligence state ---
_intel_lock = threading.Lock()
_intel_data = {
    "sentiment": None,
    "news": None,
    "macro": None,
    "last_refresh": None
}


def _refresh_intelligence(adx=None, atr=None):
    """
    Fetch all intelligence data. Runs in a background thread to avoid
    blocking the main trading loop. Each engine uses its own cache TTL,
    so redundant API calls are avoided automatically.
    """
    global _intel_data
    try:
        sent = sentiment_engine.get_sentiment()
        news = news_intelligence.get_news_analysis()
        macro = macro_engine.get_macro_regime(
            sentiment_data=sent,
            news_data=news,
            adx=adx,
            atr=atr
        )

        with _intel_lock:
            _intel_data["sentiment"] = sent
            _intel_data["news"] = news
            _intel_data["macro"] = macro
            _intel_data["last_refresh"] = datetime.now()

    except Exception as e:
        print(f"⚠️ [INTEL] Background refresh error: {e}", flush=True)


def _get_intel():
    """Thread-safe getter for intelligence data."""
    with _intel_lock:
        return (
            _intel_data["sentiment"],
            _intel_data["news"],
            _intel_data["macro"]
        )


# --- 1. STARTUP ---
if not mt5.initialize():
    print("❌ MT5 Startup Failed.", flush=True)
    sys.exit()

if not mt5.symbol_select(SYMBOL, True):
    print(f"❌ Failed to select {SYMBOL}.", flush=True)
    SYMBOL = "XAUUSD"
    mt5.symbol_select(SYMBOL, True)

# --- START GUARDIAN (Self-Discipline Enforcer) ---
guardian.start_guardian()

# --- STARTUP ALERTS ---
send_telegram_alert(
    "🟢 <b>Everest v8.0 ONLINE</b>\n"
    "Multi-Modal Intelligence Engine started.\n"
    "• Technical + ML Ensemble + Sentiment + News + Macro\n"
    f"• Symbol: {SYMBOL} | TF: M30\n"
    f"• AI: RF + GBC Ensemble: {'ON' if ENSEMBLE_ENABLED else 'OFF'}\n"
    f"• Risk Cap: {MAX_RISK_PERCENT_CAP:.0%} of balance\n"
    f"• Sentiment Mode: {SENTIMENT_MODE}\n"
    "• 🛡️ Guardian: ACTIVE (manual trades will be auto-closed)"
)

# --- Initial intelligence fetch (blocking on first run) ---
print("\n🌐 [INTEL] Performing initial intelligence sweep...", flush=True)
_refresh_intelligence()
print("✅ [INTEL] Initial intelligence loaded.\n", flush=True)


# --- 2. THE PIPELINE (CORE LOGIC) ---
def run_pipeline(model_pack, predictors, is_new_candle=True):
    """The master sequence: Gather → Predict → Enrich → Decide → Execute → Log"""
    tick = mt5.symbol_info_tick(SYMBOL)
    symbol_info = mt5.symbol_info(SYMBOL)
    acc = mt5.account_info()
    if not tick or not symbol_info or not acc:
        return

    # A. GATHER DATA
    spread_points = (tick.ask - tick.bid) / symbol_info.point
    live_rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 300)
    if live_rates is None:
        return

    live_df = data_engine.prepare_data(
        pd.DataFrame(live_rates).assign(time=lambda x: pd.to_datetime(x['time'], unit='s'))
    )
    last_row = live_df.iloc[-1]

    # B. AI PREDICTION (v8.0 Ensemble)
    prob_up = ai_oracle.predict_proba(model_pack, pd.DataFrame([last_row]))
    prob_down = 1 - prob_up

    # C. MARKET STATE
    price = last_row['close']
    sma, ema, adx = last_row['SMA_200'], last_row['EMA_50'], last_row['ADX']
    rsi, atr = last_row['RSI'], last_row['ATR']
    trend_up = (price > sma) and (price > ema)
    trend_down = (price < sma) and (price < ema)
    trend_status = "✅ BULLISH" if trend_up else "✅ BEARISH" if trend_down else "⚠️ MIXED"

    pos_obj = mt5.positions_get(symbol=SYMBOL)
    num_positions = len(pos_obj) if pos_obj else 0
    current_pos = (
        "BUY" if (pos_obj and pos_obj[0].type == mt5.ORDER_TYPE_BUY)
        else "SELL" if pos_obj
        else None
    )

    signal = None
    decision_text = "WAITING"
    risk_warning = ""

    # D. FETCH INTELLIGENCE DATA (thread-safe read)
    sentiment_data, news_data, macro_data = _get_intel()

    # Enhanced AI reasoning
    brain_reason, detailed_reason = ai_oracle.get_enhanced_reason(
        prob_up, prob_down, rsi, last_row['dist_ema50'], atr, adx,
        sentiment_data, news_data, macro_data
    )

    # E. THE v8.0 STRATEGY LOGIC (Stacking-aware)
    is_embargo, news_title = news_filter.is_news_embargo()

    # Check macro Do-Not-Trade
    do_not_trade = macro_data.get("do_not_trade", False) if macro_data else False

    conviction_result = None

    # --- STEP 1: EXIT CHECK for all open positions ---
    if num_positions > 0:
        # Check if AI reversal conditions are met for existing positions
        if current_pos == "BUY" and prob_down > CONFIDENCE_REVERSAL and price < ema:
            signal = "CLOSE"
            decision_text = f"CONFIRMED EXIT (AI Fear + Trend Break) [{num_positions} pos]"
        elif current_pos == "SELL" and prob_up > CONFIDENCE_REVERSAL and price > ema:
            signal = "CLOSE"
            decision_text = f"CONFIRMED EXIT (AI Fear + Trend Break) [{num_positions} pos]"

    # --- STEP 2: ENTRY CHECK (stacking allowed up to MAX_CONCURRENT_POSITIONS) ---
    if signal != "CLOSE":
        # v8.0: GUARDIAN CHECK — Is trading allowed?
        guardian_ok, guardian_reason = guardian.is_trading_allowed()
        if not guardian_ok:
            decision_text = f"🛡️ GUARDIAN BLOCK: {guardian_reason[:50]}"
        elif do_not_trade:
            decision_text = f"⛔ BLOCKED (Macro DNT: {macro_data.get('market_regime', '?')})"
        elif is_embargo:
            decision_text = f"⛔ BLOCKED (News Embargo: {news_title})"
        elif adx < ADX_THRESHOLD:
            decision_text = f"WAITING (Choppy: ADX {adx:.1f} < {ADX_THRESHOLD})"
        elif num_positions > 0:
            # We have positions but no exit signal — manage and look for stack opportunities
            decision_text = f"MANAGING {num_positions} POSITION(S) ({current_pos})"

            # Allow stacking in same direction if under limit
            if num_positions < guardian.MAX_CONCURRENT_POSITIONS:
                if prob_up > CONFIDENCE_ENTRY and trend_up and current_pos == "BUY" and last_row['RSI'] < 70:
                    signal = "BUY"
                    decision_text = f"STACK BUY #{num_positions + 1}"
                elif prob_down > CONFIDENCE_ENTRY and trend_down and current_pos == "SELL" and last_row['RSI'] > 30:
                    signal = "SELL"
                    decision_text = f"STACK SELL #{num_positions + 1}"
        else:
            # No positions — standard entry logic
            if prob_up > CONFIDENCE_ENTRY and trend_up:
                if last_row['RSI'] < 70:
                    signal = "BUY"
                    decision_text = "SNIPER BUY SIGNAL"
                else:
                    decision_text = "WAITING (Overbought)"
            elif prob_down > CONFIDENCE_ENTRY and trend_down:
                if last_row['RSI'] > 30:
                    signal = "SELL"
                    decision_text = "SNIPER SELL SIGNAL"
                else:
                    decision_text = "WAITING (Oversold)"
            else:
                decision_text = f"HUNTING... (Conf: {max(prob_up, prob_down):.2f})"

        # v8.0: CONVICTION CHECK before executing new entries
        if signal and signal != "CLOSE":
            conviction_result = intelligence_aggregator.compute_conviction(
                signal=signal,
                prob_up=prob_up,
                prob_down=prob_down,
                trend_up=trend_up,
                trend_down=trend_down,
                sentiment_data=sentiment_data,
                news_data=news_data,
                macro_data=macro_data
            )

            if not conviction_result["should_trade"]:
                reasons = ", ".join(conviction_result["block_reasons"])
                decision_text = f"⛔ INTEL BLOCK ({reasons})"
                signal = None  # Cancel the signal

    # F. EXECUTION & RISK
    if signal == "CLOSE":
        if current_pos:
            execution.close_all("Confirmed_Reversal_Exit")
            send_telegram_alert(
                f"🔄 <b>ALL POSITIONS CLOSED</b>\n"
                f"Reason: AI Reversal Exit for {num_positions} active {current_pos} position(s)."
            )

    elif signal and signal in ("BUY", "SELL"):
        allowed_spread = (
            MAX_SPREAD_HIGH_CONF if max(prob_up, prob_down) >= HIGH_CONFIDENCE_LVL
            else MAX_SPREAD_NORMAL
        )

        if spread_points <= allowed_spread:
            sl_d = max(SL_ATR_MULT * atr, SL_MIN_DISTANCE)

            # v8.0: Pass intelligence data to risk manager
            risk_mult = conviction_result["risk_multiplier"] if conviction_result else 1.0
            alignment = conviction_result["alignment"] if conviction_result else "partial"

            vol, cash, risk_warning = risk_manager.get_lot_size(
                acc.balance, RISK_PERCENT, sl_d, symbol_info,
                risk_multiplier=risk_mult,
                alignment=alignment,
                do_not_trade=do_not_trade
            )

            if vol > 0:
                # v8.0: GUARDIAN lot size validation
                vol = guardian.validate_lot_size(vol)

                p = tick.ask if signal == "BUY" else tick.bid
                sl = p - sl_d if signal == "BUY" else p + sl_d
                tp = p + (TP_RATIO * sl_d) if signal == "BUY" else p - (TP_RATIO * sl_d)

                execution.open_trade(signal, p, sl, tp, vol, max(prob_up, prob_down))

                # v8.0: Enhanced trade log
                conviction_val = conviction_result["conviction"] if conviction_result else 0.0
                regime_name = macro_data.get("market_regime", "n/a") if macro_data else "n/a"

                logger.log_trade_v8(
                    signal, SYMBOL, p, sl, tp, vol,
                    f"Entry AI:{max(prob_up, prob_down):.2f}",
                    conviction=conviction_val,
                    alignment=alignment,
                    regime=regime_name
                )

                # v8.0: Enriched Telegram alert
                actual_risk_usd = vol * symbol_info.trade_contract_size * sl_d
                risk_pct_actual = (actual_risk_usd / acc.balance) * 100
                stack_label = f" [Stack #{num_positions + 1}]" if num_positions > 0 else ""

                alert_msg = (
                    f"🚀 <b>NEW {signal} EXECUTED{stack_label}</b>\n"
                    f"Symbol: {SYMBOL}\n"
                    f"Entry Price: {p:.2f}\n"
                    f"Lot Size: {vol}\n"
                    f"Risk: ~${actual_risk_usd:.2f} ({risk_pct_actual:.1f}%)\n"
                    f"───────────\n"
                    f"⚡ Conviction: {conviction_val:.0%} ({alignment})\n"
                    f"🌍 Regime: {regime_name}\n"
                    f"📱 Sentiment: {sentiment_data.get('bias', 'n/a') if sentiment_data else 'n/a'}\n"
                    f"📰 News: {news_data.get('overall_bias', 'n/a') if news_data else 'n/a'}"
                )
                send_telegram_alert(alert_msg)
            else:
                decision_text = f"SKIPPED ({risk_warning})"
        else:
            decision_text = f"BLOCKED (Spread {spread_points:.1f})"

    # G. PRINT DASHBOARD & LOGS
    if is_new_candle or signal:
        conviction_summary = None
        if conviction_result:
            conviction_summary = intelligence_aggregator.format_conviction_summary(conviction_result)

        logger.print_log_block(
            datetime.now(), tick.ask, spread_points, acc.balance, acc.equity,
            prob_up, prob_down, brain_reason, trend_status, rsi, atr, adx,
            decision_text, risk_warning,
            sentiment_data=sentiment_data,
            news_data=news_data,
            macro_data=macro_data,
            conviction_summary=conviction_summary
        )
        logger.log_brain_activity(
            datetime.now(), tick.ask, prob_up, prob_down, brain_reason,
            trend_status, rsi, atr, adx, spread_points, decision_text
        )


# --- 3. MASTER LOOP ---
model_pack, predictors = ai_oracle.train_model()
if model_pack is None:
    sys.exit()

print("\n✅ Everest v8.0 MULTI-MODAL INTELLIGENCE ENGINE INITIALIZED.", flush=True)
print("   - Technical Analysis: RSI, ADX, SMA200, EMA50, ATR, MACD, Bollinger, Stochastic")
print(f"   - Machine Learning: {'RF + GBC Ensemble' if ENSEMBLE_ENABLED else 'RandomForest'} "
      f"({len(predictors)} features)")
print("   - Social Sentiment: Reddit (VADER NLP)")
print("   - News Intelligence: NewsAPI + RSS (NLP + Event Detection)")
print("   - Macro Narrative: Market Regime Classification")
print("   - Fundamental Shield: Forex Factory News Embargo")
print(f"   - Risk Cap: {MAX_RISK_PERCENT_CAP:.0%} of balance")
print("   - Guardian: 🛡️ ACTIVE (manual trades auto-closed)")
print("   - Exits: High-Frequency 5-Second Active Monitoring")

# Launch the Absolute OS Lockout Kiosk
try:
    subprocess.Popen([sys.executable, "kiosk.py"])
    print("   - OS Lockout: 🛡️ KIOSK MODE ACTIVE (Screen locked during market hours)")
except Exception as e:
    print(f"   - OS Lockout: ❌ Error starting Kiosk: {e}")

print("⏳ Waiting for next candle to print full analysis...\n", flush=True)

rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 1)
last_candle_time = rates[0]['time'] if rates is not None else 0
last_day = datetime.now().day

# --- Heartbeat & Intelligence Refresh Timers ---
heartbeat_interval_hours = 4
last_heartbeat_time = datetime.now()
intel_refresh_interval = timedelta(minutes=15)
last_intel_refresh = datetime.now()

# Force first pipeline run
run_pipeline(model_pack, predictors, is_new_candle=True)

def _write_heartbeat():
    """Write the kiosk heartbeat file so the Kiosk knows we're alive."""
    try:
        with open("kiosk_heartbeat.tmp", "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

# Seed the very first heartbeat before the loop begins
_write_heartbeat()

while True:
    try:
        # Heartbeat at TOP of loop: proves we entered a new iteration
        _write_heartbeat()
        now = datetime.now()

        # --- INTELLIGENCE REFRESH (every 15 min, background thread) ---
        if (now - last_intel_refresh) >= intel_refresh_interval:
            _adx, _atr = None, None
            try:
                _rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 300)
                if _rates is not None:
                    _df = data_engine.prepare_data(
                        pd.DataFrame(_rates).assign(
                            time=lambda x: pd.to_datetime(x['time'], unit='s')
                        )
                    )
                    _adx = _df.iloc[-1]['ADX']
                    _atr = _df.iloc[-1]['ATR']
            except Exception:
                pass

            thread = threading.Thread(
                target=_refresh_intelligence,
                args=(_adx, _atr),
                daemon=True
            )
            thread.start()
            last_intel_refresh = now

        # --- TELEGRAM 4-HOUR HEARTBEAT ---
        if (now - last_heartbeat_time) >= timedelta(hours=heartbeat_interval_hours):
            account_info = mt5.account_info()
            sentiment_data, news_data, macro_data = _get_intel()

            if account_info:
                regime_str = macro_data.get("market_regime", "n/a").upper() if macro_data else "n/a"
                sent_str = sentiment_data.get("bias", "n/a") if sentiment_data else "n/a"
                news_str = news_data.get("overall_bias", "n/a") if news_data else "n/a"

                guardian_status = guardian.get_guardian_summary()

                msg = (
                    f"⏱️ <b>Everest v8.0 Status Report</b>\n"
                    f"Status: Operational & Scanning\n"
                    f"Guardian: Active - System Secured\n"
                    f"No manual intervention permitted."
                )
                send_telegram_alert(msg)
            last_heartbeat_time = now

        # Periodic AI Retraining
        if now.day != last_day and now.hour == 9:
            model_pack, predictors = ai_oracle.train_model()
            last_day = now.day

            thread = threading.Thread(
                target=_refresh_intelligence,
                daemon=True
            )
            thread.start()

        # 1. Check if we currently hold an open trade
        pos_obj = mt5.positions_get(symbol=SYMBOL)
        in_trade = pos_obj is not None and len(pos_obj) > 0

        # 2. Check if a brand new 30-minute candle just opened
        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 1)
        is_new_candle = (
            rates is not None and len(rates) > 0
            and rates[0]['time'] != last_candle_time
        )

        # 3. The Dual-Frequency Routing
        if is_new_candle:
            last_candle_time = rates[0]['time']
            run_pipeline(model_pack, predictors, is_new_candle=True)

        elif in_trade:
            run_pipeline(model_pack, predictors, is_new_candle=False)

        # Heartbeat at BOTTOM of loop: proves we completed the iteration
        _write_heartbeat()

        # The Institutional Heartbeat (5-second pause)
        time.sleep(5)

    except Exception as e:
        print(f"⚠️ Master Loop Error: {e}", flush=True)
        time.sleep(10)
    except KeyboardInterrupt:
        # Check if we should bypass the ritual (Market is Closed / Weekend)
        if not is_market_open():
            print(f"\n{'='*70}")
            print(f"🌲 [CLEAN WEEKEND SHUTDOWN] 🌲")
            print(f"Market is closed. Everest v8.0 is standing down safely.")
            print(f"{'='*70}\n")
            break

        import time as timer_lib
        print(f"\n{'='*70}")
        print(f"🚨 🛑 MANUAL EXIT BLOCKED 🛑 🚨")
        print(f"{'-' * 70}")
        print(f"You pressed Ctrl+C to close the automated system.")
        print(f"Are you shutting this down to manually trade? If so, you are relapsing.")
        print(f"\nTo exit the bot, you MUST naturally type the following sentence EXACTLY:")
        expected_sentence = "I acknowledge that I am prone to emotional decision-making. By attempting to intervene, I am actively sabotaging my statistical edge. I have previously blown up accounts because I lacked the discipline to let the probabilities play out. If I shut this engine down now, I am surrendering to fear and I accept that I am a loser."
        
        # Displaying it with brackets so it's annoying to double-click copy just the string
        print(f"\n> [ {expected_sentence} ] <\n")
        
        start_time = timer_lib.time()
        user_input = input(">> ")
        elapsed = timer_lib.time() - start_time
        
        if user_input.strip() == expected_sentence:
            if elapsed < 35.0:
                print(f"\n❌ REJECTED. You solved that in {elapsed:.1f} seconds.")
                print(f"   You definitely copy-pasted that. You must PHYSICALLY TYPE IT to rewire your brain.")
                print(f"   Resuming automated system... KEEP YOUR HANDS OFF THE MOUSE.")
                print(f"{'='*70}\n")
            else:
                print(f"\nAcknowledged. Shutting down Everest v8.0 safely...")
                break
        else:
            print(f"\n❌ Incorrect validation. You do not have permission to leave.")
            print(f"   Resuming automated system... KEEP YOUR HANDS OFF THE MOUSE.")
            print(f"{'='*70}\n")
