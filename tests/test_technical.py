"""Tests for technical indicator computation."""
import pandas as pd
import pytest

from ticker_agent.analysis.technical import (
    compute_rsi,
    compute_macd,
    compute_bollinger_bands,
    compute_sma,
    compute_volume_ratio,
    compute_signals,
)
from ticker_agent.data.models import StockQuote


class TestRSI:
    def test_rsi_insufficient_data(self):
        prices = pd.Series([100, 101, 102])
        assert compute_rsi(prices, period=14) is None

    def test_rsi_range(self):
        # Create a synthetic price series with clear uptrend
        prices = pd.Series(list(range(100, 150)) + [145, 140, 135, 130])
        rsi = compute_rsi(prices, period=14)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_rsi_oversold(self):
        # Sharp downtrend should produce low RSI
        prices = pd.Series(list(range(100, 50, -1)))
        rsi = compute_rsi(prices, period=14)
        assert rsi is not None
        assert rsi < 30  # Oversold territory

    def test_rsi_overbought(self):
        # Sharp uptrend should produce high RSI
        prices = pd.Series(list(range(50, 101)))
        rsi = compute_rsi(prices, period=14)
        assert rsi is not None
        assert rsi > 70  # Overbought territory


class TestMACD:
    def test_macd_insufficient_data(self):
        prices = pd.Series([100, 101, 102])
        macd, sig, hist = compute_macd(prices)
        assert macd is None and sig is None and hist is None

    def test_macd_returns_tuple(self):
        prices = pd.Series(list(range(100, 150)))
        macd, sig, hist = compute_macd(prices)
        assert macd is not None
        assert sig is not None
        assert hist is not None

    def test_macd_histogram_direction(self):
        # Uptrend: histogram should be positive near the end
        prices = pd.Series(list(range(100, 150)))
        _, _, hist = compute_macd(prices)
        assert hist is not None
        assert hist > 0  # Rising prices → positive histogram


class TestBollingerBands:
    def test_bb_insufficient_data(self):
        prices = pd.Series([100, 101, 102])
        upper, mid, lower = compute_bollinger_bands(prices, period=20)
        assert upper is None and mid is None and lower is None

    def test_bb_order(self):
        prices = pd.Series(list(range(100, 150)))
        upper, mid, lower = compute_bollinger_bands(prices, period=20)
        assert lower is not None
        assert mid is not None
        assert upper is not None
        assert lower < mid < upper

    def test_bb_symmetry(self):
        # With normal distribution, bands should be symmetric around middle
        prices = pd.Series([100] * 50)  # Constant price
        upper, mid, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
        if upper and mid and lower:
            # At constant price, std dev → 0, bands collapse to SMA
            assert abs(upper - mid) < 0.01


class TestSMA:
    def test_sma_insufficient_data(self):
        prices = pd.Series([100, 101, 102])
        assert compute_sma(prices, period=20) is None

    def test_sma_calculation(self):
        prices = pd.Series([100, 100, 100, 100, 100])
        sma = compute_sma(prices, period=5)
        assert sma == 100.0

    def test_sma_uptrend(self):
        prices = pd.Series(list(range(100, 150)))
        sma_20 = compute_sma(prices, period=20)
        assert sma_20 is not None
        assert sma_20 > 100  # Average of recent prices is high


class TestVolumeRatio:
    def test_volume_ratio_insufficient_data(self):
        volumes = pd.Series([1000, 2000, 3000])
        assert compute_volume_ratio(volumes, period=10) is None

    def test_volume_ratio_spike(self):
        volumes = pd.Series([1000] * 10 + [5000])  # Spike to 5x average
        ratio = compute_volume_ratio(volumes, period=10)
        assert ratio is not None
        assert ratio >= 4.5  # Close to 5x

    def test_volume_ratio_normal(self):
        volumes = pd.Series([1000] * 20)
        ratio = compute_volume_ratio(volumes, period=10)
        assert ratio is not None
        assert 0.9 < ratio < 1.1  # Around 1x


class TestComputeSignals:
    def test_signals_with_history(self):
        # Synthetic OHLCV data
        df = pd.DataFrame({
            "Open": list(range(100, 150)),
            "High": list(range(101, 151)),
            "Low": list(range(99, 149)),
            "Close": list(range(100, 150)),
            "Volume": [1000] * 50,
        })
        signals = compute_signals("TEST", df, fifty_two_week_high=150)
        assert signals.symbol == "TEST"
        assert signals.rsi_14 is not None or signals.macd is not None
