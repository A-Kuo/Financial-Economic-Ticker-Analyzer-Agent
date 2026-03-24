"""Technical indicator calculations using the `ta` library + pandas."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ticker_agent.config import get

logger = logging.getLogger(__name__)


@dataclass
class TechnicalIndicators:
    """Calculated technical indicators for a single ticker."""

    ticker: str

    # Trend
    sma_short: float | None = None
    sma_long: float | None = None
    ema_20: float | None = None
    price_vs_sma_short_pct: float | None = None  # % above/below SMA-20
    price_vs_sma_long_pct: float | None = None   # % above/below SMA-50

    # Momentum
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

    # Volatility
    bb_upper: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None       # (upper - lower) / middle
    bb_percent_b: float | None = None   # (price - lower) / (upper - lower)
    atr: float | None = None

    # Volume
    volume_sma_20: float | None = None
    volume_ratio: float | None = None   # current volume / SMA-20

    # Derived signals
    golden_cross: bool = False          # SMA-short crossed above SMA-long
    death_cross: bool = False
    rsi_overbought: bool = False
    rsi_oversold: bool = False
    macd_bullish: bool = False          # MACD histogram turned positive
    above_bb_upper: bool = False
    below_bb_lower: bool = False

    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "raw"}


def calculate(ticker: str, price_history: list[dict]) -> TechnicalIndicators | None:
    """Compute all technical indicators from OHLCV *price_history*.

    *price_history* is a list of dicts with keys: date, open, high, low, close, volume.
    """
    if len(price_history) < 30:
        logger.warning("Insufficient history for %s (%d bars)", ticker, len(price_history))
        return None

    cfg = get("analysis.technical", {})
    rsi_period = cfg.get("rsi_period", 14)
    macd_fast = cfg.get("macd_fast", 12)
    macd_slow = cfg.get("macd_slow", 26)
    macd_sig = cfg.get("macd_signal", 9)
    bb_period = cfg.get("bb_period", 20)
    bb_std = cfg.get("bb_std", 2.0)
    sma_short_p = cfg.get("sma_short", 20)
    sma_long_p = cfg.get("sma_long", 50)

    df = pd.DataFrame(price_history)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    try:
        import ta  # noqa: PLC0415

        ind = TechnicalIndicators(ticker=ticker)

        # ── Trend ──────────────────────────────────────────────────────────
        ind.sma_short = float(close.rolling(sma_short_p).mean().iloc[-1])
        ind.sma_long = float(close.rolling(sma_long_p).mean().iloc[-1]) if len(close) >= sma_long_p else None
        ind.ema_20 = float(ta.trend.ema_indicator(close, window=20).iloc[-1])

        current_price = float(close.iloc[-1])
        if ind.sma_short:
            ind.price_vs_sma_short_pct = round((current_price - ind.sma_short) / ind.sma_short * 100, 2)
        if ind.sma_long:
            ind.price_vs_sma_long_pct = round((current_price - ind.sma_long) / ind.sma_long * 100, 2)

        # Golden / death cross (last 2 bars)
        if ind.sma_long and len(close) >= sma_long_p + 1:
            sma_s = close.rolling(sma_short_p).mean()
            sma_l = close.rolling(sma_long_p).mean()
            ind.golden_cross = bool(sma_s.iloc[-2] <= sma_l.iloc[-2] and sma_s.iloc[-1] > sma_l.iloc[-1])
            ind.death_cross = bool(sma_s.iloc[-2] >= sma_l.iloc[-2] and sma_s.iloc[-1] < sma_l.iloc[-1])

        # ── Momentum ───────────────────────────────────────────────────────
        ind.rsi = float(ta.momentum.rsi(close, window=rsi_period).iloc[-1])
        ind.rsi_overbought = ind.rsi > 70
        ind.rsi_oversold = ind.rsi < 30

        macd_obj = ta.trend.MACD(close, window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_sig)
        ind.macd = float(macd_obj.macd().iloc[-1])
        ind.macd_signal = float(macd_obj.macd_signal().iloc[-1])
        ind.macd_histogram = float(macd_obj.macd_diff().iloc[-1])
        if len(macd_obj.macd_diff()) >= 2:
            ind.macd_bullish = (
                macd_obj.macd_diff().iloc[-2] < 0 and macd_obj.macd_diff().iloc[-1] > 0
            )

        # ── Volatility ─────────────────────────────────────────────────────
        bb = ta.volatility.BollingerBands(close, window=bb_period, window_dev=bb_std)
        ind.bb_upper = float(bb.bollinger_hband().iloc[-1])
        ind.bb_lower = float(bb.bollinger_lband().iloc[-1])
        bb_mid = float(bb.bollinger_mavg().iloc[-1])
        if bb_mid:
            ind.bb_width = round((ind.bb_upper - ind.bb_lower) / bb_mid, 4)
        if ind.bb_upper and ind.bb_lower and (ind.bb_upper - ind.bb_lower) != 0:
            ind.bb_percent_b = round((current_price - ind.bb_lower) / (ind.bb_upper - ind.bb_lower), 4)
        ind.above_bb_upper = current_price > ind.bb_upper
        ind.below_bb_lower = current_price < ind.bb_lower

        atr_series = ta.volatility.average_true_range(high, low, close, window=14)
        ind.atr = float(atr_series.iloc[-1])

        # ── Volume ─────────────────────────────────────────────────────────
        ind.volume_sma_20 = float(volume.rolling(20).mean().iloc[-1])
        if ind.volume_sma_20 and ind.volume_sma_20 != 0:
            ind.volume_ratio = round(float(volume.iloc[-1]) / ind.volume_sma_20, 2)

        return ind

    except Exception as exc:
        logger.error("Technical analysis failed for %s: %s", ticker, exc)
        return None
