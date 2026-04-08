"""Analysis agent — generates investment reasoning from all collected data via Ollama."""
from __future__ import annotations

import logging

from ticker_agent.agents.base_agent import BaseAgent
from ticker_agent.data.models import StockQuote, TechnicalSignals

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a quantitative equity analyst at a top-tier investment firm.
You synthesize technical indicators, fundamental metrics, and news sentiment
into clear, actionable investment insights.
Be specific — reference the actual numbers. Avoid generic statements.
Always structure your response as: setup → catalyst → risk → verdict."""


def _fmt_technical(s: TechnicalSignals) -> str:
    lines: list[str] = []
    if s.rsi_14 is not None:
        rsi_note = "oversold" if s.rsi_14 < 30 else ("overbought" if s.rsi_14 > 70 else "neutral")
        lines.append(f"RSI(14): {s.rsi_14:.1f} [{rsi_note}]")
    if s.macd is not None and s.macd_histogram is not None:
        hist_dir = "bullish" if s.macd_histogram > 0 else "bearish"
        lines.append(
            f"MACD: {s.macd:.4f} | Signal: {s.macd_signal:.4f} | "
            f"Hist: {s.macd_histogram:+.4f} [{hist_dir} momentum]"
        )
    if s.bb_upper is not None:
        lines.append(
            f"Bollinger Bands: ${s.bb_lower:.2f} / ${s.bb_middle:.2f} / ${s.bb_upper:.2f}"
        )
    sma_parts = []
    if s.sma_20:
        sma_parts.append(f"SMA20=${s.sma_20:.2f}")
    if s.sma_50:
        sma_parts.append(f"SMA50=${s.sma_50:.2f}")
    if s.sma_200:
        sma_parts.append(f"SMA200=${s.sma_200:.2f}")
    if sma_parts:
        # Describe golden/death cross
        cross = ""
        if s.sma_50 and s.sma_200:
            cross = " [GOLDEN CROSS]" if s.sma_50 > s.sma_200 else " [DEATH CROSS]"
        lines.append("  ".join(sma_parts) + cross)
    if s.volume_ratio is not None:
        v_note = "high conviction" if s.volume_ratio > 1.5 else ("low volume" if s.volume_ratio < 0.7 else "normal volume")
        lines.append(f"Volume ratio: {s.volume_ratio:.2f}x ({v_note})")
    if s.price_vs_52wk_high_pct is not None:
        lines.append(f"vs 52-week high: {s.price_vs_52wk_high_pct:+.1f}%")
    return "\n".join(f"  {l}" for l in lines) if lines else "  (insufficient history)"


def _fmt_fundamental(q: StockQuote) -> str:
    lines: list[str] = []
    if q.pe_ratio:
        pe_note = "cheap" if q.pe_ratio < 15 else ("fair" if q.pe_ratio < 25 else "premium")
        lines.append(f"P/E (trailing): {q.pe_ratio:.1f} [{pe_note}]")
    if q.eps:
        lines.append(f"EPS: ${q.eps:.2f}")
    if q.market_cap:
        cap_b = q.market_cap / 1e9
        size = "mega-cap" if cap_b > 200 else ("large-cap" if cap_b > 10 else "mid/small-cap")
        lines.append(f"Market cap: ${cap_b:.1f}B [{size}]")
    if q.beta:
        vol_note = "low-vol" if q.beta < 0.8 else ("high-vol" if q.beta > 1.5 else "market-correlated")
        lines.append(f"Beta: {q.beta:.2f} [{vol_note}]")
    if q.dividend_yield:
        lines.append(f"Dividend yield: {q.dividend_yield * 100:.2f}%")
    if q.fifty_two_week_low and q.fifty_two_week_high:
        lines.append(
            f"52-week range: ${q.fifty_two_week_low:.2f} – ${q.fifty_two_week_high:.2f}"
        )
    return "\n".join(f"  {l}" for l in lines) if lines else "  (data unavailable)"


def _build_prompt(
    quote: StockQuote,
    signals: TechnicalSignals,
    news_summary: str,
    sentiment_score: float,
) -> str:
    sent_label = (
        "strongly bullish" if sentiment_score > 0.5
        else "bullish" if sentiment_score > 0.15
        else "bearish" if sentiment_score < -0.15
        else "strongly bearish" if sentiment_score < -0.5
        else "neutral"
    )
    return f"""\
Perform a comprehensive analysis of {quote.symbol} ({quote.sector or "Unknown Sector"}).

CURRENT PRICE: ${quote.price:.2f}

TECHNICAL INDICATORS:
{_fmt_technical(signals)}

FUNDAMENTAL METRICS:
{_fmt_fundamental(quote)}

NEWS SENTIMENT: {sentiment_score:+.2f} ({sent_label})
NEWS SUMMARY: {news_summary}

Write a 4–6 sentence analysis covering:
1. Technical setup (trend direction, momentum, key levels)
2. Fundamental valuation context
3. What the news/sentiment implies for near-term price action
4. The single biggest risk to watch
5. One-sentence verdict (bullish / bearish / neutral with price context)"""


class AnalysisAgent(BaseAgent):
    """Generate AI-powered investment reasoning combining all data sources."""

    def analyze(
        self,
        quote: StockQuote,
        signals: TechnicalSignals,
        news_summary: str,
        sentiment_score: float,
    ) -> str:
        """
        Returns a prose reasoning string (4–6 sentences).
        Falls back to a rule-based summary if Ollama is unavailable.
        """
        if not self.available:
            return self._fallback_reasoning(quote, signals, sentiment_score)

        return self.simple_prompt(
            _SYSTEM,
            _build_prompt(quote, signals, news_summary, sentiment_score),
        )

    def _fallback_reasoning(
        self,
        quote: StockQuote,
        signals: TechnicalSignals,
        sentiment_score: float,
    ) -> str:
        parts: list[str] = []

        # Technical
        if signals.rsi_14 is not None:
            if signals.rsi_14 < 30:
                parts.append(f"RSI at {signals.rsi_14:.1f} signals the stock is oversold — potential mean-reversion setup.")
            elif signals.rsi_14 > 70:
                parts.append(f"RSI at {signals.rsi_14:.1f} indicates overbought conditions — momentum may be fading.")
            else:
                parts.append(f"RSI at {signals.rsi_14:.1f} shows neutral momentum.")

        if signals.sma_50 and signals.sma_200:
            if signals.sma_50 > signals.sma_200:
                parts.append("50-day SMA above 200-day SMA (golden cross) — long-term uptrend intact.")
            else:
                parts.append("50-day SMA below 200-day SMA (death cross) — long-term downtrend in effect.")

        # Fundamental
        if quote.pe_ratio:
            if quote.pe_ratio < 15:
                parts.append(f"At a P/E of {quote.pe_ratio:.1f}, the stock looks undervalued versus historical norms.")
            elif quote.pe_ratio > 40:
                parts.append(f"P/E of {quote.pe_ratio:.1f} prices in significant growth — leaves little room for error.")

        # Sentiment
        if sentiment_score > 0.3:
            parts.append("Recent news flow is positive — potential near-term tailwind.")
        elif sentiment_score < -0.3:
            parts.append("Negative news sentiment could weigh on the stock short-term.")

        return " ".join(parts) if parts else "Insufficient data for detailed analysis."
