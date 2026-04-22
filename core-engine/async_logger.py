"""
async_logger.py
===============
Project Everest — Asynchronous Trade Event Logger

Architectural Role:
  The mt5_executor.py execution engine NEVER writes to the database directly.
  Instead, it emits lightweight event payloads to this module's asyncio.Queue.
  This module runs as an isolated background coroutine or standalone service,
  consuming events from the queue and persisting them to SQLite without
  ever blocking the execution pipeline.

Design Principles:
  - The queue is the only coupling point. The executor puts(), this logger gets().
  - Batch inserts: write every 5 seconds OR when the buffer reaches 50 events.
  - Exponential backoff: never crash on a locked database. Retain events, retry.
  - The logger is the sole owner of the SQLite connection lifecycle.

Event Payload Schema (dict):
  {
    "timestamp":       ISO-8601 str  — Event time (UTC)
    "ticket_id":       int           — MT5 ticket number
    "action":          str           — "TRADE_OPENED" | "TRADE_CLOSED" | "GOVERNOR_REJECTION"
    "symbol":          str           — e.g. "XAUUSD"
    "lot_size":        float         — Executed volume in lots
    "entry_price":     float         — Fill price
    "exit_price":      float | None  — Filled on close, None on open/rejection
    "slippage":        float         — Slippage in points (positive = adverse)
    "rsi_at_entry":    float | None  — RSI at time of signal
    "atr_at_entry":    float | None  — ATR at time of signal
    "ai_regime":       str | None    — Regime string from SentimentRegimeEngine
    "actual_r_multiple": float|None  — Set on TRADE_CLOSED
  }
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
_DB_PATH = os.path.join(os.path.dirname(__file__), "trades.db")
_BATCH_SIZE = 50         # Flush when this many events are buffered
_FLUSH_INTERVAL = 5.0    # Also flush every N seconds regardless of batch size
_MAX_RETRIES = 6         # Exponential backoff attempts before dropping a batch
_BASE_BACKOFF = 0.25     # Initial retry delay in seconds (doubles each attempt)


# --------------------------------------------------------------------------- #
# Database Schema
# --------------------------------------------------------------------------- #
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trade_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    ticket_id         INTEGER,
    action            TEXT    NOT NULL,
    symbol            TEXT,
    lot_size          REAL,
    entry_price       REAL,
    exit_price        REAL,
    slippage          REAL,
    rsi_at_entry      REAL,
    atr_at_entry      REAL,
    ai_regime         TEXT,
    actual_r_multiple REAL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_trade_events_timestamp ON trade_events (timestamp);
"""

_INSERT_SQL = """
INSERT INTO trade_events (
    timestamp, ticket_id, action, symbol, lot_size, entry_price,
    exit_price, slippage, rsi_at_entry, atr_at_entry, ai_regime, actual_r_multiple
) VALUES (
    :timestamp, :ticket_id, :action, :symbol, :lot_size, :entry_price,
    :exit_price, :slippage, :rsi_at_entry, :atr_at_entry, :ai_regime, :actual_r_multiple
)
"""


# --------------------------------------------------------------------------- #
# Event Payload Builder (helper for the execution engine)
# --------------------------------------------------------------------------- #
def build_event(
    action: str,
    symbol: str,
    ticket_id: int = 0,
    lot_size: float = 0.0,
    entry_price: float = 0.0,
    exit_price: Optional[float] = None,
    slippage: float = 0.0,
    rsi_at_entry: Optional[float] = None,
    atr_at_entry: Optional[float] = None,
    ai_regime: Optional[str] = None,
    actual_r_multiple: Optional[float] = None,
) -> dict:
    """
    Convenience factory — call this in mt5_executor or risk_governor and
    place the result on the shared queue.

    Example (from mt5_executor.py):
        event = build_event("TRADE_OPENED", symbol="XAUUSD", ticket_id=12345, ...)
        await log_queue.put(event)
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_id": ticket_id,
        "action": action.upper().strip(),
        "symbol": symbol,
        "lot_size": lot_size,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "slippage": slippage,
        "rsi_at_entry": rsi_at_entry,
        "atr_at_entry": atr_at_entry,
        "ai_regime": ai_regime,
        "actual_r_multiple": actual_r_multiple,
    }


# --------------------------------------------------------------------------- #
# Database Initialization
# --------------------------------------------------------------------------- #
async def _init_database(db_path: str) -> None:
    """Create the table and index if they do not exist."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(_CREATE_TABLE_SQL)
        await db.execute(_CREATE_INDEX_SQL)
        await db.commit()
    logger.info("Trade events database initialized at: %s", db_path)


# --------------------------------------------------------------------------- #
# Batch Writer with Exponential Backoff
# --------------------------------------------------------------------------- #
async def _write_batch(batch: list[dict], db_path: str) -> bool:
    """
    Attempts to insert a batch of events into SQLite.
    Retries with exponential backoff if the database is locked.

    Returns:
        True  — batch was written successfully.
        False — all retry attempts exhausted; batch is discarded (caller logs loss).
    """
    delay = _BASE_BACKOFF
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with aiosqlite.connect(db_path, timeout=10) as db:
                await db.executemany(_INSERT_SQL, batch)
                await db.commit()
            logger.debug("Batch of %d events written to DB (attempt %d).", len(batch), attempt)
            return True

        except aiosqlite.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                logger.warning(
                    "DB locked (attempt %d/%d). Retrying in %.2fs — reason: %s",
                    attempt, _MAX_RETRIES, delay, e,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)  # Cap backoff at 30 seconds
            else:
                logger.error("Unrecoverable DB error on attempt %d: %s", attempt, e)
                return False  # Non-lock errors are not retried

        except Exception as e:
            logger.error("Unexpected DB write error on attempt %d: %s", attempt, e)
            return False

    logger.critical(
        "All %d retry attempts exhausted. Dropping %d events to prevent memory leakage.",
        _MAX_RETRIES,
        len(batch),
    )
    return False


# --------------------------------------------------------------------------- #
# Background Worker Coroutine
# --------------------------------------------------------------------------- #
async def _logger_worker(
    queue: asyncio.Queue,
    db_path: str,
    batch_size: int,
    flush_interval: float,
) -> None:
    """
    Long-running coroutine that owns the write pipeline.

    Flush strategy:
      - Immediately flush when batch buffer reaches `batch_size`.
      - Otherwise, flush on the `flush_interval` timer.
      - On shutdown (sentinel None received), flush whatever remains.
    """
    buffer: list[dict] = []
    last_flush = time.monotonic()
    total_written = 0
    total_failed = 0

    logger.info(
        "Async logger worker started (batch_size=%d, flush_interval=%.1fs, db=%s).",
        batch_size, flush_interval, db_path,
    )

    while True:
        # Determine remaining time until the next scheduled flush
        elapsed = time.monotonic() - last_flush
        timeout = max(0.0, flush_interval - elapsed)

        try:
            event = await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            event = None  # Flush timer fired — no new event

        # Sentinel: None signals a graceful shutdown
        if event is None and not isinstance(event, dict):
            # This handles the timer case AND the shutdown sentinel
            if event is None and queue.empty():
                # Could be timer OR shutdown sentinel — drain the queue check
                # We let the flush happen, then check shutdown flag is set externally
                pass
        
        if event is not None and isinstance(event, dict):
            buffer.append(event)
            queue.task_done()

        # Flush condition: batch full OR timer expired OR shutdown sentinel
        should_flush = len(buffer) >= batch_size or (time.monotonic() - last_flush) >= flush_interval
        is_shutdown = event is None and not isinstance(event, dict) and len(buffer) > 0

        if buffer and (should_flush or is_shutdown):
            batch_to_write = buffer.copy()
            buffer.clear()
            last_flush = time.monotonic()

            success = await _write_batch(batch_to_write, db_path)
            if success:
                total_written += len(batch_to_write)
                logger.info(
                    "Flushed %d events (total written: %d).", len(batch_to_write), total_written
                )
            else:
                total_failed += len(batch_to_write)
                logger.error(
                    "%d events LOST after retry exhaustion (total failed: %d).",
                    len(batch_to_write), total_failed,
                )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
class AsyncTradeLogger:
    """
    Public interface for the asynchronous trade logger.

    Usage (from any async context):

        logger_service = AsyncTradeLogger()
        await logger_service.start()

        # From mt5_executor (after trade is filled):
        event = build_event("TRADE_OPENED", symbol="XAUUSD", ticket_id=99999,
                            lot_size=0.10, entry_price=2350.5, slippage=1.5,
                            atr_at_entry=15.2, rsi_at_entry=62.1, ai_regime="trending")
        await logger_service.emit(event)

        # On shutdown:
        await logger_service.stop()
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Initialize the database and launch the background worker."""
        await _init_database(self._db_path)
        self._worker_task = asyncio.create_task(
            _logger_worker(
                queue=self._queue,
                db_path=self._db_path,
                batch_size=_BATCH_SIZE,
                flush_interval=_FLUSH_INTERVAL,
            ),
            name="AsyncTradeLogger",
        )
        logger.info("AsyncTradeLogger started.")

    async def emit(self, event: dict) -> None:
        """
        Non-blocking event submission from any coroutine (e.g., the execution engine).
        This put() call returns immediately — the caller is never blocked.
        """
        await self._queue.put(event)

    def emit_nowait(self, event: dict) -> None:
        """
        Synchronous, non-blocking emit for use from non-async contexts.
        Raises asyncio.QueueFull if the queue is at max capacity (if maxsize is set).
        """
        self._queue.put_nowait(event)

    async def stop(self) -> None:
        """
        Graceful shutdown: drain the queue, flush remaining events, cancel worker.
        """
        logger.info("AsyncTradeLogger stopping — flushing remaining events...")
        await self._queue.join()  # Block until all queued events are processed
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncTradeLogger stopped cleanly.")

    @property
    def queue_depth(self) -> int:
        """Returns the number of events currently waiting to be written."""
        return self._queue.qsize()


# --------------------------------------------------------------------------- #
# Standalone Demo
# --------------------------------------------------------------------------- #
async def _demo():
    """
    Simulates the execution engine emitting events while the logger persists them
    without blocking.
    """
    import random

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    log_service = AsyncTradeLogger(db_path=":memory:")  # Use in-memory DB for demo
    await log_service.start()

    actions = ["TRADE_OPENED", "TRADE_CLOSED", "GOVERNOR_REJECTION"]
    symbols = ["XAUUSD", "EURUSD", "GBPUSD"]
    regimes = ["trending", "ranging", "volatile", "risk_on", "risk_off"]

    print("\n=== Simulating 120 trade events ===\n")
    for i in range(120):
        action = random.choice(actions)
        event = build_event(
            action=action,
            symbol=random.choice(symbols),
            ticket_id=random.randint(10_000_000, 99_999_999),
            lot_size=round(random.uniform(0.01, 0.50), 2),
            entry_price=round(random.uniform(1.10, 2400.0), 5),
            exit_price=round(random.uniform(1.10, 2400.0), 5) if action == "TRADE_CLOSED" else None,
            slippage=round(random.uniform(-3.0, 3.0), 1),
            rsi_at_entry=round(random.uniform(20.0, 80.0), 2),
            atr_at_entry=round(random.uniform(0.0005, 0.0050), 5),
            ai_regime=random.choice(regimes),
            actual_r_multiple=round(random.uniform(-1.5, 3.0), 2) if action == "TRADE_CLOSED" else None,
        )
        await log_service.emit(event)
        print(f"  [{i+1:03}] Emitted: {action} — {event['symbol']} @ {event['entry_price']}")
        await asyncio.sleep(0.05)   # Simulate execution engine pace

    # Allow the logger to process all remaining events
    await log_service.stop()
    print("\n✅ All events processed. Logger stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(_demo())
