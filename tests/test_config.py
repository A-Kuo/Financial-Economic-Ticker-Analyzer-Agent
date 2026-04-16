"""Tests for configuration loading and validation."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from ticker_agent.config import load_config, AppConfig, TierConfig


class TestConfigLoading:
    def test_load_default_config(self):
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.agent.model == "llama3.2"
        assert len(cfg.tickers.tier1) > 0
        assert len(cfg.tickers.tier2) > 0

    def test_tier_of_tier1(self):
        cfg = load_config()
        symbol = cfg.tickers.tier1[0]
        assert cfg.tickers.tier_of(symbol) == 1

    def test_tier_of_tier2(self):
        cfg = load_config()
        symbol = cfg.tickers.tier2[0]
        assert cfg.tickers.tier_of(symbol) == 2

    def test_tier_of_unknown(self):
        cfg = load_config()
        assert cfg.tickers.tier_of("UNKNOWN") == 0

    def test_all_tickers(self):
        cfg = load_config()
        all_tickers = cfg.tickers.all_tickers()
        assert len(all_tickers) == len(cfg.tickers.tier1) + len(cfg.tickers.tier2)
        assert all(s in all_tickers for s in cfg.tickers.tier1)
        assert all(s in all_tickers for s in cfg.tickers.tier2)


class TestCustomConfig:
    def test_load_custom_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "settings.yaml"
            data = {
                "tickers": {
                    "tier1": ["AAPL", "MSFT"],
                    "tier2": ["AMD", "INTC"],
                },
                "agent": {
                    "model": "mistral",
                    "news_lookback_hours": 48,
                },
                "scoring": {
                    "weights": {
                        "technical": 0.5,
                        "fundamental": 0.3,
                        "sentiment": 0.2,
                    }
                },
            }
            with open(config_file, "w") as f:
                yaml.dump(data, f)

            cfg = load_config(str(config_file))
            assert cfg.agent.model == "mistral"
            assert cfg.agent.news_lookback_hours == 48
            assert cfg.scoring.technical == 0.5
            assert cfg.tickers.tier_of("AAPL") == 1
            assert cfg.tickers.tier_of("AMD") == 2


class TestEnvironmentOverrides:
    def test_env_overrides_yaml(self):
        old_news_key = os.environ.get("NEWS_API_KEY")
        old_model = os.environ.get("OLLAMA_MODEL")
        try:
            os.environ["NEWS_API_KEY"] = "test_key_123"
            os.environ["OLLAMA_MODEL"] = "llama3.3"
            cfg = load_config()
            assert cfg.news_api_key == "test_key_123"
            assert cfg.agent.model == "llama3.3"
        finally:
            if old_news_key:
                os.environ["NEWS_API_KEY"] = old_news_key
            else:
                os.environ.pop("NEWS_API_KEY", None)
            if old_model:
                os.environ["OLLAMA_MODEL"] = old_model
            else:
                os.environ.pop("OLLAMA_MODEL", None)
