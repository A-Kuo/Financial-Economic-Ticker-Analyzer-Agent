"""Tests for fundamental analysis scoring."""
import pytest

from ticker_agent.analysis.fundamental import (
    score_pe_ratio,
    score_52wk_position,
    score_beta,
    score_dividend,
    compute_fundamental_score,
)
from ticker_agent.data.models import StockQuote


class TestPEScoring:
    def test_pe_none_returns_neutral(self):
        assert score_pe_ratio(None) == 50.0

    def test_pe_negative_returns_neutral(self):
        assert score_pe_ratio(-5.0) == 50.0

    def test_pe_very_cheap(self):
        score = score_pe_ratio(8.0)
        assert score > 80  # Cheap valuation scores high

    def test_pe_reasonable(self):
        score = score_pe_ratio(16.0)
        assert 60 < score < 80  # Fair value

    def test_pe_expensive(self):
        score = score_pe_ratio(50.0)
        assert score < 40  # Expensive scores lower


class Test52WeekPosition:
    def test_position_none_returns_neutral(self):
        assert score_52wk_position(100, None, None) == 50.0

    def test_position_at_low(self):
        score = score_52wk_position(100, 100, 200)
        assert score > 70  # Near 52wk low is bullish

    def test_position_at_high(self):
        score = score_52wk_position(200, 100, 200)
        assert score < 35  # Near 52wk high is bearish

    def test_position_midrange(self):
        score = score_52wk_position(150, 100, 200)
        assert 40 < score < 60  # Middle is neutral


class TestBetaScoring:
    def test_beta_none_returns_neutral(self):
        assert score_beta(None) == 50.0

    def test_beta_moderate(self):
        score = score_beta(1.0)
        assert score > 55  # Market-correlated is acceptable

    def test_beta_low(self):
        score = score_beta(0.6)
        assert score > 60  # Low volatility scores higher

    def test_beta_high(self):
        score = score_beta(2.0)
        assert score < 45  # High volatility scores lower


class TestDividendScoring:
    def test_dividend_none_returns_neutral(self):
        assert score_dividend(None) == 50.0

    def test_dividend_zero_returns_neutral(self):
        assert score_dividend(0.0) == 50.0

    def test_dividend_high(self):
        score = score_dividend(0.05)  # 5% yield
        assert score > 70

    def test_dividend_low(self):
        score = score_dividend(0.01)  # 1% yield
        assert score > 50


class TestCompositeFundamental:
    def test_fundamental_all_good_metrics(self):
        quote = StockQuote(
            symbol="TEST",
            price=100.0,
            open=95.0,
            high=102.0,
            low=94.0,
            volume=1000000,
            pe_ratio=15.0,  # Fair
            fifty_two_week_low=80.0,
            fifty_two_week_high=120.0,
            beta=1.0,
            dividend_yield=0.03,
        )
        score = compute_fundamental_score(quote)
        assert 0 <= score <= 100
        assert score > 50  # Good metrics should score above neutral

    def test_fundamental_all_poor_metrics(self):
        quote = StockQuote(
            symbol="TEST",
            price=100.0,
            open=95.0,
            high=102.0,
            low=94.0,
            volume=1000000,
            pe_ratio=100.0,  # Very expensive
            fifty_two_week_low=100.0,
            fifty_two_week_high=105.0,  # Near high
            beta=3.0,  # Very volatile
            dividend_yield=0.0,
        )
        score = compute_fundamental_score(quote)
        assert 0 <= score <= 100
        assert score < 50  # Poor metrics should score below neutral
