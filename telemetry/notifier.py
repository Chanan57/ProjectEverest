"""
notifier.py
===========
Project Everest — Telegram Telemetry Notifier

Provides structured, markdown-formatted notifications to a Telegram group chat.
Handles three message classes:
  - Trade Executions  (fills, slippage, ticket data)
  - Risk Rejections   (why the Governor blocked a trade)
  - System Alerts     (generic operational messages)

Thread-safe: can be called from any module without external locking.
"""

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends formatted messages to a Telegram group chat via the Bot API.

    All public methods are thread-safe and fire-and-forget (never raise on failure).
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self._bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self._lock = threading.Lock()
        self._enabled = bool(self._bot_token and self._chat_id)

        if not self._enabled:
            logger.warning(
                "TelegramNotifier disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set."
            )

    # ------------------------------------------------------------------ #
    # Low-level sender
    # ------------------------------------------------------------------ #
    def _send(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Posts a message to the configured Telegram chat.
        Returns True on success, False on any failure.
        """
        if not self._enabled:
            logger.debug("Telegram disabled — message suppressed.")
            return False

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            with self._lock:
                resp = requests.post(url, json=payload, timeout=10)
                resp.raise_for_status()
            logger.debug("Telegram message sent successfully.")
            return True
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # Structured message builders
    # ------------------------------------------------------------------ #
    def broadcast_execution(self, execution_report: dict) -> bool:
        """
        Broadcast a trade execution to the Telegram group.

        Expected keys in execution_report:
            symbol, direction, volume, entry_price, requested_price,
            slippage_points, sl, tp, ticket, timestamp
        """
        rpt = execution_report
        slippage = rpt.get("slippage_points", 0)
        slip_emoji = "🟢" if abs(slippage) <= 2 else "🟡" if abs(slippage) <= 5 else "🔴"

        msg = (
            f"📈 *TRADE EXECUTED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"*Symbol:*  `{rpt.get('symbol', 'N/A')}`\n"
            f"*Direction:*  {rpt.get('direction', 'N/A')}\n"
            f"*Volume:*  `{rpt.get('volume', 0):.2f}` lots\n"
            f"*Entry:*  `{rpt.get('entry_price', 0):.5f}`\n"
            f"*Requested:*  `{rpt.get('requested_price', 0):.5f}`\n"
            f"*Slippage:*  {slip_emoji} `{slippage}` pts\n"
            f"*SL:*  `{rpt.get('sl', 0):.5f}`  |  *TP:*  `{rpt.get('tp', 0):.5f}`\n"
            f"*Ticket:*  `#{rpt.get('ticket', 'N/A')}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {rpt.get('timestamp', datetime.now(timezone.utc).isoformat())}"
        )
        return self._send(msg)

    def broadcast_rejection(self, rejection_report: dict) -> bool:
        """
        Broadcast a Risk Governor rejection to the Telegram group.

        Expected keys in rejection_report:
            symbol, direction, requested_volume, reason, constraint,
            current_value, limit_value, timestamp
        """
        rpt = rejection_report
        msg = (
            f"🛑 *TRADE REJECTED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"*Symbol:*  `{rpt.get('symbol', 'N/A')}`\n"
            f"*Direction:*  {rpt.get('direction', 'N/A')}\n"
            f"*Requested Vol:*  `{rpt.get('requested_volume', 0):.2f}` lots\n"
            f"*Reason:*  _{rpt.get('reason', 'Unknown')}_\n"
            f"*Constraint:*  `{rpt.get('constraint', 'N/A')}`\n"
            f"*Current:*  `{rpt.get('current_value', 'N/A')}`  |  *Limit:*  `{rpt.get('limit_value', 'N/A')}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {rpt.get('timestamp', datetime.now(timezone.utc).isoformat())}"
        )
        return self._send(msg)

    def broadcast_system_alert(self, title: str, body: str, level: str = "INFO") -> bool:
        """
        Send a general system alert (startup, shutdown, error, etc.).
        """
        emoji_map = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🚨", "CRITICAL": "💀"}
        emoji = emoji_map.get(level.upper(), "ℹ️")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{body}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {ts}"
        )
        return self._send(msg)

    # Legacy alias for backward compatibility
    def send_message(self, message: str) -> bool:
        return self._send(message)


if __name__ == "__main__":
    notifier = TelegramNotifier()
    notifier.broadcast_system_alert(
        "Project Everest",
        "Telemetry Service initialized successfully.",
        level="INFO",
    )
