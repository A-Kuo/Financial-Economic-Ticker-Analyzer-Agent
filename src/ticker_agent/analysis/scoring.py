"""Composite scoring: convert component scores into a final signal."""
from __future__ import annotations

from datetime import datetime

from ticker_agent.config import ScoringWeights
from ticker_agent.data.models import CompositeScore, TechnicalSignals


def score_technical(signals: TechnicalSignals) -> float:
    """
    Convert TechnicalSignals into a 0–100 score via majority voting.

    Each indicator casts a vote:
      > 60 → bullish bias
      ~50  → neutral
      < 40 → bearish bias
    """
    votes: list[float] = []

    # RSI
    if signals.rsi_14 is not None:
        rsi = signals.rsi_14
        if rsi < 30:
            votes.append(88.0)   # oversold — strong bullish
        elif rsi < 40:
            votes.append(70.0)   # approaching oversold
        elif rsi < 60:
            votes.append(50.0)   # neutral momentum
        elif rsi < 70:
            votes.append(35.0)   # approaching overbought
        else:
            votes.append(20.0)   # overbought — bearish

    # MACD histogram direction + zero-line cross
    if signals.macd_histogram is not None and signals.macd is not None:
        hist = signals.macd_histogram
        macd_val = signals.macd
        if hist > 0 and macd_val > 0:
            votes.append(72.0)   # strong uptrend
        elif hist > 0:
            votes.append(60.0)   # building momentum
        elif hist < 0 and macd_val < 0:
            votes.append(28.0)   # strong downtrend
        else:
            votes.append(40.0)   # losing momentum

    # Short-term SMA trend (20 vs 50)
    if signals.sma_20 and signals.sma_50:
        if signals.sma_20 > signals.sma_50:
            votes.append(65.0)   # short-term uptrend
        else:
            votes.append(35.0)   # short-term downtrend

    # Long-term SMA trend: golden/death cross (50 vs 200)
    if signals.sma_50 and signals.sma_200:
        if signals.sma_50 > signals.sma_200:
            votes.append(68.0)   # golden cross territory
        else:
            votes.append(32.0)   # death cross territory

    # Volume confirmation
    if signals.volume_ratio is not None:
        vr = signals.volume_ratio
        if vr > 2.0:
            votes.append(60.0)   # high volume — confirms move (directionally neutral here)
        elif vr > 1.5:
            votes.append(55.0)
        elif vr < 0.5:
            votes.append(45.0)   # very low volume — weak conviction

    return round(sum(votes) / len(votes), 2) if votes else 50.0


def signal_from_score(composite: float) -> tuple[str, float]:
    """Map a 0–100 composite score to a signal string and confidence value."""
    if composite >= 75:
        return "STRONG_BUY", min(1.0, 0.60 + (composite - 75) / 25 * 0.40)
    if composite >= 60:
        return "BUY", 0.40 + (composite - 60) / 15 * 0.20
    if composite >= 40:
        return "HOLD", 0.50
    if composite >= 25:
        return "SELL", 0.40 + (40 - composite) / 15 * 0.20
    return "STRONG_SELL", min(1.0, 0.60 + (25 - composite) / 25 * 0.40)


def compute_composite_score(
    symbol: str,
    technical_score: float,
    fundamental_score: float,
    sentiment_score: float,
    weights: ScoringWeights,
    reasoning: str = "",
) -> CompositeScore:
    """Combine component scores into the final CompositeScore."""
    composite = round(
        technical_score * weights.technical
        + fundamental_score * weights.fundamental
        + sentiment_score * weights.sentiment,
        2,
    )
    signal, confidence = signal_from_score(composite)
    return CompositeScore(
        symbol=symbol,
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        sentiment_score=sentiment_score,
        composite_score=composite,
        signal=signal,
        confidence=round(confidence, 2),
        reasoning=reasoning,
        generated_at=datetime.utcnow(),
    )
