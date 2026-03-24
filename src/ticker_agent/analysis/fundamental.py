"""Fundamental analysis — score a TickerSnapshot on valuation + quality metrics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ticker_agent.data.models import TickerSnapshot

logger = logging.getLogger(__name__)

# Benchmark thresholds — loosely based on S&P 500 medians
_PE_FAIR = 25.0
_PE_CHEAP = 15.0
_FORWARD_PE_FAIR = 22.0
_PROFIT_MARGIN_GOOD = 0.15
_ROE_GOOD = 0.15
_DE_MAX = 2.0
_BETA_LOW = 0.8
_BETA_HIGH = 1.5


@dataclass
class FundamentalMetrics:
    """Human-readable fundamental metrics derived from a snapshot."""

    ticker: str

    # Valuation
    pe_ratio: float | None = None
    forward_pe: float | None = None
    price_to_52w_high_pct: float | None = None  # % below 52-week high
    price_to_52w_low_pct: float | None = None   # % above 52-week low

    # Quality
    profit_margin: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None

    # Market size
    market_cap: float | None = None
    market_cap_tier: str = "unknown"  # micro / small / mid / large / mega

    # Signals
    is_cheap_pe: bool = False
    is_high_quality: bool = False   # decent margin + ROE
    is_over_leveraged: bool = False
    is_near_52w_high: bool = False

    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "raw"}


def _market_cap_tier(cap: float | None) -> str:
    if cap is None:
        return "unknown"
    b = cap / 1e9
    if b >= 200:
        return "mega"
    if b >= 10:
        return "large"
    if b >= 2:
        return "mid"
    if b >= 0.3:
        return "small"
    return "micro"


def analyse(snapshot: TickerSnapshot) -> FundamentalMetrics:
    """Derive :class:`FundamentalMetrics` from a :class:`TickerSnapshot`."""
    m = FundamentalMetrics(ticker=snapshot.ticker)

    m.pe_ratio = snapshot.pe_ratio
    m.forward_pe = snapshot.forward_pe
    m.profit_margin = snapshot.profit_margin
    m.roe = snapshot.roe
    m.debt_to_equity = snapshot.debt_to_equity
    m.beta = snapshot.beta
    m.dividend_yield = snapshot.dividend_yield
    m.market_cap = snapshot.market_cap
    m.market_cap_tier = _market_cap_tier(snapshot.market_cap)

    price = snapshot.price
    if price and snapshot.week_52_high and snapshot.week_52_high != 0:
        m.price_to_52w_high_pct = round((price - snapshot.week_52_high) / snapshot.week_52_high * 100, 2)
        m.is_near_52w_high = m.price_to_52w_high_pct > -5
    if price and snapshot.week_52_low and snapshot.week_52_low != 0:
        m.price_to_52w_low_pct = round((price - snapshot.week_52_low) / snapshot.week_52_low * 100, 2)

    if m.pe_ratio and m.pe_ratio < _PE_CHEAP:
        m.is_cheap_pe = True

    has_margin = m.profit_margin is not None and m.profit_margin >= _PROFIT_MARGIN_GOOD
    has_roe = m.roe is not None and m.roe >= _ROE_GOOD
    m.is_high_quality = has_margin and has_roe

    if m.debt_to_equity is not None and m.debt_to_equity > _DE_MAX:
        m.is_over_leveraged = True

    return m


def score(metrics: FundamentalMetrics) -> float:
    """Return a fundamental score in [0, 100]. Higher = more attractive."""
    points = 0.0
    total = 0.0

    # Valuation (35 pts)
    if metrics.pe_ratio is not None:
        total += 20
        if metrics.pe_ratio <= _PE_CHEAP:
            points += 20
        elif metrics.pe_ratio <= _PE_FAIR:
            points += 10 + ((_PE_FAIR - metrics.pe_ratio) / (_PE_FAIR - _PE_CHEAP)) * 10
        # negative PE (loss-making) → 0
    if metrics.forward_pe is not None:
        total += 15
        if metrics.forward_pe <= _FORWARD_PE_FAIR:
            ratio = metrics.forward_pe / _FORWARD_PE_FAIR
            points += (1 - ratio) * 15 + 7  # capped at 15

    # Quality (40 pts)
    if metrics.profit_margin is not None:
        total += 20
        pts = min(metrics.profit_margin / _PROFIT_MARGIN_GOOD, 1.5) * 20
        points += min(pts, 20)
    if metrics.roe is not None:
        total += 10
        pts = min(metrics.roe / _ROE_GOOD, 1.5) * 10
        points += min(pts, 10)
    if metrics.debt_to_equity is not None:
        total += 10
        if metrics.debt_to_equity <= _DE_MAX:
            points += (1 - metrics.debt_to_equity / _DE_MAX) * 10

    # Risk / beta (15 pts)
    if metrics.beta is not None:
        total += 15
        if _BETA_LOW <= metrics.beta <= _BETA_HIGH:
            points += 15
        elif metrics.beta < _BETA_LOW:
            points += 10  # very low beta — defensive but limited upside
        else:
            points += max(0, 15 - (metrics.beta - _BETA_HIGH) * 10)

    # 52-week position bonus (10 pts)
    if metrics.price_to_52w_high_pct is not None:
        total += 10
        if metrics.price_to_52w_high_pct < -20:
            points += 10  # deep discount from high
        elif metrics.price_to_52w_high_pct < -10:
            points += 5

    if total == 0:
        return 50.0  # insufficient data — neutral
    return round(min(points / total * 100, 100), 1)
