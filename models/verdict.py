from typing import Any, Dict, Literal


VerdictLabel = Literal["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]


def compute_verdict(
    dcf_result: Dict[str, Any],
    pe_valuation: Dict[str, Any],
    sentiment_score: float,
    analyst_avg_target: float = None,
) -> Dict[str, Any]:
    """
    Computes a weighted Buy/Hold/Sell verdict based on multiple signals.
    
    Weights:
    - DCF upside: 40%
    - P/E ratio: 25%
    - News sentiment: 20%
    - Analyst targets: 15%
    
    Score 1-5: Strong Sell to Strong Buy
    """
    scores = {}
    weights = {}

    # 1. DCF Upside Score (40%)
    upside_pct = dcf_result.get("upside_pct", 0)
    dcf_score = _score_dcf(upside_pct)
    scores["dcf"] = dcf_score
    weights["dcf"] = 0.40

    # 2. P/E Ratio Score (25%)
    pe_score = pe_valuation.get("score")
    if pe_score is not None:
        scores["pe"] = pe_score
        weights["pe"] = 0.25

    # 3. Sentiment Score (20%)
    if sentiment_score is not None:
        sent_score = _score_sentiment(sentiment_score)
        scores["sentiment"] = sent_score
        weights["sentiment"] = 0.20

    # 4. Analyst Target Score (15%)
    current_price = dcf_result.get("current_price", 0)
    if analyst_avg_target is not None and current_price > 0:
        analyst_score = _score_analyst(analyst_avg_target, current_price)
        scores["analyst"] = analyst_score
        weights["analyst"] = 0.15

    # Compute weighted average
    total_weight = sum(weights.values())
    if total_weight == 0:
        weighted_score = 3.0  # Neutral default
    else:
        weighted_score = sum(
            scores[k] * weights[k] for k in scores
        ) / total_weight

    # Map to verdict label
    verdict = _score_to_verdict(weighted_score)

    return {
        "verdict": verdict,
        "score": round(weighted_score, 1),
        "components": scores,
        "weights": weights,
        "max_score": 5,
    }


def _score_dcf(upside_pct: float) -> float:
    """
    Scores DCF upside: >50% = 5, 20-50% = 4, -20-20% = 3, -50--20% = 2, <-50% = 1
    """
    if upside_pct > 0.50:
        return 5.0
    elif upside_pct > 0.20:
        return 4.0
    elif upside_pct > -0.20:
        return 3.0
    elif upside_pct > -0.50:
        return 2.0
    else:
        return 1.0


def _score_sentiment(sentiment: float) -> float:
    """
    Scores news sentiment: 1.0 = 5, 0.5 = 4, 0 = 3, -0.5 = 2, -1.0 = 1
    """
    if sentiment > 0.5:
        return 5.0
    elif sentiment > 0.2:
        return 4.0
    elif sentiment > -0.2:
        return 3.0
    elif sentiment > -0.5:
        return 2.0
    else:
        return 1.0


def _score_analyst(target: float, current: float) -> float:
    """
    Scores analyst target vs current price.
    """
    upside = (target - current) / current
    if upside > 0.30:
        return 5.0
    elif upside > 0.15:
        return 4.0
    elif upside > -0.10:
        return 3.0
    elif upside > -0.25:
        return 2.0
    else:
        return 1.0


def _score_to_verdict(score: float) -> VerdictLabel:
    """
    Maps a 1-5 score to a verdict label.
    """
    if score >= 4.5:
        return "Strong Buy"
    elif score >= 3.5:
        return "Buy"
    elif score >= 2.5:
        return "Hold"
    elif score >= 1.5:
        return "Sell"
    else:
        return "Strong Sell"
