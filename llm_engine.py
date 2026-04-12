"""
Everest v9.0 — LLM Intelligence Engine
========================================
Dual-mode: Groq API (primary) → Ollama local (fallback).
All outputs are Pydantic-validated structured JSON.

Three roles:
  1. Sentiment Reanalysis   — Context-aware Reddit post scoring (replaces VADER)
  2. News Narrative Synthesis — Understands event magnitude (replaces regex)
  3. Cross-Signal Reasoning  — Advisory meta-analysis of signal alignment

Safety:
  - All outputs are bounded by Pydantic validators
  - confidence_adjustment is hard-clamped to ±0.10
  - If both Groq and Ollama fail, returns None (existing pipeline takes over)
  - Never triggers trades directly — advisory only
"""
import json
import time
from typing import Optional
from datetime import datetime

try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Graceful degradation if pydantic is not installed yet
    print("⚠️ [LLM] pydantic not installed. LLM engine disabled.", flush=True)
    BaseModel = None

from cache_manager import cache

from config import (
    GROQ_API_KEY, GROQ_MODEL, OLLAMA_MODEL, OLLAMA_HOST,
    LLM_TIMEOUT_SECONDS, LLM_CACHE_TTL, LLM_ENABLED,
    LLM_MAX_CONFIDENCE_ADJUSTMENT
)

# =====================================================================
#  OUTPUT SCHEMAS (Pydantic models enforce structure + bounds)
# =====================================================================

if BaseModel is not None:
    class SentimentAnalysis(BaseModel):
        """Schema for LLM-enhanced sentiment analysis of Reddit posts."""
        sentiment_score: float = Field(ge=-1.0, le=1.0,
            description="Overall sentiment from -1.0 (very bearish) to +1.0 (very bullish)")
        confidence: str = Field(pattern="^(high|medium|low)$",
            description="Confidence in the assessment based on post quality and consensus")
        bias: str = Field(pattern="^(bullish|bearish|neutral)$",
            description="Dominant direction of sentiment")
        reasoning: str = Field(max_length=250,
            description="Brief explanation of the sentiment drivers")

        @field_validator('sentiment_score')
        @classmethod
        def clamp_score(cls, v):
            return max(-1.0, min(1.0, round(v, 4)))


    class NewsNarrative(BaseModel):
        """Schema for LLM-enhanced news narrative synthesis."""
        narrative: str = Field(max_length=60,
            description="Short label for the dominant narrative (e.g., 'rate_pause_rally')")
        gold_impact: str = Field(pattern="^(bullish|bearish|neutral)$",
            description="Expected impact on gold prices")
        impact_score: float = Field(ge=0.0, le=1.0,
            description="Magnitude of the expected impact (0.0 = negligible, 1.0 = extreme)")
        urgency: str = Field(pattern="^(low|medium|high|extreme)$",
            description="How time-sensitive this narrative is")
        key_event: str = Field(max_length=120,
            description="The single most important event driving this narrative")
        reasoning: str = Field(max_length=250,
            description="Brief explanation of the analysis")

        @field_validator('impact_score')
        @classmethod
        def clamp_impact(cls, v):
            return max(0.0, min(1.0, round(v, 4)))


    class CrossSignalAdvisory(BaseModel):
        """Schema for LLM cross-signal meta-analysis. Advisory only."""
        assessment: str = Field(pattern="^(proceed|caution|avoid)$",
            description="Overall recommendation for the proposed trade")
        confidence_adjustment: float = Field(ge=-0.10, le=0.10,
            description="Suggested adjustment to conviction score (bounded ±0.10)")
        risk_flag: bool = Field(
            description="True if the LLM detects an unusual risk not captured by other signals")
        reasoning: str = Field(max_length=300,
            description="Explanation of the advisory decision")

        @field_validator('confidence_adjustment')
        @classmethod
        def clamp_adjustment(cls, v):
            limit = LLM_MAX_CONFIDENCE_ADJUSTMENT
            return max(-limit, min(limit, round(v, 4)))

else:
    # Stubs if pydantic is missing
    SentimentAnalysis = None
    NewsNarrative = None
    CrossSignalAdvisory = None


# =====================================================================
#  INTERNAL: LLM QUERY ENGINE (Groq Primary → Ollama Fallback)
# =====================================================================

_groq_client = None
_groq_initialized = False


def _init_groq():
    """Lazy-initialize the Groq client."""
    global _groq_client, _groq_initialized
    if _groq_initialized:
        return
    _groq_initialized = True

    if not GROQ_API_KEY:
        print("⚠️ [LLM] GROQ_API_KEY not set. Groq API disabled (will use Ollama fallback).", flush=True)
        return
    try:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY, timeout=LLM_TIMEOUT_SECONDS)
        print("✅ [LLM] Groq API connected.", flush=True)
    except ImportError:
        print("⚠️ [LLM] groq package not installed. Run: pip install groq", flush=True)
    except Exception as e:
        print(f"⚠️ [LLM] Groq init error: {e}", flush=True)


def _query_groq(system_prompt: str, user_prompt: str) -> Optional[str]:
    """
    Query Groq API with structured JSON output.
    Returns raw JSON string or None on failure.
    """
    _init_groq()
    if _groq_client is None:
        return None

    try:
        response = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=400
        )
        content = response.choices[0].message.content
        if content:
            return content.strip()
        return None
    except Exception as e:
        print(f"⚠️ [LLM] Groq query error: {e}", flush=True)
        return None


def _query_ollama(system_prompt: str, user_prompt: str, schema: dict) -> Optional[str]:
    """
    Query local Ollama as fallback. Uses schema-constrained output.
    Returns raw JSON string or None on failure.
    """
    try:
        import ollama
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            format=schema,
            options={
                "temperature": 0,
                "num_predict": 400
            }
        )
        content = response.get('message', {}).get('content', '')
        if content:
            return content.strip()
        return None
    except ImportError:
        # Ollama package not installed — that's OK, it's optional
        return None
    except Exception as e:
        print(f"⚠️ [LLM] Ollama query error: {e}", flush=True)
        return None


def _query_llm(system_prompt: str, user_prompt: str, schema_class) -> Optional[str]:
    """
    Dual-mode query: try Groq first, fall back to Ollama.
    Returns raw JSON string or None if both fail.
    """
    if not LLM_ENABLED or schema_class is None:
        return None

    # Primary: Groq API (fast, free tier)
    result = _query_groq(system_prompt, user_prompt)
    if result is not None:
        return result

    # Fallback: Ollama (local)
    schema = schema_class.model_json_schema()
    result = _query_ollama(system_prompt, user_prompt, schema)
    return result


def _safe_parse(raw_json: Optional[str], schema_class):
    """
    Parse and validate LLM output against a Pydantic schema.
    Returns the validated model instance or None on failure.
    Includes fallback logic to extract JSON from messy responses.
    """
    if not raw_json or schema_class is None:
        return None

    # Attempt 1: Direct parse
    try:
        return schema_class.model_validate_json(raw_json)
    except Exception:
        pass

    # Attempt 2: Extract JSON object from surrounding text
    try:
        start = raw_json.index('{')
        end = raw_json.rindex('}') + 1
        extracted = raw_json[start:end]
        return schema_class.model_validate_json(extracted)
    except Exception:
        pass

    # Attempt 3: Try parsing as dict then validating
    try:
        data = json.loads(raw_json)
        return schema_class.model_validate(data)
    except Exception:
        pass

    print(f"⚠️ [LLM] Failed to parse response. Raw: {raw_json[:200]}...", flush=True)
    return None


# =====================================================================
#  SYSTEM PROMPT (shared across all roles)
# =====================================================================

_SYSTEM_PROMPT = (
    "You are a senior quantitative analyst specializing in gold (XAUUSD) markets. "
    "You work inside an automated trading engine called Everest. "
    "Your role is to provide precise, data-driven assessments. "
    "You MUST respond ONLY with valid JSON matching the requested schema. "
    "Be conservative: when uncertain, bias toward neutral/caution. "
    "Never fabricate data. If information is insufficient, say so in your reasoning."
)


# =====================================================================
#  PUBLIC API: THREE LLM ROLES
# =====================================================================

def analyze_sentiment(reddit_posts: list) -> Optional[dict]:
    """
    Role 1: LLM-enhanced sentiment analysis on raw Reddit posts.
    Replaces VADER scoring with context-aware reasoning.

    Args:
        reddit_posts: List of dicts from sentiment_engine._fetch_reddit_data()
            Each dict has: text, upvotes, comments, subreddit

    Returns:
        dict with: sentiment_score, confidence, bias, reasoning
        None if LLM is unavailable (VADER fallback should be used)
    """
    if not LLM_ENABLED or SentimentAnalysis is None:
        return None

    cache_key = "llm_sentiment"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if not reddit_posts:
        return None

    # Format posts for the LLM (compact, relevant info only)
    posts_text = "\n".join([
        f"{i+1}. [r/{p.get('subreddit', '?')} ↑{p.get('upvotes', 0)} "
        f"💬{p.get('comments', 0)}] \"{p.get('text', '')[:150]}\""
        for i, p in enumerate(reddit_posts[:6])
    ])

    prompt = f"""Analyze these Reddit posts about gold/XAUUSD trading and provide a sentiment assessment.

POSTS:
{posts_text}

Respond with JSON:
- sentiment_score: float from -1.0 (very bearish) to +1.0 (very bullish)
- confidence: "high", "medium", or "low" (based on post quality, consensus, and volume)
- bias: "bullish", "bearish", or "neutral"
- reasoning: brief explanation (max 250 chars) covering dominant themes, consensus vs dissent, and quality of arguments

Key considerations:
- Weight high-engagement posts more heavily (upvotes + comments)
- Distinguish between informed analysis and retail FOMO/panic
- Reddit sarcasm and meme posts should be discounted
- Gold-specific context: safe-haven demand, inflation fears, rate expectations"""

    raw = _query_llm(_SYSTEM_PROMPT, prompt, SentimentAnalysis)
    result = _safe_parse(raw, SentimentAnalysis)

    if result:
        data = result.model_dump()
        data["source"] = "llm"
        data["timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cache.set(cache_key, data, LLM_CACHE_TTL)
        print(f"🧠 [LLM] Sentiment: {data['sentiment_score']:+.3f} ({data['bias']}) "
              f"| Conf: {data['confidence']} | {data['reasoning'][:60]}...", flush=True)
        return data

    return None


def analyze_news(headlines: list) -> Optional[dict]:
    """
    Role 2: LLM-enhanced news narrative synthesis.
    Replaces regex-based event classification with contextual understanding.

    Args:
        headlines: List of dicts from news_intelligence
            Each dict has: title, source, description

    Returns:
        dict with: narrative, gold_impact, impact_score, urgency, key_event, reasoning
        None if LLM is unavailable (regex fallback should be used)
    """
    if not LLM_ENABLED or NewsNarrative is None:
        return None

    cache_key = "llm_news"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if not headlines:
        return None

    # Format headlines (compact)
    headlines_text = "\n".join([
        f"{i+1}. [{h.get('source', '?')}] \"{h.get('title', '')}\""
        for i, h in enumerate(headlines[:8])
    ])

    prompt = f"""Analyze these financial news headlines and assess their impact on gold (XAUUSD).

HEADLINES:
{headlines_text}

Respond with JSON:
- narrative: short label for the dominant story (e.g., "fed_pause_rally", "geopolitical_escalation")
- gold_impact: "bullish", "bearish", or "neutral"
- impact_score: float 0.0 (negligible) to 1.0 (market-moving)
- urgency: "low", "medium", "high", or "extreme"
- key_event: the single most important headline/event (max 120 chars)
- reasoning: brief analysis (max 250 chars) covering macro implications for gold

Gold-specific context:
- Rate cuts / dovish Fed → bullish for gold
- Geopolitical risk / war / sanctions → bullish for gold (safe haven)
- Strong USD / rate hikes / hawkish Fed → bearish for gold
- Inflation fears → generally bullish for gold
- Risk-on / equity rallies → mildly bearish for gold"""

    raw = _query_llm(_SYSTEM_PROMPT, prompt, NewsNarrative)
    result = _safe_parse(raw, NewsNarrative)

    if result:
        data = result.model_dump()
        data["source"] = "llm"
        data["timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cache.set(cache_key, data, LLM_CACHE_TTL)
        print(f"🧠 [LLM] News: {data['gold_impact']} ({data['impact_score']:.2f}) "
              f"| Urgency: {data['urgency']} | {data['narrative']}", flush=True)
        return data

    return None


def cross_signal_review(market_snapshot: dict) -> Optional[dict]:
    """
    Role 3: LLM cross-signal reasoning and advisory meta-analysis.
    Reviews all signals and provides a bounded confidence adjustment.

    Args:
        market_snapshot: dict with keys:
            price, trend, rsi, adx, atr, ml_prob, signal,
            sentiment_bias, news_bias, regime, conviction

    Returns:
        dict with: assessment, confidence_adjustment, risk_flag, reasoning
        None if LLM is unavailable (existing conviction logic takes over)
    """
    if not LLM_ENABLED or CrossSignalAdvisory is None:
        return None

    cache_key = "llm_advisory"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Only run cross-signal review when there's an actual signal to assess
    signal = market_snapshot.get('signal')
    if not signal or signal not in ('BUY', 'SELL'):
        return None

    # Format market state compactly
    ml_prob = market_snapshot.get('ml_prob', 0.5)
    prompt = f"""Review this XAUUSD trading signal assessment and provide an advisory.

MARKET STATE:
- Price: ${market_snapshot.get('price', 'N/A')} | Trend: {market_snapshot.get('trend', 'N/A')}
- RSI: {market_snapshot.get('rsi', 'N/A'):.1f} | ADX: {market_snapshot.get('adx', 'N/A'):.1f} | ATR: ${market_snapshot.get('atr', 'N/A'):.2f}
- ML Ensemble: {ml_prob:.0%} {'bullish' if ml_prob > 0.5 else 'bearish'}
- Sentiment: {market_snapshot.get('sentiment_bias', 'N/A')}
- News: {market_snapshot.get('news_bias', 'N/A')}
- Macro Regime: {market_snapshot.get('regime', 'N/A')}
- Proposed Signal: {signal}
- Current Conviction: {market_snapshot.get('conviction', 0):.0%}

Respond with JSON:
- assessment: "proceed" (signals align), "caution" (some conflict), or "avoid" (major red flags)
- confidence_adjustment: float from -0.10 to +0.10 (how much to adjust the conviction score)
- risk_flag: true if you detect unusual risk not captured by the technical indicators
- reasoning: brief explanation (max 300 chars)

Rules:
- Be conservative. When in doubt, reduce confidence.
- Never recommend confidence_adjustment above +0.05 unless ALL signals strongly align.
- Flag risk if RSI is extreme (>75 or <25), ADX is declining, or news/sentiment contradict the signal.
- Your output is ADVISORY ONLY — you cannot override the bot's Guardian system."""

    raw = _query_llm(_SYSTEM_PROMPT, prompt, CrossSignalAdvisory)
    result = _safe_parse(raw, CrossSignalAdvisory)

    if result:
        data = result.model_dump()
        data["source"] = "llm"
        data["signal_reviewed"] = signal
        data["timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cache.set(cache_key, data, LLM_CACHE_TTL)

        emoji = {"proceed": "✅", "caution": "⚠️", "avoid": "🛑"}.get(data['assessment'], "❓")
        print(f"🧠 [LLM] Advisory: {emoji} {data['assessment'].upper()} "
              f"| Adj: {data['confidence_adjustment']:+.3f} "
              f"| Risk: {'⚠️ YES' if data['risk_flag'] else 'No'} "
              f"| {data['reasoning'][:60]}...", flush=True)
        return data

    return None


# =====================================================================
#  UTILITY: STATUS & DIAGNOSTICS
# =====================================================================

def get_llm_status() -> str:
    """Get a human-readable status string for the dashboard."""
    if not LLM_ENABLED:
        return "🔌 LLM: DISABLED"

    _init_groq()
    if _groq_client is not None:
        return f"🧠 LLM: Groq ({GROQ_MODEL})"

    # Check if Ollama is reachable
    try:
        import ollama
        ollama.list()
        return f"🧠 LLM: Ollama ({OLLAMA_MODEL})"
    except Exception:
        pass

    return "⚠️ LLM: No backend available"


def is_available() -> bool:
    """Check if any LLM backend is reachable."""
    if not LLM_ENABLED:
        return False

    _init_groq()
    if _groq_client is not None:
        return True

    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False
