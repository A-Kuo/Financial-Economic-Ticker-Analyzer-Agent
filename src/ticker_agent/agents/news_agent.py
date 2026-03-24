"""NewsAgent — uses Ollama to score sentiment for a batch of news articles."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from ticker_agent.agents.base_agent import BaseAgent
from ticker_agent.data.models import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class ArticleSentiment:
    title: str
    sentiment: str          # "bullish" | "bearish" | "neutral"
    score: float            # -1.0 (very bearish) … +1.0 (very bullish)
    reasoning: str


@dataclass
class NewsSentimentResult:
    ticker: str
    articles: list[ArticleSentiment]
    aggregate_score: float      # average of article scores
    aggregate_label: str        # "bullish" | "bearish" | "neutral"
    summary: str                # one-paragraph narrative


class NewsAgent(BaseAgent):
    """Analyses news articles for a ticker and returns sentiment + summary."""

    def __init__(self) -> None:
        super().__init__("NewsAgent")

    def build_prompt(self, ticker: str, articles: list[NewsArticle]) -> str:  # type: ignore[override]
        headlines = "\n".join(
            f"{i+1}. [{art.source or 'Unknown'}] {art.title}"
            for i, art in enumerate(articles)
        )
        return f"""You are analysing recent news for stock ticker: {ticker}

NEWS HEADLINES:
{headlines}

For EACH headline, respond with a JSON array where each element has:
- "title": the headline (shortened to 60 chars)
- "sentiment": one of "bullish", "bearish", or "neutral"
- "score": float from -1.0 (very bearish) to +1.0 (very bullish)
- "reasoning": one sentence justification

After the JSON array, write a paragraph starting with "SUMMARY:" that synthesises
the overall news sentiment for {ticker} in 2-3 sentences.

Example format:
[
  {{"title": "...", "sentiment": "bullish", "score": 0.7, "reasoning": "..."}}
]
SUMMARY: The news flow for {ticker} is...
"""

    def parse_response(self, raw: str) -> dict[str, Any]:
        """Extract JSON array + SUMMARY from raw LLM text."""
        # Extract JSON block
        json_match = re.search(r"\[.*?\]", raw, re.DOTALL)
        articles_data: list[dict] = []
        if json_match:
            try:
                articles_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                logger.warning("NewsAgent: could not parse JSON from response")

        # Extract SUMMARY
        summary_match = re.search(r"SUMMARY:\s*(.+)", raw, re.DOTALL | re.IGNORECASE)
        summary = summary_match.group(1).strip() if summary_match else raw[-300:]

        return {"articles": articles_data, "summary": summary}

    def analyse(self, ticker: str, articles: list[NewsArticle]) -> NewsSentimentResult:
        """Run full news sentiment analysis for a ticker."""
        if not articles:
            return NewsSentimentResult(
                ticker=ticker,
                articles=[],
                aggregate_score=0.0,
                aggregate_label="neutral",
                summary="No recent news articles found.",
            )

        result = self.run(ticker=ticker, articles=articles)
        raw_articles: list[dict] = result.get("articles", [])
        summary: str = result.get("summary", "")

        sentiments: list[ArticleSentiment] = []
        for art_data in raw_articles:
            sentiments.append(ArticleSentiment(
                title=art_data.get("title", ""),
                sentiment=art_data.get("sentiment", "neutral"),
                score=float(art_data.get("score", 0.0)),
                reasoning=art_data.get("reasoning", ""),
            ))

        # Persist scores back onto the ORM objects if available
        for i, art_obj in enumerate(articles):
            if i < len(sentiments):
                art_obj.sentiment = sentiments[i].sentiment
                art_obj.sentiment_score = sentiments[i].score

        scores = [s.score for s in sentiments] if sentiments else [0.0]
        agg_score = round(sum(scores) / len(scores), 3)
        if agg_score > 0.15:
            label = "bullish"
        elif agg_score < -0.15:
            label = "bearish"
        else:
            label = "neutral"

        return NewsSentimentResult(
            ticker=ticker,
            articles=sentiments,
            aggregate_score=agg_score,
            aggregate_label=label,
            summary=summary,
        )
