"""Master pipeline orchestrator — fetch → analyse → score → alert."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ticker_agent.analysis.fundamental import compute_fundamental_score
from ticker_agent.analysis.scoring import compute_composite_score, score_technical
from ticker_agent.analysis.technical import compute_signals
from ticker_agent.agents.analysis_agent import AnalysisAgent
from ticker_agent.agents.news_agent import NewsAgent
from ticker_agent.config import AppConfig
from ticker_agent.data.models import CompositeScore, NewsArticle, StockQuote, TechnicalSignals
from ticker_agent.data.news_fetcher import NewsFetcher
from ticker_agent.data.stock_fetcher import StockFetcher

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Full output of one ticker's analysis pass."""

    symbol: str
    quote: StockQuote | None
    signals: TechnicalSignals | None
    articles: list[NewsArticle] = field(default_factory=list)
    news_summary: str = ""
    sentiment_score: float = 0.0
    reasoning: str = ""
    score: CompositeScore | None = None
    alerts_fired: list[str] = field(default_factory=list)
    error: str | None = None


class Orchestrator:
    """
    Coordinates the full analysis pipeline for one or more tickers.

    Pipeline per ticker:
      1. Fetch current quote (yfinance)
      2. Fetch OHLCV history → compute TechnicalSignals
      3. Fetch news articles (NewsAPI)
      4. NewsAgent → AI summary + sentiment score
      5. AnalysisAgent → AI reasoning prose
      6. Score all three components → CompositeScore
      7. Threshold alerts
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.stock_fetcher = StockFetcher(tier_of_fn=config.tickers.tier_of)
        self.news_fetcher = NewsFetcher(api_key=config.news_api_key)
        self.news_agent = NewsAgent(model=config.agent.model, host=config.ollama_host)
        self.analysis_agent = AnalysisAgent(model=config.agent.model, host=config.ollama_host)

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze_ticker(self, symbol: str) -> AnalysisResult:
        """Run the complete analysis pipeline for a single ticker."""
        logger.info("Analysing %s …", symbol)

        # 1. Quote
        quote = self.stock_fetcher.fetch_quote(symbol)
        if not quote:
            return AnalysisResult(
                symbol=symbol,
                quote=None,
                signals=None,
                error="Failed to fetch price data from yfinance",
            )

        # 2. Technical signals
        df = self.stock_fetcher.fetch_history(symbol, period="6mo")
        signals: TechnicalSignals | None = None
        if df is not None:
            try:
                signals = compute_signals(symbol, df, quote.fifty_two_week_high)
            except Exception as exc:
                logger.warning("Technical signal computation failed for %s: %s", symbol, exc)

        # 3. News
        articles = self.news_fetcher.fetch_news(
            symbol,
            hours_back=self.config.agent.news_lookback_hours,
            max_articles=self.config.agent.max_news_articles,
        )

        # 4. News AI analysis
        news_summary, sentiment_score = self.news_agent.analyze_articles(symbol, articles)

        # 5. Component scores
        tech_score = score_technical(signals) if signals else 50.0
        try:
            fund_score = compute_fundamental_score(quote)
        except Exception as exc:
            logger.error("Fundamental score computation failed for %s: %s", symbol, exc)
            fund_score = 50.0
        # Map sentiment -1..+1 → 0..100 (clamped to valid range)
        if not -1.0 <= sentiment_score <= 1.0:
            logger.warning(
                "%s: sentiment_score %f out of bounds [-1, 1], clamping",
                symbol, sentiment_score
            )
            sentiment_score = max(-1.0, min(1.0, sentiment_score))
        sent_score = round((sentiment_score + 1.0) / 2.0 * 100.0, 2)

        # 6. AI reasoning
        reasoning = ""
        if signals:
            try:
                reasoning = self.analysis_agent.analyze(
                    quote, signals, news_summary, sentiment_score
                )
            except Exception as exc:
                logger.warning("Analysis agent failed for %s: %s", symbol, exc)

        # 7. Composite score
        score = compute_composite_score(
            symbol=symbol,
            technical_score=tech_score,
            fundamental_score=fund_score,
            sentiment_score=sent_score,
            weights=self.config.scoring,
            reasoning=reasoning,
        )

        # 8. Threshold alerts
        alerts_fired = self._check_alerts(quote, signals, sentiment_score)

        return AnalysisResult(
            symbol=symbol,
            quote=quote,
            signals=signals,
            articles=articles,
            news_summary=news_summary,
            sentiment_score=sentiment_score,
            reasoning=reasoning,
            score=score,
            alerts_fired=alerts_fired,
        )

    def analyze_all(self, tier: int | None = None) -> list[AnalysisResult]:
        """
        Analyse all tickers for the given tier (1, 2, or None for all).
        Errors are captured per-ticker so one failure doesn't abort the run.
        """
        if tier == 1:
            symbols = self.config.tickers.tier1
        elif tier == 2:
            symbols = self.config.tickers.tier2
        else:
            symbols = self.config.tickers.all_tickers()

        results: list[AnalysisResult] = []
        total = len(symbols)
        for i, symbol in enumerate(symbols, 1):
            logger.info("[%d/%d] %s", i, total, symbol)
            try:
                results.append(self.analyze_ticker(symbol))
            except Exception as exc:
                logger.error("Unhandled error for %s: %s", symbol, exc)
                results.append(
                    AnalysisResult(
                        symbol=symbol,
                        quote=None,
                        signals=None,
                        error=str(exc),
                    )
                )

        return results

    # ── Alert checks ───────────────────────────────────────────────────────────

    def _check_alerts(
        self,
        quote: StockQuote,
        signals: TechnicalSignals | None,
        sentiment_score: float,
    ) -> list[str]:
        """Return list of alert strings that were triggered."""
        t = self.config.thresholds
        fired: list[str] = []

        # Price vs open
        if quote.open and quote.open > 0:
            pct_change = (quote.price - quote.open) / quote.open * 100
            if abs(pct_change) >= t.price_change_pct:
                direction = "up" if pct_change > 0 else "down"
                fired.append(
                    f"PRICE_SPIKE: {quote.symbol} moved {pct_change:+.1f}% ({direction}) from open"
                )

        # RSI extremes
        if signals and signals.rsi_14 is not None:
            if signals.rsi_14 <= t.rsi_oversold:
                fired.append(f"RSI_OVERSOLD: {quote.symbol} RSI={signals.rsi_14:.1f} (threshold {t.rsi_oversold})")
            elif signals.rsi_14 >= t.rsi_overbought:
                fired.append(f"RSI_OVERBOUGHT: {quote.symbol} RSI={signals.rsi_14:.1f} (threshold {t.rsi_overbought})")

        # Volume spike
        if signals and signals.volume_ratio is not None:
            if signals.volume_ratio >= t.volume_spike_ratio:
                fired.append(
                    f"VOLUME_SPIKE: {quote.symbol} volume {signals.volume_ratio:.1f}x above average"
                )

        # Negative sentiment
        if sentiment_score <= t.sentiment_negative_floor:
            fired.append(
                f"NEGATIVE_SENTIMENT: {quote.symbol} news sentiment={sentiment_score:+.2f}"
            )

        for alert in fired:
            logger.warning("ALERT — %s", alert)

        return fired
