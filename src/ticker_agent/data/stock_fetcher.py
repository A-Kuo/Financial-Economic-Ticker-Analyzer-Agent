"""yfinance wrapper — fetches price + fundamental data for a list of tickers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import yfinance as yf

from ticker_agent.config import get
from ticker_agent.data.models import TickerSnapshot

logger = logging.getLogger(__name__)

_TIMEOUT = 10


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def fetch_snapshot(ticker: str) -> TickerSnapshot | None:
    """Fetch current price + fundamentals for *ticker* and return an unsaved ORM model."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        price = _safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("ask")
        )
        prev_close = _safe_float(info.get("previousClose") or info.get("regularMarketPreviousClose"))
        change_pct = None
        if price is not None and prev_close and prev_close != 0:
            change_pct = round((price - prev_close) / prev_close * 100, 4)

        return TickerSnapshot(
            ticker=ticker.upper(),
            captured_at=datetime.utcnow(),
            price=price,
            open=_safe_float(info.get("open") or info.get("regularMarketOpen")),
            high=_safe_float(info.get("dayHigh") or info.get("regularMarketDayHigh")),
            low=_safe_float(info.get("dayLow") or info.get("regularMarketDayLow")),
            volume=_safe_int(info.get("volume") or info.get("regularMarketVolume")),
            prev_close=prev_close,
            change_pct=change_pct,
            market_cap=_safe_float(info.get("marketCap")),
            pe_ratio=_safe_float(info.get("trailingPE")),
            forward_pe=_safe_float(info.get("forwardPE")),
            eps=_safe_float(info.get("trailingEps")),
            revenue_ttm=_safe_float(info.get("totalRevenue")),
            profit_margin=_safe_float(info.get("profitMargins")),
            debt_to_equity=_safe_float(info.get("debtToEquity")),
            roe=_safe_float(info.get("returnOnEquity")),
            dividend_yield=_safe_float(info.get("dividendYield")),
            beta=_safe_float(info.get("beta")),
            week_52_high=_safe_float(info.get("fiftyTwoWeekHigh")),
            week_52_low=_safe_float(info.get("fiftyTwoWeekLow")),
        )
    except Exception as exc:
        logger.error("Failed to fetch snapshot for %s: %s", ticker, exc)
        return None


def fetch_price_history(ticker: str, days: int | None = None) -> "list[dict]":
    """Return a list of OHLCV dicts for the past *days* trading days.

    Each dict has keys: date, open, high, low, close, volume.
    """
    days = days or get("data.price_history_days", 90)
    try:
        t = yf.Ticker(ticker)
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        hist = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if hist.empty:
            logger.warning("No price history returned for %s", ticker)
            return []
        records = []
        for ts, row in hist.iterrows():
            records.append({
                "date": ts.to_pydatetime(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })
        return records
    except Exception as exc:
        logger.error("Failed to fetch price history for %s: %s", ticker, exc)
        return []


def fetch_batch_snapshots(tickers: list[str]) -> dict[str, TickerSnapshot | None]:
    """Fetch snapshots for multiple tickers; returns {ticker: snapshot_or_None}."""
    return {ticker: fetch_snapshot(ticker) for ticker in tickers}
