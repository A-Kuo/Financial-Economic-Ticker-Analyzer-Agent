"""News analysis agent — summarises articles and derives a sentiment score via Ollama."""
from __future__ import annotations

import logging
import re

from ticker_agent.agents.base_agent import BaseAgent
from ticker_agent.data.models import NewsArticle

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a senior financial news analyst at a top hedge fund.
Your job is to read recent news about a stock and produce a clear, structured assessment.
Focus only on information that is material to investors — ignore fluff, ads, or clickbait.
Be concise, accurate, and always output in the exact format requested."""


def _build_prompt(symbol: str, articles: list[NewsArticle]) -> str:
    articles_block = "\n\n".join(
        f"[{i+1}] {a.title}\n"
        f"    Source: {a.source}  |  Date: {a.published_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"    {a.description[:400].strip()}"
        for i, a in enumerate(articles[:6])
    )
    return f"""\
Analyze the following recent news articles for {symbol}:

{articles_block}

Respond in EXACTLY this format (no extra text before or after):

SUMMARY: <2–3 sentences covering the dominant theme and its market relevance>
SENTIMENT: <a single decimal number between -1.0 and 1.0, where -1=strongly bearish, 0=neutral, 1=strongly bullish>
CATALYSTS:
- <key catalyst or risk #1>
- <key catalyst or risk #2>
- <key catalyst or risk #3 (optional)>
OUTLOOK: <one sentence on likely near-term price impact>"""


class NewsAgent(BaseAgent):
    """Analyse a list of NewsArticles and return (summary_text, sentiment_score)."""

    def analyze_articles(
        self, symbol: str, articles: list[NewsArticle]
    ) -> tuple[str, float]:
        """
        Returns:
            summary (str): AI-generated news summary with catalysts.
            sentiment (float): -1.0 (very bearish) to +1.0 (very bullish).
        """
        if not articles:
            return "No recent news found for this ticker.", 0.0

        if not self.available:
            # Fallback: simple keyword-based heuristic
            return self._fallback_sentiment(symbol, articles)

        raw = self.simple_prompt(_SYSTEM, _build_prompt(symbol, articles))

        summary, sentiment = self._parse_response(raw, symbol)
        return summary, sentiment

    # ── Parsing ────────────────────────────────────────────────────────────────

    def _parse_response(self, raw: str, symbol: str) -> tuple[str, float]:
        summary = ""
        sentiment = 0.0
        catalysts: list[str] = []
        outlook = ""

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("SUMMARY:"):
                summary = stripped[len("SUMMARY:"):].strip()
            elif stripped.startswith("SENTIMENT:"):
                val_str = stripped[len("SENTIMENT:"):].strip()
                # Extract first float-like token
                m = re.search(r"-?\d+\.?\d*", val_str)
                if m:
                    try:
                        sentiment = max(-1.0, min(1.0, float(m.group())))
                    except ValueError:
                        sentiment = 0.0
            elif stripped.startswith("- "):
                catalysts.append(stripped[2:])
            elif stripped.startswith("OUTLOOK:"):
                outlook = stripped[len("OUTLOOK:"):].strip()

        # Build a rich summary string
        parts = [summary] if summary else [raw[:300]]
        if catalysts:
            parts.append("Key factors: " + " | ".join(catalysts))
        if outlook:
            parts.append(f"Outlook: {outlook}")

        return "  ".join(parts), sentiment

    # ── Fallback (no Ollama) ───────────────────────────────────────────────────

    _BULLISH_WORDS = {
        "beat", "record", "surge", "gain", "rally", "growth", "profit",
        "upgrade", "buy", "bullish", "strong", "positive", "revenue",
        "exceed", "outperform", "dividend", "raised", "guidance",
    }
    _BEARISH_WORDS = {
        "miss", "loss", "decline", "drop", "fall", "lawsuit", "recall",
        "cut", "downgrade", "sell", "bearish", "weak", "negative", "layoff",
        "investigation", "fraud", "fine", "penalty", "warning", "below",
    }

    def _fallback_sentiment(
        self, symbol: str, articles: list[NewsArticle]
    ) -> tuple[str, float]:
        combined = " ".join(
            (a.title + " " + a.description).lower() for a in articles
        )
        bull = sum(1 for w in self._BULLISH_WORDS if w in combined)
        bear = sum(1 for w in self._BEARISH_WORDS if w in combined)
        total = bull + bear or 1
        score = round((bull - bear) / total, 2)
        score = max(-1.0, min(1.0, score))
        titles = "; ".join(a.title for a in articles[:3] if a.title)
        summary = f"[Keyword analysis — Ollama offline] Recent headlines: {titles}."
        return summary, score
