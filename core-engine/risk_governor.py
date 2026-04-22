"""
risk_governor.py
================
Project Everest — Risk Governor Module

A completely isolated, strategy-agnostic gate that evaluates every proposed trade
against hardcoded .env constraints before it can reach the Execution Engine.

Design Principles:
  - ZERO knowledge of strategy logic. Receives a trade payload, returns a verdict.
  - .env variables are the ultimate authority (overrides config.yaml values).
  - Every decision is timestamped and logged for audit.
  - Thread-safe: can be called from any execution context.

Position Sizing Formula:
  lot_size = (Account_Balance × Risk_Pct) / (ATR_Stop_Distance × Pip_Value)

Verdict Schema:
  {
    "verdict":    "APPROVED" | "REJECTED",
    "symbol":     str,
    "direction":  str,
    "volume":     float,        # Governor-calculated lot size (APPROVED) or requested (REJECTED)
    "sl":         float,
    "tp":         float,
    "reason":     str | None,
    "constraint": str | None,   # Which constraint was violated
    "current_value": str | None,
    "limit_value":   str | None,
    "timestamp":  str           # ISO-8601 UTC
  }
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import yaml
from dotenv import load_dotenv

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
class TradeProposal:
    """
    Incoming trade request from a strategy module.

    Attributes:
        symbol:             Instrument (e.g. "EURUSD", "XAUUSD").
        direction:          "BUY" or "SELL".
        atr_stop_distance:  Distance from entry to stop-loss in price units.
        pip_value:          Dollar value of 1 pip for 1 standard lot.
        entry_price:        Intended entry price.
        sl:                 Stop-loss price.
        tp:                 Take-profit price.
        strategy_name:      Identifier of the originating strategy.
    """

    symbol: str
    direction: str
    atr_stop_distance: float
    pip_value: float
    entry_price: float
    sl: float
    tp: float
    strategy_name: str = "unknown"


@dataclass
class GovernorVerdict:
    """
    Immutable verdict returned by the Risk Governor.
    """

    verdict: str  # "APPROVED" or "REJECTED"
    symbol: str
    direction: str
    volume: float
    entry_price: float
    sl: float
    tp: float
    reason: Optional[str] = None
    constraint: Optional[str] = None
    current_value: Optional[str] = None
    limit_value: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "symbol": self.symbol,
            "direction": self.direction,
            "volume": round(self.volume, 2),
            "entry_price": self.entry_price,
            "sl": self.sl,
            "tp": self.tp,
            "reason": self.reason,
            "constraint": self.constraint,
            "current_value": self.current_value,
            "limit_value": self.limit_value,
            "timestamp": self.timestamp,
        }

    @property
    def approved(self) -> bool:
        return self.verdict == "APPROVED"


# --------------------------------------------------------------------------- #
# Risk Governor
# --------------------------------------------------------------------------- #
class RiskGovernor:
    """
    Strategy-agnostic risk gatekeeper.

    Evaluates every proposed trade against hard limits sourced from .env
    (with config.yaml as fallback). Returns an APPROVED or REJECTED verdict.

    Usage:
        governor = RiskGovernor()
        verdict = governor.evaluate(proposal, account_balance, daily_pnl, open_trade_count)
    """

    def __init__(self, config_override: Optional[dict] = None):
        config = config_override or _load_config()
        risk_cfg = config.get("risk_management", {})

        # .env is the ultimate authority; config.yaml is the fallback
        self._max_risk_pct: float = float(
            os.getenv("MAX_RISK_PCT", risk_cfg.get("max_risk_pct", 0.01))
        )
        self._max_drawdown_limit: float = float(
            os.getenv("MAX_DRAWDOWN_LIMIT", risk_cfg.get("max_drawdown_limit", 0.05))
        )
        self._daily_loss_limit: float = float(
            os.getenv("DAILY_LOSS_LIMIT", risk_cfg.get("daily_loss_limit", 0.02))
        )
        self._max_open_trades: int = int(
            os.getenv("MAX_OPEN_TRADES", risk_cfg.get("max_open_trades", 3))
        )

        # Broker-specific minimums (safety nets)
        self._min_lot: float = float(os.getenv("MIN_LOT_SIZE", 0.01))
        self._max_lot: float = float(os.getenv("MAX_LOT_SIZE", 10.0))

        logger.info(
            "RiskGovernor initialized: max_risk=%.2f%%, max_dd=%.2f%%, "
            "daily_limit=%.2f%%, max_trades=%d, lot_range=[%.2f, %.2f]",
            self._max_risk_pct * 100,
            self._max_drawdown_limit * 100,
            self._daily_loss_limit * 100,
            self._max_open_trades,
            self._min_lot,
            self._max_lot,
        )

    # ------------------------------------------------------------------ #
    # Position Sizing
    # ------------------------------------------------------------------ #
    def calculate_position_size(
        self,
        account_balance: float,
        risk_pct: float,
        atr_stop_distance: float,
        pip_value: float,
    ) -> float:
        """
        Calculates lot size using the standard risk-based formula:

            lot_size = (Account_Balance × Risk_Pct) / (ATR_Stop_Distance × Pip_Value)

        Returns:
            Lot size clamped to [min_lot, max_lot] and rounded to 2 decimals.
            Returns 0.0 if inputs are invalid (prevents division by zero).
        """
        if atr_stop_distance <= 0 or pip_value <= 0:
            logger.error(
                "Invalid sizing inputs: atr_stop_distance=%.5f, pip_value=%.4f",
                atr_stop_distance,
                pip_value,
            )
            return 0.0

        risk_amount = account_balance * risk_pct
        raw_lots = risk_amount / (atr_stop_distance * pip_value)
        clamped = max(self._min_lot, min(self._max_lot, raw_lots))
        final = round(clamped, 2)

        logger.debug(
            "Position sizing: balance=%.2f, risk_amt=%.2f, "
            "atr_stop=%.5f, pip_val=%.4f → raw=%.4f, clamped=%.2f",
            account_balance,
            risk_amount,
            atr_stop_distance,
            pip_value,
            raw_lots,
            final,
        )
        return final

    # ------------------------------------------------------------------ #
    # Core Evaluation Pipeline
    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        proposal: TradeProposal,
        account_balance: float,
        daily_pnl: float,
        open_trade_count: int,
    ) -> GovernorVerdict:
        """
        Evaluate a trade proposal against all risk constraints.

        Args:
            proposal:          The trade to evaluate.
            account_balance:   Current account balance (equity).
            daily_pnl:         Realized + unrealized P&L for the current day.
            open_trade_count:  Number of currently open positions.

        Returns:
            GovernorVerdict with verdict="APPROVED" or verdict="REJECTED".
        """
        logger.info(
            "Evaluating proposal: %s %s | strategy=%s | balance=%.2f | daily_pnl=%.2f | open=%d",
            proposal.direction,
            proposal.symbol,
            proposal.strategy_name,
            account_balance,
            daily_pnl,
            open_trade_count,
        )

        # ---- Gate 1: Direction validation ---- #
        if proposal.direction not in ("BUY", "SELL"):
            return self._reject(
                proposal,
                volume=0.0,
                reason=f"Invalid direction '{proposal.direction}'. Must be BUY or SELL.",
                constraint="DIRECTION_VALIDATION",
            )

        # ---- Gate 2: Daily drawdown limit ---- #
        daily_drawdown_pct = abs(daily_pnl) / account_balance if account_balance > 0 else 0
        if daily_pnl < 0 and daily_drawdown_pct >= self._daily_loss_limit:
            return self._reject(
                proposal,
                volume=0.0,
                reason="Daily loss limit breached. No new trades permitted today.",
                constraint="DAILY_LOSS_LIMIT",
                current_value=f"{daily_drawdown_pct:.4f} ({daily_drawdown_pct * 100:.2f}%)",
                limit_value=f"{self._daily_loss_limit:.4f} ({self._daily_loss_limit * 100:.2f}%)",
            )

        # ---- Gate 3: Maximum open trades ---- #
        if open_trade_count >= self._max_open_trades:
            return self._reject(
                proposal,
                volume=0.0,
                reason="Maximum open trade count reached.",
                constraint="MAX_OPEN_TRADES",
                current_value=str(open_trade_count),
                limit_value=str(self._max_open_trades),
            )

        # ---- Gate 4: Stop-loss sanity ---- #
        if proposal.sl <= 0:
            return self._reject(
                proposal,
                volume=0.0,
                reason="Stop-loss price must be greater than zero.",
                constraint="STOPLOSS_VALIDATION",
            )

        if proposal.atr_stop_distance <= 0:
            return self._reject(
                proposal,
                volume=0.0,
                reason="ATR stop distance must be positive.",
                constraint="ATR_STOP_VALIDATION",
            )

        # ---- Gate 5: Calculate position size ---- #
        volume = self.calculate_position_size(
            account_balance=account_balance,
            risk_pct=self._max_risk_pct,
            atr_stop_distance=proposal.atr_stop_distance,
            pip_value=proposal.pip_value,
        )

        if volume <= 0:
            return self._reject(
                proposal,
                volume=0.0,
                reason="Position size calculation returned zero or negative (invalid inputs).",
                constraint="POSITION_SIZING",
            )

        # ---- Gate 6: Per-trade risk validation ---- #
        # Double-check that the calculated volume doesn't exceed max risk
        actual_risk = (volume * proposal.atr_stop_distance * proposal.pip_value)
        actual_risk_pct = actual_risk / account_balance if account_balance > 0 else 1.0

        if actual_risk_pct > self._max_risk_pct * 1.01:  # 1% tolerance for rounding
            return self._reject(
                proposal,
                volume=volume,
                reason="Calculated risk exceeds maximum per-trade risk limit.",
                constraint="MAX_RISK_PCT",
                current_value=f"{actual_risk_pct:.4f} ({actual_risk_pct * 100:.2f}%)",
                limit_value=f"{self._max_risk_pct:.4f} ({self._max_risk_pct * 100:.2f}%)",
            )

        # ---- Gate 7: Cumulative drawdown check ---- #
        projected_equity = account_balance + daily_pnl - actual_risk
        starting_balance = account_balance - daily_pnl  # Approximate day-start balance
        if starting_balance > 0:
            projected_dd = (starting_balance - projected_equity) / starting_balance
            if projected_dd >= self._max_drawdown_limit:
                return self._reject(
                    proposal,
                    volume=volume,
                    reason="Projected drawdown with this trade would breach the max drawdown limit.",
                    constraint="MAX_DRAWDOWN_LIMIT",
                    current_value=f"{projected_dd:.4f} ({projected_dd * 100:.2f}%)",
                    limit_value=f"{self._max_drawdown_limit:.4f} ({self._max_drawdown_limit * 100:.2f}%)",
                )

        # ---- All gates passed ---- #
        verdict = GovernorVerdict(
            verdict="APPROVED",
            symbol=proposal.symbol,
            direction=proposal.direction,
            volume=volume,
            entry_price=proposal.entry_price,
            sl=proposal.sl,
            tp=proposal.tp,
        )

        logger.info(
            "✅ APPROVED: %s %s %.2f lots (risk $%.2f = %.2f%%)",
            proposal.direction,
            proposal.symbol,
            volume,
            actual_risk,
            actual_risk_pct * 100,
        )

        return verdict

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _reject(
        self,
        proposal: TradeProposal,
        volume: float,
        reason: str,
        constraint: str,
        current_value: Optional[str] = None,
        limit_value: Optional[str] = None,
    ) -> GovernorVerdict:
        """Build and log a REJECTED verdict."""
        verdict = GovernorVerdict(
            verdict="REJECTED",
            symbol=proposal.symbol,
            direction=proposal.direction,
            volume=volume,
            entry_price=proposal.entry_price,
            sl=proposal.sl,
            tp=proposal.tp,
            reason=reason,
            constraint=constraint,
            current_value=current_value,
            limit_value=limit_value,
        )
        logger.warning(
            "🛑 REJECTED: %s %s | %s | %s",
            proposal.direction,
            proposal.symbol,
            constraint,
            reason,
        )
        return verdict

    def get_limits(self) -> dict:
        """Return current risk limits for inspection/debugging."""
        return {
            "max_risk_pct": self._max_risk_pct,
            "max_drawdown_limit": self._max_drawdown_limit,
            "daily_loss_limit": self._daily_loss_limit,
            "max_open_trades": self._max_open_trades,
            "lot_range": [self._min_lot, self._max_lot],
        }


# --------------------------------------------------------------------------- #
# Standalone Test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json

    governor = RiskGovernor()
    print("\n--- Governor Limits ---")
    print(json.dumps(governor.get_limits(), indent=2))

    # Simulate a trade proposal
    test_proposal = TradeProposal(
        symbol="XAUUSD",
        direction="BUY",
        atr_stop_distance=15.0,    # $15 ATR stop on Gold
        pip_value=1.0,             # $1 per pip per lot for XAUUSD
        entry_price=2350.50,
        sl=2335.50,
        tp=2380.50,
        strategy_name="momentum_v1",
    )

    verdict = governor.evaluate(
        proposal=test_proposal,
        account_balance=2000.0,
        daily_pnl=-5.0,
        open_trade_count=1,
    )

    print("\n--- Verdict ---")
    print(json.dumps(verdict.to_dict(), indent=2))
