"""
Everest v8.0 — News Intelligence Engine
Fetches financial news from NewsAPI + RSS feeds, classifies headlines
using NLP, detects event types, and scores market impact.
Replaces the intelligence role of news_filter.py (embargo logic preserved separately).
"""
import time
import re
from datetime import datetime, timedelta

from config import (
    NEWSAPI_KEY, NEWS_KEYWORDS, NEWS_DOMAINS,
    NEWS_RSS_FEEDS, NEWS_CACHE_TTL, SENTIMENT_MODE
)
from cache_manager import cache

# --- Lazy imports ---
_newsapi_client = None
_vader = None
_finbert_pipeline = None
_initialized = False

# --- Event detection patterns ---
EVENT_PATTERNS = {
    "monetary_policy": [
        r"\b(interest rate|rate hike|rate cut|fed|federal reserve|fomc|powell|"
        r"hawkish|dovish|taper|quantitative|monetary policy|central bank|ecb|boj)\b"
    ],
    "inflation": [
        r"\b(inflation|cpi|ppi|consumer price|price index|deflation|stagflation|"
        r"cost of living|hyperinflation)\b"
    ],
    "geopolitical": [
        r"\b(war|conflict|military|invasion|sanctions|missile|nuclear|"
        r"tension|escalat|geopolit|attack|strike|nato|ceasefire)\b"
    ],
    "economic_health": [
        r"\b(recession|gdp|unemployment|jobs|nonfarm|non-farm|payroll|"
        r"economic growth|slowdown|contraction|labor market|jobless)\b"
    ],
    "market_crisis": [
        r"\b(crash|collapse|crisis|panic|bank run|default|contagion|"
        r"black swan|liquidity|margin call|bankruptcy|bailout)\b"
    ],
    "safe_haven": [
        r"\b(safe haven|gold surge|risk off|flight to safety|treasury|"
        r"bond yields|dollar strength|haven demand)\b"
    ]
}

# Pre-compile patterns for performance
_compiled_patterns = {
    event_type: [re.compile(p, re.IGNORECASE) for p in patterns]
    for event_type, patterns in EVENT_PATTERNS.items()
}

# Symbols affected by each event type (for XAUUSD context)
EVENT_AFFECTED_SYMBOLS = {
    "monetary_policy": ["XAUUSD", "EURUSD", "DXY"],
    "inflation": ["XAUUSD", "EURUSD", "USDJPY"],
    "geopolitical": ["XAUUSD", "USDJPY", "USOIL"],
    "economic_health": ["XAUUSD", "EURUSD", "SPX500"],
    "market_crisis": ["XAUUSD", "USDJPY", "SPX500"],
    "safe_haven": ["XAUUSD", "USDJPY", "USDCHF"]
}


def _init_newsapi():
    """Initialize NewsAPI client."""
    global _newsapi_client
    if _newsapi_client is not None:
        return
    if not NEWSAPI_KEY or NEWSAPI_KEY == "YOUR_NEWSAPI_KEY":
        print("⚠️ [NEWS] NewsAPI key not configured. Skipping NewsAPI.", flush=True)
        return
    try:
        from newsapi import NewsApiClient
        _newsapi_client = NewsApiClient(api_key=NEWSAPI_KEY)
        print("✅ [NEWS] NewsAPI connected.", flush=True)
    except Exception as e:
        print(f"⚠️ [NEWS] NewsAPI init failed: {e}", flush=True)


def _init_nlp():
    """Initialize VADER (and optionally FinBERT) for headline scoring."""
    global _vader, _finbert_pipeline
    if _vader is not None:
        return
    try:
        import nltk
        nltk.download('vader_lexicon', quiet=True)
        from nltk.sentiment import SentimentIntensityAnalyzer
        _vader = SentimentIntensityAnalyzer()
    except Exception as e:
        print(f"⚠️ [NEWS] VADER init failed: {e}", flush=True)

    if SENTIMENT_MODE == "full" and _finbert_pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline
            _finbert_pipeline = hf_pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                device=-1
            )
        except Exception:
            pass  # Already warned in sentiment_engine


def _initialize():
    """One-time initialization."""
    global _initialized
    if _initialized:
        return
    _init_newsapi()
    _init_nlp()
    _initialized = True


def _fetch_newsapi_headlines():
    """
    Fetch recent headlines from NewsAPI.
    Falls back to no domain filtering if premium domains are blocked (free tier).
    Returns list of dicts: {title, description, source, url, published_at}
    """
    if _newsapi_client is None:
        return []

    articles = []
    from_date = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

    # Try with domain filter first (paid tier)
    try:
        response = _newsapi_client.get_everything(
            q=NEWS_KEYWORDS,
            domains=NEWS_DOMAINS,
            language="en",
            sort_by="publishedAt",
            page_size=30,
            from_param=from_date
        )
        for a in response.get("articles", []):
            articles.append({
                "title": a.get("title", ""),
                "description": a.get("description", "") or "",
                "source": a.get("source", {}).get("name", "unknown"),
                "url": a.get("url", ""),
                "published_at": a.get("publishedAt", "")
            })
    except Exception as e:
        # Domain filter may fail on free tier — retry without it
        try:
            response = _newsapi_client.get_everything(
                q=NEWS_KEYWORDS,
                language="en",
                sort_by="publishedAt",
                page_size=30,
                from_param=from_date
            )
            for a in response.get("articles", []):
                articles.append({
                    "title": a.get("title", ""),
                    "description": a.get("description", "") or "",
                    "source": a.get("source", {}).get("name", "unknown"),
                    "url": a.get("url", ""),
                    "published_at": a.get("publishedAt", "")
                })
            if articles:
                print(f"📰 [NEWS] Domain filter bypassed (free tier). Got {len(articles)} articles.", flush=True)
        except Exception as e2:
            print(f"⚠️ [NEWS] NewsAPI fetch error: {e2}", flush=True)

    return articles


def _fetch_rss_headlines():
    """
    Fetch headlines from configured RSS feeds as a fallback/supplement.
    """
    articles = []
    try:
        import feedparser
    except ImportError:
        print("⚠️ [NEWS] feedparser not installed. Skipping RSS.", flush=True)
        return articles

    for feed_url in NEWS_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                # Clean HTML from summary
                try:
                    from bs4 import BeautifulSoup
                    summary = BeautifulSoup(summary, "html.parser").get_text()
                except Exception:
                    pass

                articles.append({
                    "title": title,
                    "description": summary[:500],
                    "source": feed.feed.get("title", "RSS"),
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", "")
                })
        except Exception as e:
            print(f"⚠️ [NEWS] RSS error ({feed_url}): {e}", flush=True)

    return articles


def _score_headline(text):
    """
    Score a headline's sentiment using VADER (and optionally FinBERT).
    Returns: float from -1.0 (very bearish) to +1.0 (very bullish)
    """
    if _vader is None:
        return 0.0

    vader_score = _vader.polarity_scores(text)['compound']

    if SENTIMENT_MODE == "full" and _finbert_pipeline is not None:
        try:
            result = _finbert_pipeline(text[:512], truncation=True)[0]
            score_map = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
            finbert_s = score_map.get(result['label'], 0.0) * result['score']
            return (0.6 * finbert_s) + (0.4 * vader_score)
        except Exception:
            pass

    return vader_score


def _detect_event_type(text):
    """
    Classify a headline into an event category using pattern matching.
    Returns: list of matching event types (can be multi-label)
    """
    text_lower = text.lower()
    detected = []
    for event_type, patterns in _compiled_patterns.items():
        for pattern in patterns:
            if pattern.search(text_lower):
                detected.append(event_type)
                break  # One match per category is enough
    return detected


def _calculate_impact(event_types, score):
    """
    Determine the impact level based on event type and sentiment strength.
    """
    abs_score = abs(score)

    # Crisis and geopolitical events are inherently high-impact
    high_impact_events = {"market_crisis", "geopolitical"}
    if high_impact_events.intersection(event_types):
        if abs_score >= 0.5:
            return "extreme"
        return "high"

    # Monetary policy and inflation are medium-to-high
    if {"monetary_policy", "inflation"}.intersection(event_types):
        if abs_score >= 0.6:
            return "high"
        return "medium"

    # Everything else
    if abs_score >= 0.7:
        return "high"
    elif abs_score >= 0.4:
        return "medium"
    return "low"


def get_news_analysis():
    """
    Main entry point. Fetches news, classifies, scores, and returns analysis.
    Uses cache to respect API rate limits.

    Returns:
        dict: News analysis with bias, impact, events, and embargo status.
    """
    _initialize()

    # Check cache
    cached = cache.get("news_data")
    if cached is not None:
        return cached

    # Fetch from all sources
    all_articles = _fetch_newsapi_headlines() + _fetch_rss_headlines()

    # Deduplicate by title similarity
    seen_titles = set()
    unique_articles = []
    for a in all_articles:
        title_key = a['title'].lower().strip()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(a)

    # Analyze each headline
    analyzed = []
    for article in unique_articles:
        text = f"{article['title']}. {article['description']}"
        score = _score_headline(text)
        event_types = _detect_event_type(text)
        impact = _calculate_impact(event_types, score)

        # Determine affected symbols
        affected = set()
        for et in event_types:
            affected.update(EVENT_AFFECTED_SYMBOLS.get(et, []))

        if score > 0.1:
            sentiment_label = "bullish"
        elif score < -0.1:
            sentiment_label = "bearish"
        else:
            sentiment_label = "neutral"

        analyzed.append({
            "title": article['title'],
            "source": article['source'],
            "sentiment": sentiment_label,
            "score": round(score, 4),
            "event_types": event_types,
            "impact": impact,
            "affected_symbols": list(affected) if affected else ["XAUUSD"]
        })

    # Sort by absolute impact score (most impactful first)
    impact_order = {"extreme": 4, "high": 3, "medium": 2, "low": 1}
    analyzed.sort(key=lambda x: (impact_order.get(x['impact'], 0), abs(x['score'])), reverse=True)

    # Calculate aggregate bias
    if analyzed:
        total_score = sum(a['score'] for a in analyzed)
        avg_score = total_score / len(analyzed)
    else:
        avg_score = 0.0

    if avg_score > 0.1:
        overall_bias = "bullish"
    elif avg_score < -0.1:
        overall_bias = "bearish"
    else:
        overall_bias = "neutral"

    # Determine overall impact level
    impact_counts = {"extreme": 0, "high": 0, "medium": 0, "low": 0}
    for a in analyzed:
        impact_counts[a['impact']] = impact_counts.get(a['impact'], 0) + 1

    if impact_counts["extreme"] > 0:
        overall_impact = "extreme"
    elif impact_counts["high"] >= 3:
        overall_impact = "high"
    elif impact_counts["high"] >= 1 or impact_counts["medium"] >= 3:
        overall_impact = "medium"
    else:
        overall_impact = "low"

    # Check embargo from existing news_filter (preserving backward compat)
    embargo_active = False
    embargo_event = ""
    try:
        import news_filter
        embargo_active, embargo_event = news_filter.is_news_embargo()
    except Exception:
        pass

    result = {
        "headlines_analyzed": len(analyzed),
        "overall_bias": overall_bias,
        "bias_score": round(avg_score, 4),
        "impact_level": overall_impact,
        "top_events": analyzed[:10],  # Top 10 most impactful
        "embargo_active": embargo_active,
        "embargo_event": embargo_event,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }

    # Cache
    cache.set("news_data", result, NEWS_CACHE_TTL)
    print(f"📰 [NEWS] Bias: {result['overall_bias']} ({result['bias_score']:+.3f}) | "
          f"Impact: {result['impact_level']} | Headlines: {len(analyzed)} | "
          f"Embargo: {'YES' if embargo_active else 'no'}", flush=True)

    return result


def get_news_bias_score():
    """
    Convenience method. Returns just the numeric bias score (-1.0 to +1.0).
    Designed for direct injection into the ML feature vector.
    """
    data = get_news_analysis()
    return data["bias_score"]


def get_news_impact_numeric():
    """
    Returns impact as a numeric value for ML features.
    low=0.25, medium=0.50, high=0.75, extreme=1.0
    """
    data = get_news_analysis()
    impact_map = {"low": 0.25, "medium": 0.50, "high": 0.75, "extreme": 1.0}
    return impact_map.get(data["impact_level"], 0.25)

