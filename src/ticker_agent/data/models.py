"""Pure dataclasses used as in-memory transfer objects throughout the system."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StockQuote:
    """Current price snapshot plus key fundamental metrics from yfinance."""

    symbol: str
    price: float
    open: float
    high: float
    low: float
    volume: int
    market_cap: float | None = None
    pe_ratio: float | None = None
    eps: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    avg_volume: int | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    sector: str | None = None
    industry: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tier: int = 0


@dataclass
class TechnicalSignals:
    """Computed technical indicators derived from OHLCV history."""

    symbol: str
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    volume_ratio: float | None = None          # current vol / 10-day avg
    price_vs_52wk_high_pct: float | None = None  # negative = below 52wk high
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NewsArticle:
    """A single news article fetched from NewsAPI."""

    symbol: str
    title: str
    source: str
    url: str
    published_at: datetime
    description: str = ""
    ai_summary: str | None = None
    sentiment_score: float | None = None  # -1.0 (bearish) to +1.0 (bullish)


@dataclass
class CompositeScore:
    """Final analysis result combining technical, fundamental, and sentiment scores."""

    symbol: str
    technical_score: float = 0.0    # 0–100
    fundamental_score: float = 0.0  # 0–100
    sentiment_score: float = 0.0    # 0–100 (mapped from -1..+1)
    composite_score: float = 0.0    # weighted average
    signal: str = "HOLD"            # STRONG_BUY | BUY | HOLD | SELL | STRONG_SELL
    confidence: float = 0.0         # 0.0–1.0
    reasoning: str = ""             # AI-generated prose
    generated_at: datetime = field(default_factory=datetime.utcnow)
