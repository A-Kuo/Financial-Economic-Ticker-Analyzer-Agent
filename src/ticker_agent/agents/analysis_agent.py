"""AnalysisAgent — synthesises technical + fundamental + sentiment into a narrative."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ticker_agent.agents.base_agent import BaseAgent
from ticker_agent.analysis.scoring import CompositeScore
from ticker_agent.analysis.technical import TechnicalIndicators
from ticker_agent.analysis.fundamental import FundamentalMetrics

logger = logging.getLogger(__name__)


@dataclass
class MarketIntelligenceReport:
    ticker: str
    composite_score: float
    signal: str
    confidence: str
    narrative: str          # LLM-generated multi-paragraph analysis
    key_catalysts: list[str]
    key_risks: list[str]
    price_target_comment: str


class AnalysisAgent(BaseAgent):
    """Generates a concise market intelligence narrative for one ticker."""

    def __init__(self) -> None:
        super().__init__("AnalysisAgent")

    def build_prompt(  # type: ignore[override]
        self,
        ticker: str,
        price: float | None,
        composite: CompositeScore,
        technical: TechnicalIndicators | None,
        fundamental: FundamentalMetrics | None,
        news_summary: str,
    ) -> str:
        tech_lines = ""
        if technical:
            tech_lines = f"""
TECHNICAL INDICATORS:
  RSI(14): {technical.rsi:.1f if technical.rsi else 'N/A'} {'(Overbought)' if technical.rsi_overbought else '(Oversold)' if technical.rsi_oversold else ''}
  MACD histogram: {technical.macd_histogram:.4f if technical.macd_histogram else 'N/A'}
  Price vs SMA-20: {technical.price_vs_sma_short_pct:+.1f}%  vs SMA-50: {technical.price_vs_sma_long_pct:+.1f}%
  Bollinger %B: {technical.bb_percent_b:.2f if technical.bb_percent_b else 'N/A'}
  Volume ratio (vs 20d avg): {technical.volume_ratio:.2f if technical.volume_ratio else 'N/A'}x
  Golden cross: {technical.golden_cross}  Death cross: {technical.death_cross}"""

        fund_lines = ""
        if fundamental:
            fund_lines = f"""
FUNDAMENTAL METRICS:
  P/E: {fundamental.pe_ratio:.1f if fundamental.pe_ratio else 'N/A'}  Forward P/E: {fundamental.forward_pe:.1f if fundamental.forward_pe else 'N/A'}
  Profit margin: {fundamental.profit_margin*100:.1f if fundamental.profit_margin else 'N/A'}%
  ROE: {fundamental.roe*100:.1f if fundamental.roe else 'N/A'}%
  D/E: {fundamental.debt_to_equity:.2f if fundamental.debt_to_equity else 'N/A'}
  Beta: {fundamental.beta:.2f if fundamental.beta else 'N/A'}
  Market cap tier: {fundamental.market_cap_tier}
  52-week position: {fundamental.price_to_52w_high_pct:+.1f}% vs high, {fundamental.price_to_52w_low_pct:+.1f}% vs low"""

        return f"""Analyse {ticker} (current price: ${price:.2f if price else 'N/A'}) and produce a concise market intelligence report.

COMPOSITE SCORE: {composite.composite_score}/100  SIGNAL: {composite.signal}  CONFIDENCE: {composite.confidence}
  Technical sub-score: {composite.technical_score}  Fundamental: {composite.fundamental_score}  Sentiment: {composite.sentiment_score}
{tech_lines}
{fund_lines}

RECENT NEWS SENTIMENT:
{news_summary}

Write your response in this EXACT format:

NARRATIVE:
[2-3 paragraphs: overall assessment, key drivers, outlook]

KEY_CATALYSTS:
- [catalyst 1]
- [catalyst 2]
- [catalyst 3]

KEY_RISKS:
- [risk 1]
- [risk 2]

PRICE_TARGET_COMMENT:
[One sentence on near-term price direction based on the data above]
"""

    def parse_response(self, raw: str) -> dict:
        def _extract(header: str, text: str) -> str:
            pattern = rf"{header}:\s*(.*?)(?=\n[A-Z_]+:|$)"
            m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        def _extract_bullets(header: str, text: str) -> list[str]:
            block = _extract(header, text)
            lines = [ln.lstrip("-• ").strip() for ln in block.splitlines() if ln.strip()]
            return [ln for ln in lines if ln]

        return {
            "narrative": _extract("NARRATIVE", raw),
            "key_catalysts": _extract_bullets("KEY_CATALYSTS", raw),
            "key_risks": _extract_bullets("KEY_RISKS", raw),
            "price_target_comment": _extract("PRICE_TARGET_COMMENT", raw),
        }

    def generate_report(
        self,
        ticker: str,
        price: float | None,
        composite: CompositeScore,
        technical: TechnicalIndicators | None,
        fundamental: FundamentalMetrics | None,
        news_summary: str,
    ) -> MarketIntelligenceReport:
        result = self.run(
            ticker=ticker,
            price=price,
            composite=composite,
            technical=technical,
            fundamental=fundamental,
            news_summary=news_summary,
        )
        return MarketIntelligenceReport(
            ticker=ticker,
            composite_score=composite.composite_score,
            signal=composite.signal,
            confidence=composite.confidence,
            narrative=result.get("narrative", raw_fallback := "Analysis unavailable."),
            key_catalysts=result.get("key_catalysts", []),
            key_risks=result.get("key_risks", []),
            price_target_comment=result.get("price_target_comment", ""),
        )
