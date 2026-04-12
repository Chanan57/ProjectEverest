"""
Everest v9.0 — Dashboard & Logger
Enhanced dashboard with intelligence + LLM advisory columns.
Logs trades and prints the live monitoring console.
"""
import csv
import os
from datetime import datetime
import MetaTrader5 as mt5
from config import *
import psychology


def log_trade(action, symbol, price, sl, tp, volume, logic_note):
    """Logs actual trade executions to the CSV."""
    filename = "Everest_Trades_v8.csv"
    try:
        file_exists = os.path.isfile(filename)
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow([
                    "Date", "Time", "Action", "Symbol", "Price", "SL", "TP",
                    "Volume", "Balance", "Logic", "Conviction", "Alignment", "Regime"
                ])
            now = datetime.now()
            acc = mt5.account_info()
            writer.writerow([
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                action, symbol, price, sl, tp, volume,
                acc.balance, logic_note, "", "", ""
            ])
    except Exception:
        pass


def log_trade_v8(action, symbol, price, sl, tp, volume, logic_note,
                  conviction=0.0, alignment="n/a", regime="n/a"):
    """v8.0: Enhanced trade log with intelligence context."""
    filename = "Everest_Trades_v8.csv"
    try:
        file_exists = os.path.isfile(filename)
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow([
                    "Date", "Time", "Action", "Symbol", "Price", "SL", "TP",
                    "Volume", "Balance", "Logic", "Conviction", "Alignment", "Regime"
                ])
            now = datetime.now()
            acc = mt5.account_info()
            writer.writerow([
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                action, symbol, price, sl, tp, volume,
                acc.balance, logic_note,
                f"{conviction:.2f}", alignment, regime
            ])
    except Exception:
        pass


def log_brain_activity(timestamp, price, prob_up, prob_down, brain_reason,
                        trend, rsi, atr, adx, spread, decision):
    """DISABLED: We are no longer flooding the CSV with every candle's data."""
    pass


def print_log_block(timestamp, price, spread, balance, equity,
                     prob_up, prob_down, brain_reason, trend_status,
                     rsi, atr, adx, decision, risk_note="",
                     sentiment_data=None, news_data=None, macro_data=None,
                     conviction_summary=None):
    """
    v9.0: Enhanced live dashboard with intelligence + LLM advisory panels.
    """
    # Dynamic target: starting balance + target growth %
    target = balance * (1.0 + EQUITY_TARGET_PCT)
    gap = target - equity
    gap_pct = (gap / target) * 100 if target > 0 else 0

    print(f"\n{'='*70}", flush=True)
    print(f" 📅 LOG: {timestamp.strftime('%H:%M:%S')} | "
          f"🦅 Everest v9.0 (MULTI-MODAL + LLM INTELLIGENCE)", flush=True)
    print(f"{'-'*70}", flush=True)

    # --- PRICE & ACCOUNT ---
    print(f" 💰 Price:   {price:<10.2f}    🛡️ Spread: {spread:<5.1f}", flush=True)
    print(f" 💵 Equity:  ${equity:<10.2f}    🎯 Target: ${target:<8.0f} (Gap: ${gap:<.0f}, {gap_pct:.1f}%)", flush=True)
    print(f"{'-'*70}", flush=True)

    # --- TECHNICAL ANALYSIS ---
    print(f" 🎯 ADX FILTER:     {adx:.1f} "
          f"({'✅ GO' if adx > ADX_THRESHOLD else '⛔ WAIT/CHOP'})", flush=True)
    print(f" 🧠 AI BRAIN:       🟢 UP: {prob_up:.1%}    🔴 DOWN: {prob_down:.1%}", flush=True)
    print(f"    👉 Reason:      {brain_reason}", flush=True)
    print(f" 🌊 TREND:          {trend_status}", flush=True)
    print(f" 📊 TECHS:          RSI: {rsi:.1f} | ATR: {atr:.2f}", flush=True)

    # --- v8.0: INTELLIGENCE PANEL ---
    print(f"{'-'*70}", flush=True)
    print(f" 🌐 INTELLIGENCE LAYER:", flush=True)

    # Sentiment
    if sentiment_data:
        s = sentiment_data
        sent_icon = "🟢" if s.get('bias') == 'bullish' else "🔴" if s.get('bias') == 'bearish' else "⚪"
        print(f"    📱 Social:      {sent_icon} {s.get('bias', 'n/a').upper()} "
              f"({s.get('sentiment_score', 0):+.3f}) | "
              f"Posts: {s.get('post_count', 0)} | Vol: {s.get('volume_trend', 'n/a')} | "
              f"Conf: {s.get('confidence', 'n/a')}", flush=True)
    else:
        print(f"    📱 Social:      ⚪ No data", flush=True)

    # News
    if news_data:
        n = news_data
        news_icon = "🟢" if n.get('overall_bias') == 'bullish' else "🔴" if n.get('overall_bias') == 'bearish' else "⚪"
        embargo = "⛔ EMBARGO" if n.get('embargo_active') else "clear"
        print(f"    📰 News:        {news_icon} {n.get('overall_bias', 'n/a').upper()} "
              f"({n.get('bias_score', 0):+.3f}) | "
              f"Impact: {n.get('impact_level', 'n/a')} | "
              f"Headlines: {n.get('headlines_analyzed', 0)} | {embargo}", flush=True)
    else:
        print(f"    📰 News:        ⚪ No data", flush=True)

    # Macro Regime
    if macro_data:
        m = macro_data
        regime_icons = {
            "risk_off": "🛡️", "risk_on": "📈", "inflation_fear": "🔥",
            "rate_hike": "🏦", "geopolitical_crisis": "⚠️",
            "uncertainty": "❓", "normal": "➡️"
        }
        r_icon = regime_icons.get(m.get('market_regime', ''), '➡️')
        dnt = " | ⛔ DO NOT TRADE" if m.get('do_not_trade') else ""
        print(f"    🌍 Macro:       {r_icon} {m.get('market_regime', 'n/a').upper()} "
              f"(conf: {m.get('confidence', 0):.0%}) | "
              f"Gold: {m.get('gold_bias', 'n/a')} | "
              f"Risk×{m.get('risk_multiplier', 1.0):.2f}{dnt}", flush=True)
    else:
        print(f"    🌍 Macro:       ⚪ No data", flush=True)

    # Conviction
    print(f"{'-'*70}", flush=True)
    if conviction_summary:
        print(f" ⚡ CONVICTION:     {conviction_summary}", flush=True)

    # Decision
    print(f" 🤖 DECISION:       {decision}", flush=True)
    if risk_note:
        print(f" ⚠️ RISK NOTE:      {risk_note}", flush=True)

    # Guardian Status
    try:
        import guardian
        print(f" 🛡️ GUARDIAN:        {guardian.get_guardian_status()}", flush=True)
    except Exception:
        pass

    # v9.0: LLM Advisory Panel (shown when available)
    if conviction_summary and isinstance(conviction_summary, str) and 'LLM' in conviction_summary:
        pass  # Already shown in conviction line
    try:
        import llm_engine
        if llm_engine.is_available():
            print(f" 🧠 LLM ENGINE:      {llm_engine.get_llm_status()}", flush=True)
    except Exception:
        pass

    # Trading Psychology Module
    print(psychology.print_psychology_block(), flush=True)

    print(f"{'='*70}\n", flush=True)
