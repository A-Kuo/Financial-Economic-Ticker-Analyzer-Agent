"""yfinance wrapper: fetch current quotes and OHLCV history with retry logic."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Callable

import pandas as pd
import yfinance as yf

from ticker_agent.data.models import StockQuote

logger = logging.getLogger(__name__)


class StockFetcher:
    def __init__(self, tier_of_fn: Callable[[str], int] | None = None):
        self._tier_of = tier_of_fn or (lambda _: 0)

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch_quote(self, symbol: str, retries: int = 3) -> StockQuote | None:
        """Fetch the latest price + fundamentals for a single ticker."""
        for attempt in range(retries):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info or {}
                hist = ticker.history(period="5d", interval="1d")
                if hist.empty:
                    logger.warning("No price history for %s", symbol)
                    return None
                latest = hist.iloc[-1]
                return StockQuote(
                    symbol=symbol,
                    price=float(latest.get("Close", 0.0)),
                    open=float(latest.get("Open", 0.0)),
                    high=float(latest.get("High", 0.0)),
                    low=float(latest.get("Low", 0.0)),
                    volume=int(latest.get("Volume", 0)),
                    market_cap=info.get("marketCap"),
                    pe_ratio=info.get("trailingPE"),
                    eps=info.get("trailingEps"),
                    fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                    fifty_two_week_low=info.get("fiftyTwoWeekLow"),
                    avg_volume=info.get("averageVolume"),
                    beta=info.get("beta"),
                    dividend_yield=info.get("dividendYield"),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    timestamp=datetime.utcnow(),
                    tier=self._tier_of(symbol),
                )
            except Exception as exc:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.debug("Retry %d for %s after %ds (%s)", attempt + 1, symbol, wait, exc)
                    time.sleep(wait)
                else:
                    logger.error("Failed to fetch quote for %s: %s", symbol, exc)
                    return None
        return None  # unreachable, but satisfies type checker

    def fetch_history(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        """Fetch OHLCV history as a pandas DataFrame."""
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            return df if not df.empty else None
        except Exception as exc:
            logger.error("History fetch failed for %s: %s", symbol, exc)
            return None

    def fetch_quotes_batch(
        self, symbols: list[str], retries: int = 2
    ) -> dict[str, StockQuote]:
        """Fetch quotes for multiple tickers, returning only successful ones."""
        results: dict[str, StockQuote] = {}
        for symbol in symbols:
            quote = self.fetch_quote(symbol, retries=retries)
            if quote:
                results[symbol] = quote
        return results
