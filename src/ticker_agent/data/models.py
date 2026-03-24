"""SQLAlchemy ORM models for the ticker agent database."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TickerSnapshot(Base):
    """Point-in-time price + fundamental snapshot for one ticker."""

    __tablename__ = "ticker_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Price
    price: Mapped[float | None] = mapped_column(Float)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    prev_close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)

    # Fundamental (from yfinance info)
    market_cap: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    forward_pe: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    revenue_ttm: Mapped[float | None] = mapped_column(Float)
    profit_margin: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    roe: Mapped[float | None] = mapped_column(Float)
    dividend_yield: Mapped[float | None] = mapped_column(Float)
    beta: Mapped[float | None] = mapped_column(Float)
    week_52_high: Mapped[float | None] = mapped_column(Float)
    week_52_low: Mapped[float | None] = mapped_column(Float)

    analyses: Mapped[list[AnalysisResult]] = relationship(
        "AnalysisResult", back_populates="snapshot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TickerSnapshot ticker={self.ticker} price={self.price} at={self.captured_at}>"


class NewsArticle(Base):
    """A news article fetched from NewsAPI for a specific ticker."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1024))
    source: Mapped[str | None] = mapped_column(String(128))

    # LLM-derived sentiment: "bullish" | "bearish" | "neutral"
    sentiment: Mapped[str | None] = mapped_column(String(16))
    sentiment_score: Mapped[float | None] = mapped_column(Float)  # -1.0 to +1.0

    def __repr__(self) -> str:
        return f"<NewsArticle ticker={self.ticker} title={self.title[:40]!r}>"


class AnalysisResult(Base):
    """Composite analysis + LLM narrative for one snapshot."""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("ticker_snapshots.id"), index=True)
    analysed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    # Composite scores (0–100)
    technical_score: Mapped[float | None] = mapped_column(Float)
    fundamental_score: Mapped[float | None] = mapped_column(Float)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    composite_score: Mapped[float | None] = mapped_column(Float)

    signal: Mapped[str | None] = mapped_column(String(16))  # STRONG_BUY … STRONG_SELL
    llm_summary: Mapped[str | None] = mapped_column(Text)

    # Raw indicators stored as JSON for downstream viz
    technical_indicators: Mapped[dict | None] = mapped_column(JSON)
    fundamental_metrics: Mapped[dict | None] = mapped_column(JSON)

    snapshot: Mapped[TickerSnapshot] = relationship("TickerSnapshot", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<AnalysisResult ticker={self.ticker} score={self.composite_score} signal={self.signal}>"


class Alert(Base):
    """Fired alert record."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    alert_type: Mapped[str] = mapped_column(String(32))   # PRICE_SPIKE, SIGNAL_CHANGE, …
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Alert ticker={self.ticker} type={self.alert_type}>"
