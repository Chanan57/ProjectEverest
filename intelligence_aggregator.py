"""
Everest v8.0 — Intelligence Aggregator
Combines Technical, ML, Sentiment, News, and Macro signals
into a single unified conviction score and alignment assessment.
This is the decision fusion layer between analysis and execution.
"""
from datetime import datetime

from config import (
    WEIGHT_TECHNICAL, WEIGHT_ML, WEIGHT_SENTIMENT,
    WEIGHT_NEWS, WEIGHT_MACRO, MIN_CONVICTION_TO_TRADE,
    RISK_MULT_ALIGNED, RISK_MULT_PARTIAL, RISK_MULT_CONFLICTING,
    RISK_MULT_DNT, WEIGHT_LLM_ADVISORY, LLM_MAX_CONFIDENCE_ADJUSTMENT
)


def _normalize_to_direction(value, direction="BUY"):
    """
    Normalize a score to align with trade direction.
    For BUY: positive values support, negative values oppose
    For SELL: flip the sign
    """
    if direction == "SELL":
        return -value
    return value


def compute_conviction(
    signal,
    prob_up,
    prob_down,
    trend_up,
    trend_down,
    sentiment_data=None,
    news_data=None,
    macro_data=None,
    llm_advisory=None
):
    """
    Compute the unified conviction score for a proposed trade.

    Args:
        signal: "BUY" or "SELL" — the proposed trade direction
        prob_up: ML probability of upward movement (0-1)
        prob_down: ML probability of downward movement (0-1)
        trend_up: bool — price above SMA200 and EMA50
        trend_down: bool — price below SMA200 and EMA50
        sentiment_data: output from sentiment_engine.get_sentiment()
        news_data: output from news_intelligence.get_news_analysis()
        macro_data: output from macro_engine.get_macro_regime()

    Returns:
        dict with conviction score, alignment, risk multiplier, reasoning, and flags
    """
    if signal is None:
        return _empty_result()

    components = {}
    directions = {}  # Track what each signal is saying: +1=BUY, -1=SELL, 0=neutral

    # --- 1. TECHNICAL SIGNAL ---
    if signal == "BUY" and trend_up:
        tech_score = 1.0
        directions["technical"] = 1
    elif signal == "SELL" and trend_down:
        tech_score = 1.0
        directions["technical"] = -1
    elif signal == "BUY" and not trend_up:
        tech_score = 0.3   # Signal present but trend not fully confirmed
        directions["technical"] = 0
    elif signal == "SELL" and not trend_down:
        tech_score = 0.3
        directions["technical"] = 0
    else:
        tech_score = 0.5
        directions["technical"] = 0

    components["technical"] = {
        "score": tech_score,
        "weight": WEIGHT_TECHNICAL,
        "weighted": tech_score * WEIGHT_TECHNICAL
    }

    # --- 2. ML PREDICTION ---
    if signal == "BUY":
        ml_score = prob_up
        directions["ml"] = 1 if prob_up > 0.55 else (-1 if prob_down > 0.55 else 0)
    else:
        ml_score = prob_down
        directions["ml"] = -1 if prob_down > 0.55 else (1 if prob_up > 0.55 else 0)

    components["ml"] = {
        "score": ml_score,
        "weight": WEIGHT_ML,
        "weighted": ml_score * WEIGHT_ML
    }

    # --- 3. SENTIMENT ---
    sent_score = 0.5  # Neutral default
    if sentiment_data:
        raw_sentiment = sentiment_data.get("sentiment_score", 0.0)
        # Convert from [-1, +1] range to [0, 1] aligned with signal direction
        if signal == "BUY":
            sent_score = (raw_sentiment + 1.0) / 2.0  # Bullish sentiment = high score
            directions["sentiment"] = 1 if raw_sentiment > 0.15 else (-1 if raw_sentiment < -0.15 else 0)
        else:
            sent_score = (-raw_sentiment + 1.0) / 2.0  # Bearish sentiment = high score for SELL
            directions["sentiment"] = -1 if raw_sentiment < -0.15 else (1 if raw_sentiment > 0.15 else 0)

    components["sentiment"] = {
        "score": round(sent_score, 4),
        "weight": WEIGHT_SENTIMENT,
        "weighted": round(sent_score * WEIGHT_SENTIMENT, 4)
    }

    # --- 4. NEWS ---
    news_score = 0.5  # Neutral default
    if news_data:
        raw_news = news_data.get("bias_score", 0.0)
        if signal == "BUY":
            news_score = (raw_news + 1.0) / 2.0
            directions["news"] = 1 if raw_news > 0.1 else (-1 if raw_news < -0.1 else 0)
        else:
            news_score = (-raw_news + 1.0) / 2.0
            directions["news"] = -1 if raw_news < -0.1 else (1 if raw_news > 0.1 else 0)

    components["news"] = {
        "score": round(news_score, 4),
        "weight": WEIGHT_NEWS,
        "weighted": round(news_score * WEIGHT_NEWS, 4)
    }

    # --- 5. MACRO REGIME ---
    macro_score = 0.5  # Neutral default
    if macro_data:
        gold_bias = macro_data.get("gold_bias", "neutral")
        regime_conf = macro_data.get("confidence", 0.5)

        if signal == "BUY":
            if gold_bias == "bullish":
                macro_score = 0.5 + (regime_conf * 0.5)
                directions["macro"] = 1
            elif gold_bias == "bearish":
                macro_score = 0.5 - (regime_conf * 0.5)
                directions["macro"] = -1
            else:
                macro_score = 0.5
                directions["macro"] = 0
        else:  # SELL
            if gold_bias == "bearish":
                macro_score = 0.5 + (regime_conf * 0.5)
                directions["macro"] = -1
            elif gold_bias == "bullish":
                macro_score = 0.5 - (regime_conf * 0.5)
                directions["macro"] = 1
            else:
                macro_score = 0.5
                directions["macro"] = 0

    components["macro"] = {
        "score": round(macro_score, 4),
        "weight": WEIGHT_MACRO,
        "weighted": round(macro_score * WEIGHT_MACRO, 4)
    }

    # --- FINAL CONVICTION SCORE ---
    conviction = sum(c["weighted"] for c in components.values())
    conviction = round(max(0.0, min(1.0, conviction)), 4)

    # --- v9.0: LLM ADVISORY ADJUSTMENT ---
    llm_adjustment = 0.0
    llm_reasoning = None
    if llm_advisory and WEIGHT_LLM_ADVISORY > 0:
        raw_adj = llm_advisory.get("confidence_adjustment", 0.0)
        # Hard-clamp the adjustment to prevent runaway influence
        llm_adjustment = max(-LLM_MAX_CONFIDENCE_ADJUSTMENT,
                            min(LLM_MAX_CONFIDENCE_ADJUSTMENT, raw_adj))
        llm_adjustment = round(llm_adjustment * WEIGHT_LLM_ADVISORY / 0.10, 4)  # Scale by weight
        conviction = round(max(0.0, min(1.0, conviction + llm_adjustment)), 4)
        llm_reasoning = llm_advisory.get("reasoning", "")

        # If LLM flags risk, downgrade alignment by one tier
        if llm_advisory.get("risk_flag", False):
            if alignment == "strong":
                alignment = "aligned"
            elif alignment == "aligned":
                alignment = "partial"
            reasoning_parts.append("⚠️ LLM risk flag active")

    # --- ALIGNMENT ASSESSMENT ---
    trade_direction = 1 if signal == "BUY" else -1
    agreeing = sum(1 for d in directions.values() if d == trade_direction)
    opposing = sum(1 for d in directions.values() if d == -trade_direction)
    total_opinions = len(directions)

    if agreeing >= 4:
        alignment = "strong"
    elif agreeing >= 3:
        alignment = "aligned"
    elif opposing >= 3:
        alignment = "conflicting"
    elif agreeing >= 2 and opposing <= 1:
        alignment = "partial"
    else:
        alignment = "mixed"

    # --- RISK MULTIPLIER ---
    if macro_data and macro_data.get("do_not_trade", False):
        risk_mult = RISK_MULT_DNT
    elif alignment in ["strong", "aligned"]:
        risk_mult = RISK_MULT_ALIGNED
    elif alignment == "partial":
        risk_mult = RISK_MULT_PARTIAL
    elif alignment == "conflicting":
        risk_mult = RISK_MULT_CONFLICTING
    else:
        risk_mult = RISK_MULT_PARTIAL

    # Apply macro regime modifier
    if macro_data:
        macro_mult = macro_data.get("risk_multiplier", 1.0)
        risk_mult = round(risk_mult * macro_mult, 2)

    # --- TRADE PERMISSION ---
    should_trade = True
    block_reasons = []

    if conviction < MIN_CONVICTION_TO_TRADE:
        should_trade = False
        block_reasons.append(f"Conviction {conviction:.2f} < threshold {MIN_CONVICTION_TO_TRADE}")

    if macro_data and macro_data.get("do_not_trade", False):
        should_trade = False
        block_reasons.append("Macro Do-Not-Trade mode active")

    if alignment == "conflicting" and conviction < 0.5:
        should_trade = False
        block_reasons.append("Conflicting signals with low conviction")

    # --- BUILD REASONING ---
    reasoning_parts = []
    for name, comp in components.items():
        reasoning_parts.append(f"{name}: {comp['score']:.2f}×{comp['weight']:.2f}={comp['weighted']:.3f}")

    if macro_data:
        reasoning_parts.append(f"Regime: {macro_data.get('market_regime', 'unknown')}")
    if sentiment_data:
        reasoning_parts.append(f"Social: {sentiment_data.get('bias', 'n/a')}")

    result = {
        "conviction": conviction,
        "alignment": alignment,
        "risk_multiplier": risk_mult,
        "should_trade": should_trade,
        "block_reasons": block_reasons,
        "signal": signal,
        "components": components,
        "directions": directions,
        "reasoning": " | ".join(reasoning_parts),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        # v9.0: LLM advisory data
        "llm_adjustment": llm_adjustment,
        "llm_reasoning": llm_reasoning,
        "llm_assessment": llm_advisory.get("assessment") if llm_advisory else None
    }

    return result


def _empty_result():
    """Return a neutral result when no signal is present."""
    return {
        "conviction": 0.0,
        "alignment": "none",
        "risk_multiplier": 0.0,
        "should_trade": False,
        "block_reasons": ["No signal"],
        "signal": None,
        "components": {},
        "directions": {},
        "reasoning": "No signal to evaluate",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }


def format_conviction_summary(result):
    """
    Returns a compact human-readable string for the dashboard/Telegram.
    """
    if result["signal"] is None:
        return "No signal"

    c = result["conviction"]
    a = result["alignment"]
    r = result["risk_multiplier"]
    s = result["signal"]

    # Conviction bar visualization
    filled = int(c * 10)
    bar = "█" * filled + "░" * (10 - filled)

    status = "✅ GO" if result["should_trade"] else "⛔ BLOCKED"
    blocks = f" ({', '.join(result['block_reasons'])})" if result['block_reasons'] else ""

    return f"{s} [{bar}] {c:.0%} | {a.upper()} | Risk×{r:.2f} | {status}{blocks}"

