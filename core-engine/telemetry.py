import os
import time
import requests
import logging
from dotenv import load_dotenv

# Initialize logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TelemetryManager:
    """
    Handles stakeholder notifications via Telegram.
    Includes specific formatting for executions, risk rejections, and daily summaries.
    Implements a robust retry mechanism for 429s and timeouts.
    """

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def _send_with_retry(self, text, parse_mode="Markdown"):
        """
        Sends a message to Telegram with a retry mechanism for timeouts and 429s.
        Retries up to 3 times before dropping.
        """
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials missing in environment variables.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }

        retries = 3
        backoff = 2

        for attempt in range(retries):
            try:
                response = requests.post(self.api_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    return True
                
                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", backoff)
                    logger.warning(f"Telegram 429: Too Many Requests. Retrying after {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                logger.error(f"Telegram API Error: {response.status_code} - {response.text}")
                break # Non-retryable error

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"Telegram Connection Error (Attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                continue
            
            except Exception as e:
                logger.error(f"Unexpected error sending Telegram message: {e}")
                break

        logger.error("Failed to send Telegram message after maximum retries.")
        return False

    def send_execution_alert(self, symbol, direction, lot_size, entry_price, exit_price, slippage):
        """
        Formats and sends a standard trade execution alert.
        Highlighting exact slippage incurred.
        """
        status = "CLOSED" if exit_price else "OPENED"
        price_line = f"*Exit Price:* `{exit_price}`" if exit_price else f"*Entry Price:* `{entry_price}`"
        
        msg = (
            f"🚀 *TRADE {status}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"*Symbol:* `{symbol}`\n"
            f"*Direction:* `{direction}`\n"
            f"*Lot Size:* `{lot_size}`\n"
            f"{price_line}\n"
            f"*Slippage:* `{slippage}` pts\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        return self._send_with_retry(msg)

    def send_risk_rejection(self, symbol, direction, reason):
        """
        Formats and sends a Risk Governor rejection alert.
        High-priority warning and specific mathematical reason.
        """
        msg = (
            f"⚠️ *RISK REJECTION ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"*Target Symbol:* `{symbol}`\n"
            f"*Attempted Direction:* `{direction}`\n"
            f"*Reason:* _{reason}_\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔴 *ACCESS DENIED BY GOVERNOR*"
        )
        return self._send_with_retry(msg)

    def send_daily_summary(self, equity, daily_drawdown_pct, win_rate, regime_distribution):
        """
        Formats and sends an end-of-day report.
        Equity, drawdown, win rate, and market regime distribution.
        """
        regime_str = "\n".join([f"• {regime}: `{count}`" for regime, count in regime_distribution.items()])
        
        msg = (
            f"📅 *END-OF-DAY SUMMARY*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"*Current Equity:* `${equity:,.2f}`\n"
            f"*Daily Drawdown:* `{daily_drawdown_pct:.2f}%`\n"
            f"*Win Rate:* `{win_rate:.1f}%`\n\n"
            f"*AI Regime Distribution:*\n"
            f"{regime_str}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        return self._send_with_retry(msg)

if __name__ == "__main__":
    # Test block
    telemetry = TelemetryManager()
    
    # Test execution alert
    telemetry.send_execution_alert("XAUUSD", "BUY", 0.01, 2350.50, None, 1.2)
    
    # Test risk rejection
    telemetry.send_risk_rejection("XAUUSD", "SELL", "Proposed trade exceeds 1% Max Risk Limit (Calc: 1.42%)")
    
    # Test daily summary
    test_regimes = {"Trending": 12, "Ranging": 8, "Volatile": 4}
    telemetry.send_daily_summary(10500.25, 0.45, 62.5, test_regimes)
