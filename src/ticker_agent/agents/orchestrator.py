"""Orchestrator — coordinates the full analysis pipeline for one or more tickers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ticker_agent.agents.analysis_agent import AnalysisAgent, MarketIntelligenceReport
from ticker_agent.agents.news_agent import NewsAgent, NewsSentimentResult
from ticker_agent.analysis import fundamental as fund_module
from ticker_agent.analysis import scoring as scoring_module
from ticker_agent.analysis import technical as tech_module
from ticker_agent.data import database, news_fetcher, stock_fetcher
from ticker_agent.data.models import AnalysisResult, TickerSnapshot

logger = logging.getLogger(__name__)


@dataclass
class TickerAnalysis:
    """Complete analysis bundle for one ticker — ready for output/reporting."""

    ticker: str
    snapshot: TickerSnapshot | None
    report: MarketIntelligenceReport | None
    news_result: NewsSentimentResult | None
    analysed_at: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.report is not None

    def to_pipeline_payload(self) -> dict[str, Any]:
        """Serialise to the inter-service JSON schema used by the FinancialPipeline."""
        snap = self.snapshot
        rep = self.report
        news = self.news_result
        return {
            "ticker": self.ticker,
            "analysed_at": self.analysed_at.isoformat(),
            "market_context": {
                "current_price": snap.price if snap else None,
                "change_pct": snap.change_pct if snap else None,
                "market_cap": snap.market_cap if snap else None,
                "composite_score": rep.composite_score if rep else None,
                "signal": rep.signal if rep else None,
                "confidence": rep.confidence if rep else None,
                "sentiment_score": news.aggregate_score if news else None,
                "sentiment_label": news.aggregate_label if news else None,
            },
            "narrative": rep.narrative if rep else None,
            "key_catalysts": rep.key_catalysts if rep else [],
            "key_risks": rep.key_risks if rep else [],
        }


class Orchestrator:
    """Runs the full two-tier analysis pipeline for a list of tickers.

    Tier 1 (high-frequency): fetch snapshot + news → score → persist.
    Tier 2 (standard):       tier-1 + LLM narrative report.
    """

    def __init__(self, use_llm: bool = True) -> None:
        self._news_agent = NewsAgent() if use_llm else None
        self._analysis_agent = AnalysisAgent() if use_llm else None
        self._use_llm = use_llm
        database.init_db()

    def analyse_ticker(self, ticker: str, tier: int = 2) -> TickerAnalysis:
        """Full pipeline for a single ticker. *tier* 1 skips LLM narrative."""
        logger.info("Analysing %s (tier %d)", ticker, tier)
        try:
            # ── Stage 1: Data fetch ────────────────────────────────────────
            snapshot = stock_fetcher.fetch_snapshot(ticker)
            if snapshot is None:
                return TickerAnalysis(ticker=ticker, snapshot=None, report=None, news_result=None,
                                      error=f"Could not fetch snapshot for {ticker}")

            price_history = stock_fetcher.fetch_price_history(ticker)
            articles = news_fetcher.fetch_articles(ticker)

            # ── Stage 2: Technical analysis ────────────────────────────────
            tech_ind = tech_module.calculate(ticker, price_history)
            tech_score = scoring_module.technical_score_from_indicators(tech_ind)

            # ── Stage 3: Fundamental analysis ─────────────────────────────
            fund_metrics = fund_module.analyse(snapshot)
            fund_score = fund_module.score(fund_metrics)

            # ── Stage 4: News sentiment (LLM) ─────────────────────────────
            news_result: NewsSentimentResult | None = None
            sent_score: float | None = None
            if self._use_llm and self._news_agent and articles:
                news_result = self._news_agent.analyse(ticker, articles)
                # Map -1…+1 → 0…100
                raw_s = news_result.aggregate_score
                sent_score = round((raw_s + 1) / 2 * 100, 1)

            # ── Stage 5: Composite scoring ─────────────────────────────────
            composite = scoring_module.compute(ticker, tech_score, fund_score, sent_score)

            # ── Stage 6: LLM narrative (tier 2 only) ──────────────────────
            report: MarketIntelligenceReport | None = None
            if tier == 2 and self._use_llm and self._analysis_agent:
                news_summary = news_result.summary if news_result else "No recent news."
                report = self._analysis_agent.generate_report(
                    ticker=ticker,
                    price=snapshot.price,
                    composite=composite,
                    technical=tech_ind,
                    fundamental=fund_metrics,
                    news_summary=news_summary,
                )
            elif tier == 1 or not self._use_llm:
                # Build a lightweight report without LLM
                from ticker_agent.agents.analysis_agent import MarketIntelligenceReport  # noqa: PLC0415
                news_summary_short = news_result.summary[:200] if news_result else "N/A"
                report = MarketIntelligenceReport(
                    ticker=ticker,
                    composite_score=composite.composite_score,
                    signal=composite.signal,
                    confidence=composite.confidence,
                    narrative=f"Signal: {composite.signal} | Score: {composite.composite_score}",
                    key_catalysts=[],
                    key_risks=[],
                    price_target_comment="",
                )

            # ── Stage 7: Persist ───────────────────────────────────────────
            self._persist(snapshot, articles, composite, tech_ind, fund_metrics, report)

            return TickerAnalysis(
                ticker=ticker,
                snapshot=snapshot,
                report=report,
                news_result=news_result,
            )

        except Exception as exc:
            logger.exception("Orchestrator error for %s", ticker)
            return TickerAnalysis(ticker=ticker, snapshot=None, report=None, news_result=None,
                                  error=str(exc))

    def analyse_batch(self, tickers: list[str], tier: int = 2) -> list[TickerAnalysis]:
        """Analyse a list of tickers sequentially."""
        results = []
        for ticker in tickers:
            results.append(self.analyse_ticker(ticker, tier=tier))
        return results

    def _persist(
        self,
        snapshot: TickerSnapshot,
        articles,
        composite,
        tech_ind,
        fund_metrics,
        report,
    ) -> None:
        try:
            with database.session_scope() as session:
                session.add(snapshot)
                session.flush()  # get snapshot.id

                for art in articles:
                    session.add(art)

                ar = AnalysisResult(
                    snapshot_id=snapshot.id,
                    ticker=snapshot.ticker,
                    technical_score=composite.technical_score,
                    fundamental_score=composite.fundamental_score,
                    sentiment_score=composite.sentiment_score,
                    composite_score=composite.composite_score,
                    signal=composite.signal,
                    llm_summary=report.narrative if report else None,
                    technical_indicators=tech_ind.to_dict() if tech_ind else None,
                    fundamental_metrics=fund_metrics.to_dict() if fund_metrics else None,
                )
                session.add(ar)
        except Exception as exc:
            logger.error("Failed to persist analysis for %s: %s", snapshot.ticker, exc)
