"""Fundamental analysis scoring derived from StockQuote metrics."""
from __future__ import annotations

from ticker_agent.data.models import StockQuote


def score_pe_ratio(pe: float | None) -> float:
    """Score trailing P/E: lower multiples score higher (value-oriented). 0–100."""
    if pe is None or pe <= 0:
        return 50.0  # neutral when unavailable or negative earnings
    if pe < 10:
        return 88.0
    if pe < 15:
        return 78.0
    if pe < 20:
        return 68.0
    if pe < 25:
        return 58.0
    if pe < 35:
        return 48.0
    if pe < 50:
        return 35.0
    return 22.0  # extreme growth premium


def score_52wk_position(
    price: float,
    low: float | None,
    high: float | None,
) -> float:
    """
    Score price position within its 52-week range.
    Lower positions (near 52wk low) suggest potential upside → higher score.
    """
    if not low or not high or high <= low:
        return 50.0
    position = (price - low) / (high - low)  # 0 = at 52wk low, 1 = at 52wk high
    if position < 0.20:
        return 78.0  # near 52wk low — potential value entry
    if position < 0.40:
        return 65.0
    if position < 0.60:
        return 52.0  # mid-range neutral
    if position < 0.80:
        return 40.0
    return 28.0  # near 52wk high — limited near-term upside


def score_beta(beta: float | None) -> float:
    """
    Score market-relative volatility.
    Moderate beta (0.7–1.3) is neutral; extremes reduce score.
    """
    if beta is None:
        return 50.0
    if 0.7 <= beta <= 1.3:
        return 58.0
    if 0.5 <= beta < 0.7:
        return 62.0  # low-beta defensive — slight premium
    if 1.3 < beta <= 1.8:
        return 44.0
    if beta < 0.5:
        return 65.0  # very stable (e.g. utilities)
    return 30.0  # very high beta — speculative


def score_dividend(yield_pct: float | None) -> float:
    """
    Dividend yield as a mild positive factor.
    yfinance returns yield as a decimal (e.g. 0.025 = 2.5%).
    """
    if yield_pct is None or yield_pct == 0:
        return 50.0  # neutral for growth stocks
    pct = yield_pct * 100
    if pct >= 5.0:
        return 80.0
    if pct >= 3.0:
        return 70.0
    if pct >= 1.5:
        return 62.0
    return 55.0


def compute_fundamental_score(quote: StockQuote) -> float:
    """
    Composite fundamental score (0–100) from weighted sub-scores.

    Weights:
      P/E ratio        40%
      52wk position    30%
      Beta             20%
      Dividend yield   10%
    """
    pe_s = score_pe_ratio(quote.pe_ratio)
    wk_s = score_52wk_position(quote.price, quote.fifty_two_week_low, quote.fifty_two_week_high)
    beta_s = score_beta(quote.beta)
    div_s = score_dividend(quote.dividend_yield)
    return round(pe_s * 0.40 + wk_s * 0.30 + beta_s * 0.20 + div_s * 0.10, 2)
