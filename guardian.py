"""
Everest v8.0 — Guardian System (Self-Discipline Enforcer)
==========================================================
Prevents manual trading and enforces risk limits.
Think of this as your personal risk manager who CANNOT be overridden.

WHAT IT DOES:
1. AUTO-CLOSES any trade not placed by Everest (wrong magic number)
2. CANCELS any pending orders not from Everest
3. Enforces daily loss limits (circuit breaker)
4. Enforces maximum drawdown (emergency shutdown)
5. Prevents more than 1 position at a time
6. Logs all violations and sends Telegram alerts
7. After 3 unauthorized trades in a day → FULL LOCKDOWN

HOW IT WORKS:
- Runs as a background thread inside main.py
- Scans every 3 seconds
- Cannot be disabled without changing the code
- Like a Raiz portfolio — you deposit money, Everest manages it
"""
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import MetaTrader5 as mt5

from config import MAGIC_NUMBER, SYMBOL, MAX_RISK_PERCENT_CAP
from telegram_notifier import send_telegram_alert


# =====================================================================
#  GUARDIAN CONFIGURATION
# =====================================================================

# --- Self-Discipline Rules ---
AUTO_CLOSE_UNAUTHORIZED = True     # Close trades not placed by Everest
AUTO_CANCEL_PENDING = True         # Cancel manual pending orders
MAX_DAILY_VIOLATIONS = 3           # After this many → full lockdown for 24hr
VIOLATION_LOCKDOWN_HOURS = 24      # How long to lock after too many violations

# --- Circuit Breakers ---
DAILY_LOSS_LIMIT_PCT = 0.05        # 5% max daily loss → stop trading for the day
MAX_DRAWDOWN_PCT = 0.15            # 15% max drawdown from peak → emergency shutdown
MAX_CONCURRENT_POSITIONS = 3       # Allow 3 stacked positions (validated by backtest)
MAX_LOT_SIZE = 10.0                # Maximum lot size per trade (absolute cap)

# --- Monitoring ---
SCAN_INTERVAL_SECONDS = 0.5        # Hyper-fast monitoring (500ms) for instant protection


# =====================================================================
#  GUARDIAN STATE
# =====================================================================

class GuardianState:
    """Thread-safe state for the Guardian system."""

    def __init__(self):
        self._lock = threading.Lock()
        self.is_locked = False
        self.lock_reason = ""
        self.lock_until = None

        self.daily_violations = 0
        self.total_violations = 0
        self.last_violation_reset = datetime.now().date()

        self.starting_balance = None
        self.daily_start_balance = None
        self.peak_balance = None
        self.last_daily_reset = datetime.now().date()
        self.processed_balance_tickets = set()
        self.is_initial_deals_seeded = False

        self.violation_log = []

    def handle_balance_deals(self):
        """Detect deposits and withdrawals and gracefully adjust limits."""
        # Use a 3-day lookback to completely avoid Windows Local vs MT5 Broker timezone mismatches (e.g. Sydney vs UTC+2)
        start_search = datetime.now() - timedelta(days=3)
        end_search = datetime.now() + timedelta(days=1)
        deals = mt5.history_deals_get(start_search, end_search)
        
        with self._lock:
            if not self.is_initial_deals_seeded:
                if deals:
                    for d in deals:
                        if d.type not in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL):
                            self.processed_balance_tickets.add(d.ticket)
                self.is_initial_deals_seeded = True
                return

            if deals:
                for d in deals:
                    if d.type not in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL) and d.ticket not in self.processed_balance_tickets:
                        self.processed_balance_tickets.add(d.ticket)
                        diff = d.profit
                        # Important: Only adjust daily_start and peak if they are established
                        if self.daily_start_balance is not None:
                            self.daily_start_balance += diff
                        if self.peak_balance is not None:
                            self.peak_balance += diff
                            
                        # Also adjust starting balance
                        if self.starting_balance is not None:
                            self.starting_balance += diff
                            
                        action_str = "Deposit" if diff > 0 else "Withdrawal"
                        msg = f"💰 [GUARDIAN] {action_str} of ${abs(diff):.2f} detected. Adjusting limits."
                        print(msg, flush=True)
                        send_telegram_alert(f"ℹ️ <b>{action_str} Detected</b>\n{msg}")

    def reset_daily(self, current_balance):
        """Reset daily counters at the start of each trading day."""
        with self._lock:
            today = datetime.now().date()
            if today != self.last_daily_reset:
                self.daily_violations = 0
                self.daily_start_balance = current_balance
                self.last_daily_reset = today
                self.last_violation_reset = today
                self.processed_balance_tickets.clear()
                self.is_initial_deals_seeded = False

    def set_starting_balance(self, balance):
        with self._lock:
            if self.starting_balance is None:
                self.starting_balance = balance
                self.daily_start_balance = balance
                self.peak_balance = balance

    def update_peak(self, balance):
        with self._lock:
            if self.peak_balance is None or balance > self.peak_balance:
                self.peak_balance = balance

    def record_violation(self, description):
        with self._lock:
            self.daily_violations += 1
            self.total_violations += 1
            self.violation_log.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "description": description,
                "daily_count": self.daily_violations
            })

            if self.daily_violations >= MAX_DAILY_VIOLATIONS:
                self.is_locked = True
                self.lock_until = datetime.now() + timedelta(hours=VIOLATION_LOCKDOWN_HOURS)
                self.lock_reason = (
                    f"LOCKDOWN: {self.daily_violations} unauthorized trades detected today. "
                    f"Trading suspended until {self.lock_until.strftime('%Y-%m-%d %H:%M')}"
                )

    def set_circuit_breaker(self, reason):
        with self._lock:
            self.is_locked = True
            self.lock_reason = reason
            self.lock_until = None  # Manual reset required

    def check_lock_expired(self):
        with self._lock:
            if self.is_locked and self.lock_until is not None:
                if datetime.now() >= self.lock_until:
                    self.is_locked = False
                    self.lock_reason = ""
                    self.lock_until = None
                    return True  # Lock just expired
            return False

    def is_trading_allowed(self):
        with self._lock:
            return not self.is_locked

    def get_status(self):
        with self._lock:
            return {
                "locked": self.is_locked,
                "reason": self.lock_reason,
                "daily_violations": self.daily_violations,
                "total_violations": self.total_violations,
                "peak_balance": self.peak_balance,
                "daily_start": self.daily_start_balance
            }


# Global state
_state = GuardianState()


# =====================================================================
#  CORE GUARDIAN FUNCTIONS
# =====================================================================

def _close_unauthorized_position(position):
    """Force-close a position that wasn't opened by Everest."""
    ticket = position.ticket
    symbol = position.symbol
    volume = position.volume
    pos_type = position.type

    # Ensure symbol is active in Market Watch to get valid ticks
    mt5.symbol_select(symbol, True)

    # Reverse the trade to close it
    close_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        return False, f"Failed to close #{ticket}: Cannot get tick for {symbol} (MarketWatch issue?)"

    price = tick.bid if pos_type == mt5.ORDER_TYPE_BUY else tick.ask
    if price == 0.0 or price is None:
        return False, f"Failed to close #{ticket}: MT5 returned 0.0 price for {symbol}."

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": close_type,
        "position": int(ticket),
        "price": float(price),
        "magic": int(MAGIC_NUMBER),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return True, f"Closed ticket #{ticket}"
        
    # Fallback to FOK (Some brokers/pairs reject IOC)
    request["type_filling"] = mt5.ORDER_FILLING_FOK
    result_fallback = mt5.order_send(request)
    
    if result_fallback and result_fallback.retcode == mt5.TRADE_RETCODE_DONE:
        return True, f"Closed ticket #{ticket} (via FOK fallback)"

    # If both failed, report the error code
    if result_fallback is None and result is None:
        last_error = mt5.last_error()
        error_str = f"Local API Error: {last_error}"
    else:
        error_msg = result_fallback.comment if result_fallback else (result.comment if result else "None")
        retcode = result_fallback.retcode if result_fallback else (result.retcode if result else 0)
        error_str = f"{error_msg} (retcode: {retcode})"
    
    return False, f"Failed to close #{ticket}: {error_str}"


def _cancel_unauthorized_order(order):
    """Cancel a pending order not placed by Everest."""
    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": order.ticket,
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return True, f"Cancelled order #{order.ticket}"
    else:
        error = result.comment if result else "Unknown error"
        return False, f"Failed to cancel #{order.ticket}: {error}"


def _scan_unauthorized_trades():
    """Check for any positions/orders NOT placed by Everest."""
    violations = []

    # Check open positions
    positions = mt5.positions_get()
    if positions:
        for pos in positions:
            if pos.magic != MAGIC_NUMBER:
                violations.append({
                    "type": "position",
                    "object": pos,
                    "description": (
                        f"UNAUTHORIZED {'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL'} "
                        f"on {pos.symbol} | {pos.volume} lots | "
                        f"Magic: {pos.magic} (expected: {MAGIC_NUMBER})"
                    )
                })

    # Check pending orders
    orders = mt5.orders_get()
    if orders:
        for order in orders:
            if order.magic != MAGIC_NUMBER:
                violations.append({
                    "type": "order",
                    "object": order,
                    "description": (
                        f"UNAUTHORIZED PENDING ORDER on {order.symbol} | "
                        f"{order.volume_current} lots | Magic: {order.magic}"
                    )
                })

    return violations


def _check_circuit_breakers():
    """Check if any circuit breakers should trip."""
    acc = mt5.account_info()
    if acc is None:
        return

    balance = acc.balance
    equity = acc.equity

    _state.handle_balance_deals()
    _state.update_peak(balance)
    _state.reset_daily(balance)
    status = _state.get_status()

    # --- DAILY LOSS LIMIT ---
    if status["daily_start"] and status["daily_start"] > 0:
        daily_loss = status["daily_start"] - equity
        daily_loss_pct = daily_loss / status["daily_start"]

        if daily_loss_pct >= DAILY_LOSS_LIMIT_PCT:
            reason = (
                f"CIRCUIT BREAKER: Daily loss limit hit! "
                f"Lost ${daily_loss:.2f} ({daily_loss_pct:.1%}) today. "
                f"Trading suspended until tomorrow."
            )
            _state.set_circuit_breaker(reason)
            print(f"\n🚨 [GUARDIAN] {reason}", flush=True)
            send_telegram_alert(f"🚨 <b>CIRCUIT BREAKER TRIPPED</b>\n{reason}")

    # --- MAX DRAWDOWN ---
    if status["peak_balance"] and status["peak_balance"] > 0:
        drawdown = status["peak_balance"] - equity
        drawdown_pct = drawdown / status["peak_balance"]

        if drawdown_pct >= MAX_DRAWDOWN_PCT:
            reason = (
                f"EMERGENCY SHUTDOWN: Max drawdown {drawdown_pct:.1%} exceeded "
                f"{MAX_DRAWDOWN_PCT:.0%} limit! "
                f"Peak: ${status['peak_balance']:.2f} → Equity: ${equity:.2f}. "
                f"Manual intervention required to restart."
            )
            _state.set_circuit_breaker(reason)
            print(f"\n🚨🚨🚨 [GUARDIAN] {reason}", flush=True)
            send_telegram_alert(f"🚨🚨🚨 <b>EMERGENCY SHUTDOWN</b>\n{reason}")


def _check_position_limits():
    """Ensure we don't exceed max concurrent positions."""
    Everest_positions = mt5.positions_get(symbol=SYMBOL)
    if Everest_positions and len(Everest_positions) > MAX_CONCURRENT_POSITIONS:
        # Keep the first position, close extras
        for pos in Everest_positions[MAX_CONCURRENT_POSITIONS:]:
            _close_unauthorized_position(pos)
            print(f"⚠️ [GUARDIAN] Closed excess position #{pos.ticket} "
                  f"(max {MAX_CONCURRENT_POSITIONS} allowed)", flush=True)


# =====================================================================
#  GUARDIAN THREAD (Background Watchdog)
# =====================================================================

def _guardian_loop():
    """
    The eternal watchdog. Runs every 3 seconds.
    This is the enforcer that keeps you disciplined.
    """
    print("🛡️ [GUARDIAN] Self-Discipline System ACTIVE", flush=True)
    print(f"   • Auto-close unauthorized: {AUTO_CLOSE_UNAUTHORIZED}", flush=True)
    print(f"   • Daily loss limit: {DAILY_LOSS_LIMIT_PCT:.0%}", flush=True)
    print(f"   • Max drawdown: {MAX_DRAWDOWN_PCT:.0%}", flush=True)
    print(f"   • Max positions: {MAX_CONCURRENT_POSITIONS}", flush=True)
    print(f"   • Max violations before lockdown: {MAX_DAILY_VIOLATIONS}", flush=True)

    while True:
        try:
            # Check if lockout expired
            if _state.check_lock_expired():
                print("🔓 [GUARDIAN] Lockdown period expired. Trading resumed.", flush=True)
                send_telegram_alert("🔓 <b>Lockdown expired.</b> Trading resumed.")

            # 1. SCAN FOR UNAUTHORIZED TRADES
            violations = _scan_unauthorized_trades()

            for v in violations:
                print(f"\n🚨 [GUARDIAN] {v['description']}", flush=True)

                if v["type"] == "position" and AUTO_CLOSE_UNAUTHORIZED:
                    success, msg = _close_unauthorized_position(v["object"])
                    if success:
                        print(f"   ✅ {msg}", flush=True)
                        print(f"\n{'=' * 70}")
                        print(f" 💀 HARSH REALITY CHECK 💀")
                        print(f"{'-' * 70}")
                        print(f" Do you enjoy blowing up accounts? Because this is exactly how you")
                        print(f" blow up accounts. You let emotional impulses (fear or FOMO) override")
                        print(f" the execution of a verified, probabilistic edge.")
                        print(f"")
                        print(f" Let the machine work. If you want to gamble, go to a casino.")
                        print(f" KEEP YOUR HANDS OFF THE MOUSE AND TRUST THE SYSTEM.")
                        print(f"{'=' * 70}\n", flush=True)
                        
                        _state.record_violation(v["description"])

                        alert = (
                            f"🚨 <b>UNAUTHORIZED TRADE CLOSED</b>\n"
                            f"{v['description']}\n\n"
                            f"⚠️ This trade was NOT placed by Everest and has been "
                            f"automatically closed. Stop trading manually!\n\n"
                            f"Daily violations: {_state.get_status()['daily_violations']}"
                            f"/{MAX_DAILY_VIOLATIONS}"
                        )
                        send_telegram_alert(alert)
                    else:
                        print(f"   ❌ {msg}", flush=True)

                elif v["type"] == "order" and AUTO_CANCEL_PENDING:
                    success, msg = _cancel_unauthorized_order(v["object"])
                    if success:
                        print(f"   ✅ {msg}", flush=True)
                        _state.record_violation(v["description"])
                        send_telegram_alert(
                            f"🚨 <b>UNAUTHORIZED ORDER CANCELLED</b>\n{v['description']}"
                        )

            # Check if lockdown was triggered by violations
            status = _state.get_status()
            if status["locked"] and status["daily_violations"] >= MAX_DAILY_VIOLATIONS:
                # Close ALL positions during lockdown
                all_positions = mt5.positions_get()
                if all_positions:
                    for pos in all_positions:
                        _close_unauthorized_position(pos)
                    send_telegram_alert(
                        f"🔒 <b>FULL LOCKDOWN ACTIVATED</b>\n"
                        f"{status['daily_violations']} unauthorized trades detected.\n"
                        f"ALL positions closed. Trading suspended for "
                        f"{VIOLATION_LOCKDOWN_HOURS} hours.\n\n"
                        f"🛑 DO NOT attempt to override. This is for your protection."
                    )

            # 2. CHECK CIRCUIT BREAKERS
            _check_circuit_breakers()

            # 3. CHECK POSITION LIMITS
            _check_position_limits()

        except Exception as e:
            print(f"⚠️ [GUARDIAN] Scan error: {e}", flush=True)

        time.sleep(SCAN_INTERVAL_SECONDS)


def start_guardian():
    """
    Start the Guardian as a background daemon thread.
    Call this from main.py at startup.
    """
    acc = mt5.account_info()
    if acc:
        _state.set_starting_balance(acc.balance)

    thread = threading.Thread(target=_guardian_loop, daemon=True, name="Guardian")
    thread.start()
    return thread


def is_trading_allowed():
    """
    Check with the Guardian before placing any trade.
    Returns: (allowed: bool, reason: str)
    """
    if not _state.is_trading_allowed():
        status = _state.get_status()
        return False, status["reason"]

    # Check position limit
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions and len(positions) >= MAX_CONCURRENT_POSITIONS:
        return False, f"Max {MAX_CONCURRENT_POSITIONS} position(s) already open"

    return True, "OK"


def validate_lot_size(lots):
    """
    Validate that lot size doesn't exceed the guardian's limit.
    Returns clamped lot size.
    """
    if lots > MAX_LOT_SIZE:
        print(f"⚠️ [GUARDIAN] Lot size {lots} clamped to max {MAX_LOT_SIZE}", flush=True)
        return MAX_LOT_SIZE
    return lots


def get_guardian_status():
    """Get the current Guardian status for the dashboard."""
    status = _state.get_status()
    if status["locked"]:
        return f"🔒 LOCKED: {status['reason'][:60]}"
    elif status["daily_violations"] > 0:
        return f"⚠️ {status['daily_violations']} violation(s) today"
    else:
        return "🛡️ Active — No violations"


def get_guardian_summary():
    """Get a summary for Telegram heartbeats."""
    status = _state.get_status()
    return (
        f"🛡️ Guardian: {'🔒 LOCKED' if status['locked'] else '✅ Active'}\n"
        f"Violations today: {status['daily_violations']}/{MAX_DAILY_VIOLATIONS}\n"
        f"Total violations: {status['total_violations']}\n"
        f"Peak balance: ${status['peak_balance']:,.2f}" if status['peak_balance'] else ""
    )

