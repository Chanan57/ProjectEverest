"""
Everest v8.0 — Social Sentiment Engine
Aggregates market sentiment from Reddit (and optionally Twitter/X).
Uses VADER for fast social-media-aware sentiment analysis.
Optional FinBERT mode for higher accuracy (requires torch + transformers).
"""
import time
from datetime import datetime
from collections import defaultdict

from config import (
    SENTIMENT_MODE, ENABLE_TWITTER, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT, SENTIMENT_SUBREDDITS, SENTIMENT_KEYWORDS,
    SENTIMENT_POSTS_PER_SUB, SENTIMENT_CACHE_TTL
)
from cache_manager import cache

# --- Lazy imports to avoid crashing if libs aren't installed yet ---
_praw = None
_vader = None
_finbert_pipeline = None
_initialized = False


def _init_nltk():
    """Download VADER lexicon on first use."""
    global _vader
    if _vader is not None:
        return
    try:
        import nltk
        nltk.download('vader_lexicon', quiet=True)
        from nltk.sentiment import SentimentIntensityAnalyzer
        _vader = SentimentIntensityAnalyzer()
    except Exception as e:
        print(f"⚠️ [SENTIMENT] Failed to init VADER: {e}", flush=True)


def _init_reddit():
    """Initialize PRAW Reddit client."""
    global _praw
    if _praw is not None:
        return
    if not REDDIT_CLIENT_ID or REDDIT_CLIENT_ID == "YOUR_REDDIT_CLIENT_ID":
        print("⚠️ [SENTIMENT] Reddit API credentials not configured. Skipping Reddit.", flush=True)
        return
    try:
        import praw
        _praw = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        # Verify connection
        _praw.user.me()  # Will be None for script apps, but won't error
        print("✅ [SENTIMENT] Reddit API connected.", flush=True)
    except Exception as e:
        print(f"⚠️ [SENTIMENT] Reddit connection failed: {e}", flush=True)
        _praw = None


def _init_finbert():
    """Load FinBERT model (only when SENTIMENT_MODE == 'full')."""
    global _finbert_pipeline
    if _finbert_pipeline is not None:
        return
    if SENTIMENT_MODE != "full":
        return
    try:
        from transformers import pipeline as hf_pipeline
        print("🧠 [SENTIMENT] Loading FinBERT model (first run takes ~60s)...", flush=True)
        _finbert_pipeline = hf_pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            device=-1  # Force CPU
        )
        print("✅ [SENTIMENT] FinBERT loaded.", flush=True)
    except Exception as e:
        print(f"⚠️ [SENTIMENT] FinBERT failed to load: {e}. Falling back to VADER.", flush=True)
        _finbert_pipeline = None


def _initialize():
    """One-time initialization of all sentiment components."""
    global _initialized
    if _initialized:
        return
    _init_nltk()
    _init_reddit()
    if SENTIMENT_MODE == "full":
        _init_finbert()
    _initialized = True


def _vader_score(text):
    """
    Score a single text string using VADER.
    Returns compound score: -1.0 (bearish) to +1.0 (bullish).
    """
    if _vader is None:
        return 0.0
    scores = _vader.polarity_scores(text)
    return scores['compound']


def _finbert_score(texts):
    """
    Score a batch of texts using FinBERT.
    Returns average score: -1.0 (bearish) to +1.0 (bullish).
    """
    if _finbert_pipeline is None or not texts:
        return 0.0
    try:
        results = _finbert_pipeline(texts[:64], truncation=True, max_length=512)
        score_map = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
        scores = [score_map.get(r['label'], 0.0) * r['score'] for r in results]
        return sum(scores) / len(scores) if scores else 0.0
    except Exception as e:
        print(f"⚠️ [SENTIMENT] FinBERT scoring error: {e}", flush=True)
        return 0.0


def _is_relevant(text):
    """Check if a post/comment contains any of our monitored keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in SENTIMENT_KEYWORDS)


def _fetch_reddit_data():
    """
    Fetch relevant posts from monitored subreddits.
    Returns list of dicts: {text, score, upvotes, comments, created}
    """
    if _praw is None:
        return []

    posts = []
    for sub_name in SENTIMENT_SUBREDDITS:
        try:
            subreddit = _praw.subreddit(sub_name)
            for post in subreddit.hot(limit=SENTIMENT_POSTS_PER_SUB):
                full_text = f"{post.title} {post.selftext or ''}"
                if _is_relevant(full_text):
                    posts.append({
                        "text": full_text[:1000],   # Truncate for performance
                        "upvotes": post.score,
                        "comments": post.num_comments,
                        "upvote_ratio": post.upvote_ratio,
                        "created_utc": post.created_utc,
                        "subreddit": sub_name
                    })
        except Exception as e:
            print(f"⚠️ [SENTIMENT] Error fetching r/{sub_name}: {e}", flush=True)
            continue

    return posts


def _calculate_volume_trend(posts):
    """
    Determine if social chatter is spiking, rising, stable, or declining.
    Based on recency-weighted post count.
    """
    if not posts:
        return "silent"

    now = time.time()
    recent_count = 0   # Posts in last 2 hours
    older_count = 0    # Posts in last 2-12 hours

    for p in posts:
        age_hours = (now - p['created_utc']) / 3600
        if age_hours <= 2:
            recent_count += 1
        elif age_hours <= 12:
            older_count += 1

    if recent_count == 0 and older_count == 0:
        return "silent"
    elif older_count == 0:
        return "spiking" if recent_count >= 5 else "rising"
    
    ratio = recent_count / max(older_count, 1)
    if ratio >= 3.0:
        return "spiking"
    elif ratio >= 1.5:
        return "rising"
    elif ratio >= 0.5:
        return "stable"
    else:
        return "declining"


def _calculate_engagement_weight(post):
    """
    Weight a post's sentiment by its engagement.
    High-engagement posts have more influence on the aggregate score.
    """
    # Logarithmic scaling to prevent a single viral post from dominating
    import math
    engagement = post['upvotes'] + (post['comments'] * 2)
    return max(1.0, math.log2(engagement + 1))


def get_sentiment():
    """
    Main entry point. Returns the full sentiment analysis dict.
    Uses cache to avoid hammering Reddit's API.

    Returns:
        dict: Sentiment analysis results with score, confidence, bias, etc.
    """
    _initialize()

    # Check cache first
    cached = cache.get("sentiment_data")
    if cached is not None:
        return cached

    # Fetch fresh data
    reddit_posts = _fetch_reddit_data()

    # Score each post with VADER
    scored_posts = []
    for post in reddit_posts:
        vader_s = _vader_score(post['text'])
        weight = _calculate_engagement_weight(post)
        scored_posts.append({
            **post,
            "vader_score": vader_s,
            "weight": weight
        })

    # Calculate weighted aggregate sentiment
    if scored_posts:
        total_weight = sum(p['weight'] for p in scored_posts)
        weighted_score = sum(p['vader_score'] * p['weight'] for p in scored_posts) / total_weight
    else:
        weighted_score = 0.0

    # Optional FinBERT refinement on aggregate texts
    finbert_score = 0.0
    if SENTIMENT_MODE == "full" and scored_posts:
        texts = [p['text'] for p in scored_posts[:32]]  # Cap at 32 for speed
        finbert_score = _finbert_score(texts)
        # Blend: 60% FinBERT (more accurate) + 40% VADER (more social-aware)
        weighted_score = (0.6 * finbert_score) + (0.4 * weighted_score)

    # Determine confidence
    post_count = len(scored_posts)
    if post_count >= 20:
        confidence = "high"
    elif post_count >= 8:
        confidence = "medium"
    else:
        confidence = "low"

    # Determine bias
    if weighted_score > 0.15:
        bias = "bullish"
    elif weighted_score < -0.15:
        bias = "bearish"
    else:
        bias = "neutral"

    # Compute average engagement
    avg_engagement = 0.0
    if scored_posts:
        avg_engagement = sum(p['upvotes'] + p['comments'] for p in scored_posts) / len(scored_posts)

    volume_trend = _calculate_volume_trend(scored_posts)

    result = {
        "symbol": "XAUUSD",
        "sentiment_score": round(weighted_score, 4),
        "confidence": confidence,
        "volume_trend": volume_trend,
        "bias": bias,
        "post_count": post_count,
        "avg_engagement": round(avg_engagement, 1),
        "source_breakdown": {
            "reddit": {
                "score": round(weighted_score, 4),
                "posts": post_count
            },
            "twitter": {
                "score": None,
                "posts": 0
            }
        },
        "finbert_score": round(finbert_score, 4) if SENTIMENT_MODE == "full" else None,
        "mode": SENTIMENT_MODE,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }

    # Cache result
    cache.set("sentiment_data", result, SENTIMENT_CACHE_TTL)
    print(f"📊 [SENTIMENT] Score: {result['sentiment_score']:+.3f} ({result['bias']}) | "
          f"Posts: {post_count} | Volume: {volume_trend} | Confidence: {confidence}", flush=True)

    return result


def get_sentiment_score():
    """
    Convenience method. Returns just the numeric score (-1.0 to +1.0).
    Designed for direct injection into the ML feature vector.
    """
    data = get_sentiment()
    return data["sentiment_score"]

