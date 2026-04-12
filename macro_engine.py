"""
Everest v8.0 — Macro Narrative Engine
Synthesizes sentiment, news, and technical data into a market regime classification.
This is the key differentiator — it understands WHY the market is moving.
"""
from datetime import datetime

from config import MACRO_CACHE_TTL, ADX_THRESHOLD
from cache_manager import cache

# --- Market Regime Definitions ---
# Each regime defines: description, gold_bias, risk_multiplier
REGIME_PROFILES = {
    "risk_off": {
        "description": "Fear dominant. Safe-haven demand rising.",
        "gold_bias": "bullish",
        "risk_multiplier": 1.15,
        "preferred_assets": ["gold", "USD", "JPY", "CHF"],
        "avoid_assets": ["stocks", "AUD", "NZD", "emerging_markets"]
    },
    "risk_on": {
        "description": "Confidence high. Risk appetite expanding.",
        "gold_bias": "bearish",
        "risk_multiplier": 0.85,
        "preferred_assets": ["stocks", "AUD", "NZD"],
        "avoid_assets": ["gold", "JPY"]
    },
    "inflation_fear": {
        "description": "Inflation expectations rising. Real rates declining.",
        "gold_bias": "bullish",
        "risk_multiplier": 1.10,
        "preferred_assets": ["gold", "commodities", "TIPS"],
        "avoid_assets": ["bonds", "growth_stocks"]
    },
    "rate_hike": {
        "description": "Central bank tightening cycle. Strong dollar environment.",
        "gold_bias": "bearish",
        "risk_multiplier": 0.80,
        "preferred_assets": ["USD", "short_bonds"],
        "avoid_assets": ["gold", "emerging_markets"]
    },
    "geopolitical_crisis": {
        "description": "War, sanctions, or geopolitical instability.",
        "gold_bias": "bullish",
        "risk_multiplier": 1.20,
        "preferred_assets": ["gold", "USD", "JPY", "oil"],
        "avoid_assets": ["stocks", "emerging_markets"]
    },
    "uncertainty": {
        "description": "Mixed signals. No clear macro narrative.",
        "gold_bias": "neutral",
        "risk_multiplier": 0.60,
        "preferred_assets": ["cash", "short_duration"],
        "avoid_assets": ["leveraged_positions"]
    },
    "normal": {
        "description": "No dominant macro theme. Trade on technicals.",
        "gold_bias": "neutral",
        "risk_multiplier": 1.00,
        "preferred_assets": [],
        "avoid_assets": []
    }
}


def _classify_regime(sentiment_data, news_data, adx=None, atr=None):
    """
    Core classification logic. Determines the current market regime
    by analyzing the combination of sentiment, news, and technical signals.

    Uses a scoring system where each data point votes for a regime.
    The regime with the highest vote count wins.
    """
    votes = {regime: 0.0 for regime in REGIME_PROFILES}
    reasoning_parts = []

    # --- 1. NEWS EVENT ANALYSIS ---
    if news_data:
        impact = news_data.get("impact_level", "low")
        news_bias = news_data.get("bias_score", 0.0)
        top_events = news_data.get("top_events", [])

        # Check for specific event types in the top events
        event_type_counts = {}
        for event in top_events[:5]:  # Only top 5 most impactful
            for et in event.get("event_types", []):
                event_type_counts[et] = event_type_counts.get(et, 0) + 1

        # Geopolitical crisis detection
        if event_type_counts.get("geopolitical", 0) >= 2 or (
            event_type_counts.get("geopolitical", 0) >= 1 and impact in ["high", "extreme"]
        ):
            votes["geopolitical_crisis"] += 3.0
            reasoning_parts.append("Multiple geopolitical headlines detected")

        # Market crisis detection
        if event_type_counts.get("market_crisis", 0) >= 1:
            votes["risk_off"] += 2.5
            reasoning_parts.append("Market crisis indicators in headlines")

        # Monetary policy regime
        if event_type_counts.get("monetary_policy", 0) >= 2:
            if news_bias < -0.2:
                votes["rate_hike"] += 2.5
                reasoning_parts.append("Hawkish monetary policy signals")
            elif news_bias > 0.2:
                votes["risk_on"] += 1.5
                reasoning_parts.append("Dovish monetary policy signals")

        # Inflation regime
        if event_type_counts.get("inflation", 0) >= 2:
            votes["inflation_fear"] += 2.5
            reasoning_parts.append("Inflation concerns dominating headlines")

        # Safe haven demand
        if event_type_counts.get("safe_haven", 0) >= 1:
            votes["risk_off"] += 2.0
            reasoning_parts.append("Safe-haven demand in headlines")

        # News embargo adds uncertainty
        if news_data.get("embargo_active", False):
            votes["uncertainty"] += 1.5
            reasoning_parts.append(f"News embargo: {news_data.get('embargo_event', 'unknown')}")

        # Extreme impact = increased uncertainty or directional bias
        if impact == "extreme":
            votes["uncertainty"] += 1.0

    # --- 2. SOCIAL SENTIMENT ANALYSIS ---
    if sentiment_data:
        sent_score = sentiment_data.get("sentiment_score", 0.0)
        sent_confidence = sentiment_data.get("confidence", "low")
        volume_trend = sentiment_data.get("volume_trend", "stable")

        # Strong bullish social sentiment → risk-off (gold is fear-driven)
        if sent_score > 0.3 and sent_confidence in ["high", "medium"]:
            votes["risk_off"] += 1.5
            reasoning_parts.append(f"Strong bullish gold sentiment ({sent_score:+.2f})")

        # Strong bearish social sentiment → risk-on
        elif sent_score < -0.3 and sent_confidence in ["high", "medium"]:
            votes["risk_on"] += 1.5
            reasoning_parts.append(f"Bearish gold sentiment ({sent_score:+.2f})")

        # Volume spike amplifies whatever regime is emerging
        if volume_trend == "spiking":
            # Find the current leading regime and boost it
            if votes:
                leading = max(votes, key=votes.get)
                if votes[leading] > 0:
                    votes[leading] += 1.0
                    reasoning_parts.append("Social volume spiking — amplifying signal")

        # Low confidence + low volume = normal/uncertain
        if sent_confidence == "low" and volume_trend in ["silent", "declining"]:
            votes["normal"] += 1.0

    # --- 3. TECHNICAL CONTEXT ---
    if adx is not None:
        if adx < ADX_THRESHOLD:
            votes["uncertainty"] += 1.0
            votes["normal"] += 0.5
        elif adx > 35:
            # Strong trend — the market has conviction, reduce uncertainty
            votes["uncertainty"] -= 1.0

    # --- 4. DETERMINE WINNING REGIME ---
    # If no signal has meaningful votes, default to "normal"
    max_votes = max(votes.values()) if votes else 0
    if max_votes < 1.5:
        regime = "normal"
        confidence = 0.3
        reasoning_parts.append("No dominant macro narrative — defaulting to normal")
    else:
        regime = max(votes, key=votes.get)
        # Calculate confidence based on margin between top two
        sorted_votes = sorted(votes.values(), reverse=True)
        margin = sorted_votes[0] - sorted_votes[1] if len(sorted_votes) > 1 else sorted_votes[0]
        confidence = min(0.95, 0.4 + (margin * 0.1))

    # --- 5. DO-NOT-TRADE CHECK ---
    do_not_trade = False
    if regime == "geopolitical_crisis" and confidence > 0.7:
        # During confirmed crises, we may want to sit out entirely
        # But for gold, crises are actually bullish — so we only DNT for extreme uncertainty
        pass
    if regime == "uncertainty" and confidence > 0.8:
        do_not_trade = True
        reasoning_parts.append("⛔ Extreme uncertainty — Do Not Trade mode ACTIVE")

    # Check for extreme news impact
    if news_data and news_data.get("impact_level") == "extreme":
        if regime in ["uncertainty", "geopolitical_crisis"]:
            do_not_trade = True
            reasoning_parts.append("⛔ Extreme-impact event — Do Not Trade mode ACTIVE")

    profile = REGIME_PROFILES[regime]
    reasoning = ". ".join(reasoning_parts) if reasoning_parts else "Insufficient data for narrative."

    return {
        "market_regime": regime,
        "confidence": round(confidence, 2),
        "preferred_assets": profile["preferred_assets"],
        "avoid_assets": profile["avoid_assets"],
        "gold_bias": profile["gold_bias"],
        "risk_multiplier": profile["risk_multiplier"],
        "do_not_trade": do_not_trade,
        "description": profile["description"],
        "reasoning": reasoning,
        "vote_breakdown": {k: round(v, 2) for k, v in votes.items() if v != 0},
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }


def get_macro_regime(sentiment_data=None, news_data=None, adx=None, atr=None):
    """
    Main entry point. Returns the full macro regime classification.
    Uses cache to avoid redundant computation.

    Args:
        sentiment_data: Output from sentiment_engine.get_sentiment()
        news_data: Output from news_intelligence.get_news_analysis()
        adx: Current ADX value from technical indicators
        atr: Current ATR value from technical indicators

    Returns:
        dict: Market regime classification with confidence, bias, and risk multiplier.
    """
    # Check cache
    cached = cache.get("macro_regime")
    if cached is not None:
        return cached

    # Fetch dependencies if not provided
    if sentiment_data is None:
        try:
            from sentiment_engine import get_sentiment
            sentiment_data = get_sentiment()
        except Exception as e:
            print(f"⚠️ [MACRO] Could not fetch sentiment: {e}", flush=True)
            sentiment_data = {}

    if news_data is None:
        try:
            from news_intelligence import get_news_analysis
            news_data = get_news_analysis()
        except Exception as e:
            print(f"⚠️ [MACRO] Could not fetch news: {e}", flush=True)
            news_data = {}

    # Classify
    result = _classify_regime(sentiment_data, news_data, adx, atr)

    # Cache
    cache.set("macro_regime", result, MACRO_CACHE_TTL)

    emoji_map = {
        "risk_off": "🛡️", "risk_on": "📈", "inflation_fear": "🔥",
        "rate_hike": "🏦", "geopolitical_crisis": "⚠️",
        "uncertainty": "❓", "normal": "➡️"
    }
    emoji = emoji_map.get(result["market_regime"], "➡️")

    print(f"{emoji} [MACRO] Regime: {result['market_regime'].upper()} "
          f"(conf: {result['confidence']:.0%}) | Gold Bias: {result['gold_bias']} | "
          f"Risk Mult: {result['risk_multiplier']:.2f}"
          f"{' | ⛔ DNT' if result['do_not_trade'] else ''}", flush=True)

    return result


def get_risk_multiplier(sentiment_data=None, news_data=None, adx=None, atr=None):
    """
    Convenience method. Returns just the risk multiplier (float).
    """
    regime = get_macro_regime(sentiment_data, news_data, adx, atr)
    return regime["risk_multiplier"]


def get_gold_bias(sentiment_data=None, news_data=None, adx=None, atr=None):
    """
    Convenience method. Returns gold bias as a numeric value.
    bullish=+1.0, neutral=0.0, bearish=-1.0
    """
    regime = get_macro_regime(sentiment_data, news_data, adx, atr)
    bias_map = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}
    return bias_map.get(regime["gold_bias"], 0.0)

