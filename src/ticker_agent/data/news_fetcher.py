"""NewsAPI wrapper for fetching financial news articles."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ticker_agent.data.models import NewsArticle

logger = logging.getLogger(__name__)

# Map tickers → company names for better NewsAPI search quality
_COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "GOOGL": "Google Alphabet",
    "AMZN": "Amazon",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "BRK-B": "Berkshire Hathaway",
    "JPM": "JPMorgan Chase",
    "V": "Visa",
    "AMD": "AMD",
    "INTC": "Intel",
    "ORCL": "Oracle",
    "CRM": "Salesforce",
    "ADBE": "Adobe",
    "AVGO": "Broadcom",
    "BAC": "Bank of America",
    "GS": "Goldman Sachs",
    "WFC": "Wells Fargo",
    "MS": "Morgan Stanley",
    "JNJ": "Johnson Johnson",
    "UNH": "UnitedHealth",
    "PFE": "Pfizer",
    "XOM": "ExxonMobil",
    "CVX": "Chevron",
    "WMT": "Walmart",
    "COST": "Costco",
    "HD": "Home Depot",
    "MCD": "McDonald's",
    "PG": "Procter Gamble",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
}


class NewsFetcher:
    """Fetches news from NewsAPI. Gracefully no-ops when the key is absent."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None
        if api_key:
            try:
                from newsapi import NewsApiClient
                self._client = NewsApiClient(api_key=api_key)
                logger.debug("NewsAPI client initialised")
            except ImportError:
                logger.warning(
                    "newsapi-python not installed. Run: pip install newsapi-python"
                )

    def fetch_news(
        self,
        symbol: str,
        hours_back: int = 24,
        max_articles: int = 5,
    ) -> list[NewsArticle]:
        """Return recent news articles for *symbol*. Returns [] on any error."""
        if not self._client:
            logger.debug("No NewsAPI client — skipping news for %s", symbol)
            return []

        company = _COMPANY_NAMES.get(symbol, symbol)
        from_dt = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
        query = f'"{company}" OR "{symbol}" stock'

        try:
            resp = self._client.get_everything(
                q=query,
                from_param=from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                language="en",
                sort_by="relevancy",
                page_size=min(max_articles, 20),
            )
        except Exception as exc:
            logger.error("NewsAPI error for %s: %s", symbol, exc)
            return []

        articles: list[NewsArticle] = []
        for item in resp.get("articles") or []:
            url = item.get("url")
            if not url:
                continue
            try:
                pub_at = datetime.fromisoformat(
                    item["publishedAt"].replace("Z", "+00:00")
                )
            except Exception:
                pub_at = datetime.now(tz=timezone.utc)

            articles.append(
                NewsArticle(
                    symbol=symbol,
                    title=item.get("title") or "",
                    source=(item.get("source") or {}).get("name") or "",
                    url=url,
                    published_at=pub_at,
                    description=(item.get("description") or item.get("content") or "")[:500],
                )
            )

        return articles[:max_articles]
