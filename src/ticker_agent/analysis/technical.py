"""Technical indicator computation — pure pandas/numpy, no external TA libraries."""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from ticker_agent.data.models import TechnicalSignals

logger = logging.getLogger(__name__)


# ── Indicator functions ────────────────────────────────────────────────────────

def compute_rsi(prices: pd.Series, period: int = 14) -> float | None:
    """Wilder's RSI using exponential smoothing. Returns None if insufficient data."""
    if len(prices) < period + 1:
        return None
    delta = prices.diff().dropna()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else None


def compute_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float | None, float | None, float | None]:
    """Standard MACD. Returns (macd_line, signal_line, histogram)."""
    if len(prices) < slow + signal_period:
        return None, None, None
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return (
        float(macd_line.iloc[-1]),
        float(signal_line.iloc[-1]),
        float(histogram.iloc[-1]),
    )


def compute_bollinger_bands(
    prices: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    """Bollinger Bands. Returns (upper, middle/SMA, lower)."""
    if len(prices) < period:
        return None, None, None
    sma = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper = (sma + num_std * std).iloc[-1]
    middle = sma.iloc[-1]
    lower = (sma - num_std * std).iloc[-1]
    if any(pd.isna(v) for v in [upper, middle, lower]):
        return None, None, None
    return float(upper), float(middle), float(lower)


def compute_sma(prices: pd.Series, period: int) -> float | None:
    if len(prices) < period:
        return None
    val = prices.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else None


def compute_volume_ratio(volumes: pd.Series, period: int = 10) -> float | None:
    """Ratio of today's volume to the N-day average (excluding today)."""
    if len(volumes) < period + 1:
        return None
    avg = volumes.iloc[-(period + 1):-1].mean()
    if avg == 0:
        return None
    return float(volumes.iloc[-1] / avg)


# ── High-level builder ─────────────────────────────────────────────────────────

def compute_signals(
    symbol: str,
    df: pd.DataFrame,
    fifty_two_week_high: float | None = None,
) -> TechnicalSignals:
    """Derive all TechnicalSignals from a yfinance OHLCV DataFrame."""
    closes = df["Close"].dropna()
    volumes = df["Volume"].dropna()

    macd, macd_sig, macd_hist = compute_macd(closes)
    bb_upper, bb_mid, bb_lower = compute_bollinger_bands(closes)

    price_vs_52wk: float | None = None
    if len(closes) > 0 and fifty_two_week_high and fifty_two_week_high > 0:
        price_vs_52wk = round(
            (float(closes.iloc[-1]) - fifty_two_week_high) / fifty_two_week_high * 100, 2
        )

    return TechnicalSignals(
        symbol=symbol,
        rsi_14=compute_rsi(closes),
        macd=macd,
        macd_signal=macd_sig,
        macd_histogram=macd_hist,
        bb_upper=bb_upper,
        bb_middle=bb_mid,
        bb_lower=bb_lower,
        sma_20=compute_sma(closes, 20),
        sma_50=compute_sma(closes, 50),
        sma_200=compute_sma(closes, 200),
        volume_ratio=compute_volume_ratio(volumes),
        price_vs_52wk_high_pct=price_vs_52wk,
        timestamp=datetime.utcnow(),
    )
