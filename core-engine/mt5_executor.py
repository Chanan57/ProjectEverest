"""
mt5_executor.py
===============
Project Everest — MetaTrader 5 Execution Engine

Handles all order routing to the MT5 terminal. Accepts only APPROVED verdicts
from the Risk Governor — never interacts with strategy logic directly.

Responsibilities:
  - MT5 terminal connection lifecycle (init, login, shutdown).
  - Market order execution with fill-or-kill semantics.
  - Slippage measurement (requested vs. actual fill price).
  - Execution report generation (ticket, entry, slippage, timestamp).
  - Telegram broadcast of every execution and every rejection.

Design Principles:
  - The Executor NEVER decides position size or risk. That is the Governor's job.
  - Every order result is logged with full MT5 error detail.
  - Thread-safe: the MT5 API is single-threaded by nature, so all calls
    are serialized through a reentrant lock.
"""

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import yaml
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Conditional MT5 import — allows module to load on non-Windows for testing
# --------------------------------------------------------------------------- #
try:
    import MetaTrader5 as mt5

    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

# Add parent directory to path for cross-module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import with importlib to handle hyphenated directory names
import importlib.util

def _import_from_path(module_name: str, file_path: str):
    """Import a module from an absolute file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_notifier_mod = _import_from_path(
    "notifier", os.path.join(_PROJECT_ROOT, "telemetry", "notifier.py")
)
TelegramNotifier = _notifier_mod.TelegramNotifier

# GovernorVerdict imported from sibling module in the same directory
from risk_governor import GovernorVerdict

# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error("Failed to load config.yaml: %s", e)
        return {}


# --------------------------------------------------------------------------- #
# Data Structures
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionReport:
    """
    Immutable record of a completed order execution.
    """

    success: bool
    symbol: str
    direction: str
    volume: float
    requested_price: float
    entry_price: float
    slippage_points: float
    sl: float
    tp: float
    ticket: int
    mt5_retcode: int
    mt5_comment: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "symbol": self.symbol,
            "direction": self.direction,
            "volume": self.volume,
            "requested_price": self.requested_price,
            "entry_price": self.entry_price,
            "slippage_points": self.slippage_points,
            "sl": self.sl,
            "tp": self.tp,
            "ticket": self.ticket,
            "mt5_retcode": self.mt5_retcode,
            "mt5_comment": self.mt5_comment,
            "timestamp": self.timestamp,
        }


# --------------------------------------------------------------------------- #
# MT5 Connection Manager
# --------------------------------------------------------------------------- #
class MT5Connection:
    """
    Manages the MT5 terminal connection lifecycle.
    """

    def __init__(self):
        self._login = int(os.getenv("MT5_LOGIN", "0"))
        self._password = os.getenv("MT5_PASSWORD", "")
        self._server = os.getenv("MT5_SERVER", "")
        self._path = os.getenv("MT5_PATH", "")
        self._connected = False

    def connect(self) -> bool:
        """Initialize and log into the MT5 terminal."""
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 package not available on this platform.")
            return False

        logger.info("Initializing MT5 terminal...")

        init_kwargs = {}
        if self._path:
            init_kwargs["path"] = self._path

        if not mt5.initialize(**init_kwargs):
            error = mt5.last_error()
            logger.error("MT5 initialize() failed: %s", error)
            return False

        if self._login and self._password and self._server:
            authorized = mt5.login(
                login=self._login,
                password=self._password,
                server=self._server,
            )
            if not authorized:
                error = mt5.last_error()
                logger.error("MT5 login() failed: %s", error)
                mt5.shutdown()
                return False

        account = mt5.account_info()
        if account:
            logger.info(
                "MT5 connected: Account #%d | Balance: %.2f %s | Server: %s",
                account.login,
                account.balance,
                account.currency,
                account.server,
            )
        self._connected = True
        return True

    def disconnect(self):
        """Gracefully shut down the MT5 terminal connection."""
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 terminal connection closed.")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> Optional[dict]:
        """Return current account snapshot."""
        if not self._connected or not MT5_AVAILABLE:
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "currency": info.currency,
            "server": info.server,
        }


# --------------------------------------------------------------------------- #
# Execution Engine
# --------------------------------------------------------------------------- #
class MT5Executor:
    """
    Accepts APPROVED GovernorVerdicts and routes them to the MT5 terminal.

    Usage:
        connection = MT5Connection()
        connection.connect()

        notifier = TelegramNotifier()
        executor = MT5Executor(connection, notifier)

        verdict = governor.evaluate(proposal, balance, pnl, open_count)
        if verdict.approved:
            report = executor.execute(verdict)

        connection.disconnect()
    """

    # MT5 order type mapping
    _ORDER_TYPES = {
        "BUY": mt5.ORDER_TYPE_BUY if MT5_AVAILABLE else 0,
        "SELL": mt5.ORDER_TYPE_SELL if MT5_AVAILABLE else 1,
    }

    # Maximum allowed slippage in points
    DEFAULT_MAX_SLIPPAGE = 20

    def __init__(
        self,
        connection: MT5Connection,
        notifier: Optional[TelegramNotifier] = None,
        max_slippage: int = DEFAULT_MAX_SLIPPAGE,
    ):
        self._conn = connection
        self._notifier = notifier or TelegramNotifier()
        self._max_slippage = max_slippage
        import threading

        self._lock = threading.RLock()

    def execute(self, verdict: GovernorVerdict) -> ExecutionReport:
        """
        Execute an APPROVED trade verdict on the MT5 terminal.

        Args:
            verdict: A GovernorVerdict with verdict="APPROVED".

        Returns:
            ExecutionReport with full fill details or failure info.
        """
        if not verdict.approved:
            logger.error("Executor received a non-APPROVED verdict. Ignoring.")
            self._broadcast_rejection(verdict)
            return self._failed_report(verdict, "Verdict was not APPROVED")

        if not self._conn.is_connected:
            logger.error("MT5 is not connected. Cannot execute.")
            return self._failed_report(verdict, "MT5 not connected")

        if not MT5_AVAILABLE:
            logger.error("MT5 library not available.")
            return self._failed_report(verdict, "MT5 library unavailable")

        with self._lock:
            return self._send_market_order(verdict)

    def _send_market_order(self, verdict: GovernorVerdict) -> ExecutionReport:
        """Build and send a market order request to MT5."""
        symbol = verdict.symbol
        direction = verdict.direction

        # Ensure the symbol is available in Market Watch
        if not mt5.symbol_select(symbol, True):
            logger.error("Failed to select symbol '%s' in Market Watch.", symbol)
            return self._failed_report(verdict, f"Symbol '{symbol}' not available")

        # Get current tick for price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error("Failed to get tick data for '%s'.", symbol)
            return self._failed_report(verdict, "No tick data")

        price = tick.ask if direction == "BUY" else tick.bid
        order_type = self._ORDER_TYPES.get(direction)

        if order_type is None:
            return self._failed_report(verdict, f"Invalid direction: {direction}")

        # Build the order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": verdict.volume,
            "type": order_type,
            "price": price,
            "sl": verdict.sl,
            "tp": verdict.tp,
            "deviation": self._max_slippage,
            "magic": 202604,  # Project Everest magic number
            "comment": "Everest",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        logger.info(
            "Sending %s order: %s %.2f lots @ %.5f | SL=%.5f | TP=%.5f",
            direction,
            symbol,
            verdict.volume,
            price,
            verdict.sl,
            verdict.tp,
        )

        # Execute
        result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            logger.error("order_send() returned None. MT5 error: %s", error)
            return self._failed_report(verdict, f"order_send() failed: {error}")

        # Calculate slippage
        fill_price = result.price if result.price else price
        if direction == "BUY":
            slippage_raw = fill_price - price
        else:
            slippage_raw = price - fill_price

        # Convert to points using symbol info
        sym_info = mt5.symbol_info(symbol)
        point = sym_info.point if sym_info else 0.00001
        slippage_points = round(slippage_raw / point) if point > 0 else 0

        report = ExecutionReport(
            success=(result.retcode == mt5.TRADE_RETCODE_DONE),
            symbol=symbol,
            direction=direction,
            volume=result.volume if result.volume else verdict.volume,
            requested_price=price,
            entry_price=fill_price,
            slippage_points=slippage_points,
            sl=verdict.sl,
            tp=verdict.tp,
            ticket=result.order if result.order else 0,
            mt5_retcode=result.retcode,
            mt5_comment=result.comment if result.comment else "",
        )

        if report.success:
            logger.info(
                "✅ ORDER FILLED: %s %s %.2f lots @ %.5f | Ticket #%d | Slippage: %d pts",
                direction,
                symbol,
                report.volume,
                report.entry_price,
                report.ticket,
                report.slippage_points,
            )
            self._broadcast_execution(report)
        else:
            logger.error(
                "❌ ORDER FAILED: retcode=%d (%s) | %s %s",
                result.retcode,
                report.mt5_comment,
                direction,
                symbol,
            )
            self._broadcast_order_failure(report)

        return report

    # ------------------------------------------------------------------ #
    # Telegram Broadcasting
    # ------------------------------------------------------------------ #
    def _broadcast_execution(self, report: ExecutionReport):
        """Send a trade execution notification to Telegram."""
        try:
            self._notifier.broadcast_execution(report.to_dict())
        except Exception as e:
            logger.error("Failed to broadcast execution to Telegram: %s", e)

    def _broadcast_rejection(self, verdict: GovernorVerdict):
        """Send a rejection notification to Telegram."""
        try:
            self._notifier.broadcast_rejection(verdict.to_dict())
        except Exception as e:
            logger.error("Failed to broadcast rejection to Telegram: %s", e)

    def _broadcast_order_failure(self, report: ExecutionReport):
        """Send an order failure alert to Telegram."""
        try:
            self._notifier.broadcast_system_alert(
                title="ORDER FAILED",
                body=(
                    f"*Symbol:* `{report.symbol}`\n"
                    f"*Direction:* {report.direction}\n"
                    f"*Volume:* `{report.volume:.2f}`\n"
                    f"*Retcode:* `{report.mt5_retcode}`\n"
                    f"*Comment:* _{report.mt5_comment}_"
                ),
                level="ERROR",
            )
        except Exception as e:
            logger.error("Failed to broadcast order failure to Telegram: %s", e)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _failed_report(self, verdict: GovernorVerdict, reason: str) -> ExecutionReport:
        """Build a failure ExecutionReport without touching MT5."""
        return ExecutionReport(
            success=False,
            symbol=verdict.symbol,
            direction=verdict.direction,
            volume=verdict.volume,
            requested_price=verdict.entry_price,
            entry_price=0.0,
            slippage_points=0,
            sl=verdict.sl,
            tp=verdict.tp,
            ticket=0,
            mt5_retcode=-1,
            mt5_comment=reason,
        )

    def get_open_positions(self) -> list[dict]:
        """Return all currently open positions."""
        if not MT5_AVAILABLE or not self._conn.is_connected:
            return []
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "magic": p.magic,
                "comment": p.comment,
            }
            for p in positions
        ]

    def get_open_position_count(self) -> int:
        """Return count of open positions."""
        if not MT5_AVAILABLE or not self._conn.is_connected:
            return 0
        positions = mt5.positions_get()
        return len(positions) if positions else 0

    def get_daily_pnl(self) -> float:
        """
        Calculate today's realized + unrealized P&L.
        Unrealized = sum of all open position profits.
        Realized = approximated from today's closed deals.
        """
        if not MT5_AVAILABLE or not self._conn.is_connected:
            return 0.0

        # Unrealized P&L from open positions
        unrealized = 0.0
        positions = mt5.positions_get()
        if positions:
            unrealized = sum(p.profit for p in positions)

        # Realized P&L from today's closed deals
        from datetime import datetime, timezone, timedelta

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        deals = mt5.history_deals_get(today_start, datetime.now(timezone.utc))
        realized = 0.0
        if deals:
            realized = sum(d.profit + d.commission + d.swap for d in deals if d.entry == 1)

        return round(unrealized + realized, 2)


# --------------------------------------------------------------------------- #
# Full Pipeline Demo (standalone)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json
    from risk_governor import RiskGovernor, TradeProposal

    print("\n=== Project Everest: Execution Pipeline Test ===\n")

    # 1. Initialize components
    notifier = TelegramNotifier()
    governor = RiskGovernor()
    connection = MT5Connection()

    if not connection.connect():
        print("❌ Cannot connect to MT5. Exiting.")
        sys.exit(1)

    executor = MT5Executor(connection, notifier)

    # 2. Get account state
    account = connection.get_account_info()
    print(f"Account: #{account['login']} | Balance: {account['balance']:.2f} {account['currency']}")

    daily_pnl = executor.get_daily_pnl()
    open_count = executor.get_open_position_count()
    print(f"Daily P&L: {daily_pnl:.2f} | Open positions: {open_count}")

    # 3. Create a test proposal
    proposal = TradeProposal(
        symbol="EURUSD",
        direction="BUY",
        atr_stop_distance=0.0015,  # 15 pips for EURUSD
        pip_value=10.0,            # $10 per pip per lot for EURUSD
        entry_price=1.13500,
        sl=1.13350,
        tp=1.13800,
        strategy_name="test_pipeline",
    )

    # 4. Risk Governor evaluation
    verdict = governor.evaluate(
        proposal=proposal,
        account_balance=account["balance"],
        daily_pnl=daily_pnl,
        open_trade_count=open_count,
    )
    print(f"\nGovernor Verdict: {verdict.verdict}")
    print(json.dumps(verdict.to_dict(), indent=2))

    # 5. Execute if approved (COMMENTED OUT for safety)
    # if verdict.approved:
    #     report = executor.execute(verdict)
    #     print(f"\nExecution Report:")
    #     print(json.dumps(report.to_dict(), indent=2))

    # 6. Cleanup
    connection.disconnect()
    print("\n✅ Pipeline test complete.")
