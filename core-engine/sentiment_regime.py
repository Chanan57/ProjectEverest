"""
sentiment_regime.py
===================
Project Everest — Sentiment & Regime Analysis Module

Acts as the bot's 'world view'. This module:
  1. Fetches and standardizes RSS headlines from major financial news sources.
  2. Determines the current trading session (Sydney/Tokyo/London/New York).
  3. Constructs a rich prompt and queries a local Ollama LLM (e.g. Gemma 4).
  4. Validates and returns a strict JSON regime assessment.
  5. Falls back to a safe 'event_risk' state on any LLM failure or timeout.

Output Schema:
  {
    "regime":     str,   # e.g. "trending", "ranging", "volatile", "event_risk"
    "confidence": float, # 0.0 – 1.0
    "bias":       str    # "bullish" | "bearish" | "neutral"
  }
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, field_validator

# --------------------------------------------------------------------------- #
# Configuration
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
# Data Models
# --------------------------------------------------------------------------- #
class RegimeSignal(BaseModel):
    """Validated market regime assessment returned by the LLM."""

    regime: str
    confidence: float
    bias: str

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, round(float(v), 4)))

    @field_validator("bias")
    @classmethod
    def validate_bias(cls, v: str) -> str:
        allowed = {"bullish", "bearish", "neutral"}
        v = v.strip().lower()
        if v not in allowed:
            raise ValueError(f"bias must be one of {allowed}, got '{v}'")
        return v

    def to_dict(self) -> dict:
        return self.model_dump()


class NewsHeadline(BaseModel):
    """Standardized representation of a single news item."""

    source: str
    title: str
    published: str  # ISO-8601 string


# --------------------------------------------------------------------------- #
# RSS Feed Fetcher
# --------------------------------------------------------------------------- #
FEED_FETCH_TIMEOUT = 8  # seconds per feed


def _parse_entry_date(entry) -> str:
    """Extract and normalize the publication date from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_rss_headlines(feeds: list[dict], max_per_feed: int = 5) -> list[NewsHeadline]:
    """
    Fetches headlines from a list of RSS feed definitions.

    Args:
        feeds:        List of {"name": str, "url": str} dicts from config.yaml.
        max_per_feed: Maximum entries to extract per feed.

    Returns:
        A deduplicated, sorted list of NewsHeadline objects.
    """
    headlines: list[NewsHeadline] = []
    seen_titles: set[str] = set()

    for feed_def in feeds:
        name = feed_def.get("name", "Unknown")
        url = feed_def.get("url", "")
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": "ProjectEverest/1.0"})
            if parsed.bozo and not parsed.entries:
                logger.warning("Feed '%s' returned a malformed response.", name)
                continue

            count = 0
            for entry in parsed.entries:
                if count >= max_per_feed:
                    break
                title = getattr(entry, "title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                headlines.append(
                    NewsHeadline(
                        source=name,
                        title=title,
                        published=_parse_entry_date(entry),
                    )
                )
                count += 1
            logger.debug("Fetched %d headlines from '%s'.", count, name)

        except Exception as e:
            logger.warning("Failed to fetch feed '%s' (%s): %s", name, url, e)

    # Sort by publication date, newest first
    headlines.sort(key=lambda h: h.published, reverse=True)
    return headlines


# --------------------------------------------------------------------------- #
# Trading Session Detection
# --------------------------------------------------------------------------- #
def get_active_sessions(session_config: dict) -> list[str]:
    """
    Returns a list of currently active trading session names based on config.

    Note: Handles overnight sessions (e.g. Sydney spans 21:00 – 06:00 UTC).
    """
    now_utc = datetime.now(timezone.utc)
    current_minutes = now_utc.hour * 60 + now_utc.minute
    active = []

    for session_name, times in session_config.items():
        open_h, open_m = (int(x) for x in times["open"].split(":"))
        close_h, close_m = (int(x) for x in times["close"].split(":"))
        open_minutes = open_h * 60 + open_m
        close_minutes = close_h * 60 + close_m

        if open_minutes < close_minutes:
            # Normal session (e.g. London 08:00 – 16:00)
            if open_minutes <= current_minutes < close_minutes:
                active.append(session_name.capitalize())
        else:
            # Overnight session (e.g. Sydney 21:00 – 06:00)
            if current_minutes >= open_minutes or current_minutes < close_minutes:
                active.append(session_name.capitalize())

    return active if active else ["Inter-session"]


# --------------------------------------------------------------------------- #
# Prompt Engineering
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = """\
You are a senior macro analyst and quantitative strategist specializing in forex and commodity markets.
Your role is to assess the CURRENT MARKET REGIME based solely on recent financial news headlines.

You MUST respond with ONLY a single valid JSON object. Do NOT include markdown, code fences, explanations,
or any text before or after the JSON. The JSON must conform exactly to this schema:

{
  "regime":     <string>,  // e.g. "trending", "ranging", "volatile", "risk_on", "risk_off", "event_risk"
  "confidence": <float>,   // a number between 0.0 (no confidence) and 1.0 (very high confidence)
  "bias":       <string>   // MUST be exactly one of: "bullish", "bearish", or "neutral"
}

Regime definitions:
  - "trending"    : Clear directional momentum driven by a dominant macro theme.
  - "ranging"     : Market awaiting catalysts; low conviction, mean-reverting behaviour likely.
  - "volatile"    : High uncertainty, erratic price action; multiple conflicting signals.
  - "risk_on"     : Broad appetite for risk; equities and commodity currencies favoured.
  - "risk_off"    : Flight to safe-havens (USD, JPY, Gold); risk assets under pressure.
  - "event_risk"  : A major scheduled or unscheduled event is dominating market attention.
"""


def build_llm_prompt(headlines: list[NewsHeadline], active_sessions: list[str]) -> str:
    """Assembles the user-facing portion of the LLM prompt."""
    now_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y %H:%M UTC")
    sessions_str = " / ".join(active_sessions) if active_sessions else "Inter-session"

    headline_block = "\n".join(
        f"  [{h.source}] {h.published[:16].replace('T', ' ')} — {h.title}"
        for h in headlines
    )

    user_message = f"""\
Current Date & Time: {now_str}
Active Trading Sessions: {sessions_str}

Recent Financial News Headlines:
{headline_block}

Based exclusively on the above context, output your single JSON assessment now.
"""
    return user_message


# --------------------------------------------------------------------------- #
# LLM Client (Ollama)
# --------------------------------------------------------------------------- #
SAFE_FALLBACK: dict = {"regime": "event_risk", "confidence": 0.0, "bias": "neutral"}


def _query_ollama(
    prompt: str,
    model: str,
    ollama_url: str,
    timeout: int,
) -> dict:
    """
    Sends a prompt to a local Ollama instance and returns the parsed regime dict.

    Raises:
        requests.exceptions.Timeout: On LLM timeout.
        ValueError: If the LLM returns malformed or non-compliant JSON.
    """
    endpoint = f"{ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "options": {
            "temperature": 0.1,  # Low temperature for deterministic, structured output
            "num_predict": 128,
        },
        "format": "json",  # Ollama native JSON mode — enforces valid JSON output
    }

    logger.debug("Querying Ollama at %s (model=%s, timeout=%ds)", endpoint, model, timeout)
    response = requests.post(endpoint, json=payload, timeout=timeout)
    response.raise_for_status()

    raw_content: str = response.json()["message"]["content"].strip()
    logger.debug("Raw LLM response: %s", raw_content)

    # Parse and validate
    parsed = json.loads(raw_content)
    signal = RegimeSignal(**parsed)
    return signal.to_dict()


def get_regime_signal(
    headlines: list[NewsHeadline],
    active_sessions: list[str],
    model: str,
    ollama_url: str,
    timeout: int,
) -> dict:
    """
    Core function: builds the prompt, queries the LLM, and returns a validated regime dict.
    Returns SAFE_FALLBACK on any failure.
    """
    if not headlines:
        logger.warning("No headlines available; returning safe fallback.")
        return {**SAFE_FALLBACK, "reason": "no_headlines"}

    prompt = build_llm_prompt(headlines, active_sessions)

    try:
        result = _query_ollama(prompt, model, ollama_url, timeout)
        logger.info("Regime signal: %s", result)
        return result

    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out after %ds. Returning safe fallback.", timeout)
        return {**SAFE_FALLBACK, "reason": "llm_timeout"}

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama at %s. Is it running?", ollama_url)
        return {**SAFE_FALLBACK, "reason": "llm_connection_error"}

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("LLM returned malformed JSON: %s. Returning safe fallback.", e)
        return {**SAFE_FALLBACK, "reason": "llm_invalid_json"}

    except ValidationError as e:
        logger.error("LLM response failed schema validation: %s. Returning safe fallback.", e)
        return {**SAFE_FALLBACK, "reason": "llm_schema_violation"}

    except Exception as e:
        logger.error("Unexpected error querying LLM: %s. Returning safe fallback.", e)
        return {**SAFE_FALLBACK, "reason": "llm_unknown_error"}


# --------------------------------------------------------------------------- #
# Sentiment & Regime Engine (Main Class)
# --------------------------------------------------------------------------- #
class SentimentRegimeEngine:
    """
    Manages the periodic news fetch + LLM regime assessment cycle.

    Usage:
        engine = SentimentRegimeEngine()
        engine.start()                   # Starts background polling thread
        signal = engine.get_latest()     # Non-blocking read from any thread
        engine.stop()
    """

    def __init__(self, config_override: Optional[dict] = None):
        config = config_override or _load_config()
        sr_cfg = config.get("sentiment_regime", {})
        infra_cfg = config.get("infrastructure", {})

        self._enabled: bool = sr_cfg.get("enabled", True)
        self._model: str = os.getenv("LLM_MODEL", sr_cfg.get("llm_model", "gemma3:4b"))
        self._ollama_url: str = os.getenv(
            "OLLAMA_BASE_URL", infra_cfg.get("ollama_url", "http://localhost:11434")
        )
        self._timeout: int = sr_cfg.get("llm_timeout_seconds", 20)
        self._interval: int = sr_cfg.get("fetch_interval_seconds", 900)
        self._max_headlines: int = sr_cfg.get("max_headlines", 15)
        self._feeds: list[dict] = sr_cfg.get("feeds", [])
        self._sessions_cfg: dict = sr_cfg.get("trading_sessions", {})

        self._latest_signal: dict = dict(SAFE_FALLBACK)
        self._latest_headlines: list[NewsHeadline] = []
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def get_latest(self) -> dict:
        """Thread-safe read of the most recent regime signal."""
        with self._lock:
            return dict(self._latest_signal)

    def get_latest_headlines(self) -> list[dict]:
        """Thread-safe read of the most recent headlines (as dicts)."""
        with self._lock:
            return [h.model_dump() for h in self._latest_headlines]

    def run_once(self) -> dict:
        """
        Performs a single fetch + analysis cycle synchronously.
        Returns the regime signal dict.
        """
        logger.info("Sentiment & Regime: Starting analysis cycle.")
        max_per_feed = max(1, self._max_headlines // max(len(self._feeds), 1))
        headlines = fetch_rss_headlines(self._feeds, max_per_feed=max_per_feed)
        headlines = headlines[: self._max_headlines]

        active_sessions = get_active_sessions(self._sessions_cfg)
        logger.info("Active sessions: %s | Headlines fetched: %d", active_sessions, len(headlines))

        signal = get_regime_signal(
            headlines=headlines,
            active_sessions=active_sessions,
            model=self._model,
            ollama_url=self._ollama_url,
            timeout=self._timeout,
        )

        with self._lock:
            self._latest_signal = signal
            self._latest_headlines = headlines

        return signal

    def _polling_loop(self):
        """Background loop: runs a cycle, then sleeps for the configured interval."""
        logger.info("Sentiment & Regime polling thread started (interval=%ds).", self._interval)
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.exception("Unhandled error in regime polling loop: %s", e)
            self._stop_event.wait(timeout=self._interval)
        logger.info("Sentiment & Regime polling thread stopped.")

    def start(self):
        """Start the background polling thread."""
        if not self._enabled:
            logger.info("Sentiment & Regime module is disabled in config.")
            return
        if self._thread and self._thread.is_alive():
            logger.warning("Engine is already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._polling_loop,
            name="SentimentRegimeEngine",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """Signal the background thread to stop gracefully."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Sentiment & Regime engine stopped.")


# --------------------------------------------------------------------------- #
# Standalone Entry Point (for testing)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    engine = SentimentRegimeEngine()
    print("\n=== Running one-shot analysis cycle ===\n")
    result = engine.run_once()
    print("\n--- Regime Signal ---")
    print(json.dumps(result, indent=2))
    print("\n--- Recent Headlines ---")
    for h in engine.get_latest_headlines():
        print(f"  [{h['source']}] {h['published'][:16]} — {h['title']}")
