"""NewsAPI fetcher — retrieves recent articles for a given ticker."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import requests

from ticker_agent.config import get
from ticker_agent.data.models import NewsArticle

logger = logging.getLogger(__name__)

_NEWSAPI_URL = "https://newsapi.org/v2/everything"


def _get_api_key() -> str:
    key = os.getenv("NEWS_API_KEY") or get("news.api_key", "")
    if not key:
        raise EnvironmentError(
            "NEWS_API_KEY is not set. Add it to your .env file or environment."
        )
    return key


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fetch_articles(ticker: str, n: int | None = None) -> list[NewsArticle]:
    """Fetch recent news articles for *ticker* from NewsAPI.

    Returns a list of unsaved :class:`NewsArticle` ORM objects.
    """
    n = n or get("data.news_articles_per_ticker", 5)
    lookback_hours = get("data.news_lookback_hours", 24)
    from_dt = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        resp = requests.get(
            _NEWSAPI_URL,
            params={
                "q": ticker,
                "from": from_dt,
                "sortBy": "relevancy",
                "pageSize": n,
                "language": "en",
                "apiKey": _get_api_key(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except requests.RequestException as exc:
        logger.error("NewsAPI request failed for %s: %s", ticker, exc)
        return []

    articles = []
    for art in data.get("articles", []):
        articles.append(
            NewsArticle(
                ticker=ticker.upper(),
                fetched_at=datetime.utcnow(),
                published_at=_parse_dt(art.get("publishedAt")),
                title=art.get("title") or "",
                description=art.get("description"),
                url=art.get("url"),
                source=(art.get("source") or {}).get("name"),
            )
        )

    logger.debug("Fetched %d articles for %s", len(articles), ticker)
    return articles
