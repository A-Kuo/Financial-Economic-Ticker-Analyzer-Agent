"""Tests for composite scoring logic."""
import pytest

from ticker_agent.analysis.scoring import (
    score_technical,
    signal_from_score,
    compute_composite_score,
)
from ticker_agent.config import ScoringWeights
from ticker_agent.data.models import TechnicalSignals


class TestTechnicalScoring:
    def test_technical_no_signals_neutral(self):
        signals = TechnicalSignals(symbol="TEST")
        score = score_technical(signals)
        assert score == 50.0  # Empty signals → neutral

    def test_technical_oversold_bullish(self):
        signals = TechnicalSignals(
            symbol="TEST",
            rsi_14=25.0,  # Oversold
        )
        score = score_technical(signals)
        assert score > 50  # Oversold is bullish

    def test_technical_overbought_bearish(self):
        signals = TechnicalSignals(
            symbol="TEST",
            rsi_14=75.0,  # Overbought
        )
        score = score_technical(signals)
        assert score < 50  # Overbought is bearish

    def test_technical_golden_cross_bullish(self):
        signals = TechnicalSignals(
            symbol="TEST",
            sma_20=105.0,
            sma_50=100.0,
            sma_200=95.0,
        )
        score = score_technical(signals)
        assert score > 50  # Golden cross is bullish

    def test_technical_death_cross_bearish(self):
        signals = TechnicalSignals(
            symbol="TEST",
            sma_20=95.0,
            sma_50=100.0,
            sma_200=105.0,
        )
        score = score_technical(signals)
        assert score < 50  # Death cross is bearish

    def test_technical_positive_macd_bullish(self):
        signals = TechnicalSignals(
            symbol="TEST",
            macd=0.5,
            macd_signal=0.3,
            macd_histogram=0.2,  # Positive = bullish
        )
        score = score_technical(signals)
        assert score > 50


class TestSignalMapping:
    def test_signal_strong_buy(self):
        signal, conf = signal_from_score(80.0)
        assert signal == "STRONG_BUY"
        assert 0.5 < conf <= 1.0

    def test_signal_buy(self):
        signal, conf = signal_from_score(65.0)
        assert signal == "BUY"
        assert 0.3 < conf < 0.7

    def test_signal_hold(self):
        signal, conf = signal_from_score(50.0)
        assert signal == "HOLD"
        assert conf == 0.50

    def test_signal_sell(self):
        signal, conf = signal_from_score(35.0)
        assert signal == "SELL"
        assert 0.3 < conf < 0.7

    def test_signal_strong_sell(self):
        signal, conf = signal_from_score(10.0)
        assert signal == "STRONG_SELL"
        assert 0.5 < conf <= 1.0


class TestCompositeScoring:
    def test_composite_calculates_correctly(self):
        weights = ScoringWeights(technical=0.4, fundamental=0.3, sentiment=0.3)
        score = compute_composite_score(
            symbol="TEST",
            technical_score=80.0,
            fundamental_score=70.0,
            sentiment_score=60.0,
            weights=weights,
        )
        expected = 0.4 * 80 + 0.3 * 70 + 0.3 * 60  # = 71.0
        assert score.composite_score == expected

    def test_composite_generates_signal(self):
        weights = ScoringWeights(technical=0.4, fundamental=0.3, sentiment=0.3)
        score = compute_composite_score(
            symbol="TEST",
            technical_score=85.0,
            fundamental_score=75.0,
            sentiment_score=70.0,
            weights=weights,
        )
        assert score.signal == "STRONG_BUY"
        assert score.confidence > 0.5

    def test_composite_with_reasoning(self):
        weights = ScoringWeights()
        score = compute_composite_score(
            symbol="AAPL",
            technical_score=50.0,
            fundamental_score=50.0,
            sentiment_score=50.0,
            weights=weights,
            reasoning="This is a test reasoning.",
        )
        assert score.reasoning == "This is a test reasoning."
