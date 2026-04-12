"""
Everest v8.0 — Dynamic Risk Manager
Lot sizing with intelligence-aware risk adjustment.
Uses percentage-based hard cap (3% of balance) instead of fixed dollar amount.
"""
import MetaTrader5 as mt5
from config import *


def get_lot_size(balance, risk_pct, sl_dist, sym_info,
                 risk_multiplier=1.0, alignment="partial", do_not_trade=False):
    """
    Calculates the exact lot size for the trade with v8.0 intelligence adjustments.

    Args:
        balance: Account balance in USD
        risk_pct: Base risk percentage (e.g., 0.02 for 2%)
        sl_dist: Stop-loss distance in price units
        sym_info: MT5 symbol info object
        risk_multiplier: From intelligence aggregator (default 1.0)
        alignment: Signal alignment assessment
        do_not_trade: If True, returns 0 lots

    Returns:
        tuple: (lot_size, risk_in_usd, risk_note_string)
    """
    contract_size = sym_info.trade_contract_size
    acc_info = mt5.account_info()

    # --- v8.0: DO NOT TRADE MODE ---
    if do_not_trade:
        return 0.0, 0.0, "⛔ BLOCKED: Do-Not-Trade Mode (Macro Intelligence)"

    # 1. PERCENTAGE-BASED HARD CAP (3% of balance)
    max_risk_usd = balance * MAX_RISK_PERCENT_CAP
    min_lot_risk_usd = 0.01 * contract_size * sl_dist

    if min_lot_risk_usd > max_risk_usd:
        return 0.0, 0.0, (f"⛔ BLOCKED: Min lot risk ${min_lot_risk_usd:.2f} > "
                          f"{MAX_RISK_PERCENT_CAP:.0%} cap (${max_risk_usd:.2f})")

    # 2. STANDARD RISK CALCULATION
    risk_cash_usd = balance * risk_pct

    # --- v8.0: APPLY INTELLIGENCE RISK MULTIPLIER ---
    # Clamp the multiplier to prevent extreme values
    effective_mult = max(0.25, min(1.50, risk_multiplier))
    adjusted_risk = risk_cash_usd * effective_mult

    raw_lots = adjusted_risk / (sl_dist * contract_size)

    # 3. MARGIN CHECK: Does the broker actually let us take this size?
    margin_check = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, SYMBOL, 1.0, sym_info.ask)
    max_lots = raw_lots
    if margin_check is not None and margin_check > 0:
        max_lots = (acc_info.margin_free * 0.95) / margin_check

    # 4. FINAL APPROVAL
    final_lots = round(min(raw_lots, max_lots), 2)
    if final_lots < 0.01:
        final_lots = 0.01

    actual_risk_usd = final_lots * contract_size * sl_dist

    # --- v8.0: HARD CAP CHECK ON FINAL (post-multiplier) ---
    if actual_risk_usd > max_risk_usd:
        # Scale down to fit within the percentage cap
        final_lots = round(max_risk_usd / (contract_size * sl_dist), 2)
        if final_lots < 0.01:
            return 0.0, 0.0, f"⛔ BLOCKED: Cannot fit within {MAX_RISK_PERCENT_CAP:.0%} cap"
        actual_risk_usd = final_lots * contract_size * sl_dist

    # Build the risk note
    risk_pct_actual = (actual_risk_usd / balance) * 100 if balance > 0 else 0

    mult_note = ""
    if effective_mult != 1.0:
        direction = "↑" if effective_mult > 1.0 else "↓"
        mult_note = f" | Intel×{effective_mult:.2f}{direction}"

    alignment_note = ""
    if alignment in ["strong", "aligned"]:
        alignment_note = " | 🎯 Aligned"
    elif alignment == "conflicting":
        alignment_note = " | ⚠️ Conflicting"

    risk_note = f"Risk: ${actual_risk_usd:.2f} ({risk_pct_actual:.1f}%){mult_note}{alignment_note}"
    return final_lots, adjusted_risk, risk_note
