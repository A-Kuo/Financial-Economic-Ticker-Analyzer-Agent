"""Composite scoring engine — blends technical, fundamental, and sentiment scores."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ticker_agent.config import get

logger = logging.getLogger(__name__)

SIGNALS = {
    (80, 101): "STRONG_BUY",
    (60, 80):  "BUY",
    (40, 60):  "HOLD",
    (20, 40):  "SELL",
    (0,  20):  "STRONG_SELL",
}


def _signal_from_score(score: float) -> str:
    for (low, high), label in SIGNALS.items():
        if low <= score < high:
            return label
    return "HOLD"


@dataclass
class CompositeScore:
    ticker: str
    technical_score: float
    fundamental_score: float
    sentiment_score: float
    composite_score: float
    signal: str
    confidence: str  # HIGH / MEDIUM / LOW based on data availability


def compute(
    ticker: str,
    technical_score: float | None,
    fundamental_score: float | None,
    sentiment_score: float | None,
) -> CompositeScore:
    """Blend three sub-scores into a single composite using configured weights.

    Missing sub-scores are replaced with 50 (neutral) and the confidence is
    downgraded to MEDIUM or LOW accordingly.
    """
    cfg = get("analysis.scoring", {})
    w_tech = cfg.get("technical_weight", 0.40)
    w_fund = cfg.get("fundamental_weight", 0.35)
    w_sent = cfg.get("sentiment_weight", 0.25)

    missing = sum(1 for s in (technical_score, fundamental_score, sentiment_score) if s is None)

    t = technical_score if technical_score is not None else 50.0
    f = fundamental_score if fundamental_score is not None else 50.0
    s = sentiment_score if sentiment_score is not None else 50.0

    composite = round(t * w_tech + f * w_fund + s * w_sent, 1)
    signal = _signal_from_score(composite)

    if missing == 0:
        confidence = "HIGH"
    elif missing == 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return CompositeScore(
        ticker=ticker,
        technical_score=round(t, 1),
        fundamental_score=round(f, 1),
        sentiment_score=round(s, 1),
        composite_score=composite,
        signal=signal,
        confidence=confidence,
    )


def technical_score_from_indicators(ind) -> float:
    """Convert a :class:`TechnicalIndicators` object to a 0-100 score."""
    if ind is None:
        return 50.0

    points = 0.0
    total = 0.0

    # RSI (25 pts)
    if ind.rsi is not None:
        total += 25
        if 40 <= ind.rsi <= 60:
            points += 25        # neutral zone — neither overbought nor oversold
        elif ind.rsi < 30:
            points += 20        # oversold = buying opportunity
        elif ind.rsi > 70:
            points += 5         # overbought
        else:
            points += 15

    # MACD (20 pts)
    if ind.macd_histogram is not None:
        total += 20
        if ind.macd_histogram > 0:
            points += 20
        elif ind.macd_bullish:
            points += 15

    # Price vs SMAs (25 pts)
    if ind.price_vs_sma_short_pct is not None:
        total += 12
        if ind.price_vs_sma_short_pct > 0:
            points += 12
    if ind.price_vs_sma_long_pct is not None:
        total += 13
        if ind.price_vs_sma_long_pct > 0:
            points += 13

    # Golden/Death cross bonus (15 pts)
    total += 15
    if ind.golden_cross:
        points += 15
    elif ind.death_cross:
        points += 0
    else:
        points += 7  # no cross — neutral

    # Bollinger Bands (15 pts)
    if ind.bb_percent_b is not None:
        total += 15
        if 0.2 <= ind.bb_percent_b <= 0.8:
            points += 15       # price inside bands — healthy
        elif ind.below_bb_lower:
            points += 10       # oversold signal
        else:
            points += 3

    if total == 0:
        return 50.0
    return round(min(points / total * 100, 100), 1)
