"""Configuration loader — merges settings.yaml with environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Project root = three levels up from this file (src/ticker_agent/config.py)
_ROOT = Path(__file__).parent.parent.parent


@dataclass
class TierConfig:
    tier1: list[str] = field(default_factory=list)
    tier2: list[str] = field(default_factory=list)

    def all_tickers(self) -> list[str]:
        return self.tier1 + self.tier2

    def tier_of(self, symbol: str) -> int:
        if symbol in self.tier1:
            return 1
        if symbol in self.tier2:
            return 2
        return 0


@dataclass
class AgentConfig:
    model: str = "llama3.2"
    news_lookback_hours: int = 24
    max_news_articles: int = 5
    analysis_depth: str = "quick"


@dataclass
class AlertThresholds:
    price_change_pct: float = 5.0
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    volume_spike_ratio: float = 2.0
    sentiment_negative_floor: float = -0.5


@dataclass
class ScheduleConfig:
    run_times: list[str] = field(default_factory=lambda: ["14:00", "21:00"])
    tier1_interval_minutes: int = 60


@dataclass
class ScoringWeights:
    technical: float = 0.40
    fundamental: float = 0.30
    sentiment: float = 0.30


@dataclass
class AppConfig:
    tickers: TierConfig = field(default_factory=TierConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    db_path: str = "data/ticker_agent.db"
    reports_dir: str = "reports"
    logs_dir: str = "logs"
    news_api_key: str = ""
    ollama_host: str = "http://localhost:11434"


def load_config(config_path: str | None = None) -> AppConfig:
    """Load AppConfig from YAML file, then overlay environment variables."""
    if config_path is None:
        config_path = str(_ROOT / "config" / "settings.yaml")

    raw: dict = {}
    if Path(config_path).exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}

    cfg = AppConfig()

    # Tickers
    tickers_raw = raw.get("tickers", {})
    cfg.tickers = TierConfig(
        tier1=[str(s) for s in tickers_raw.get("tier1", [])],
        tier2=[str(s) for s in tickers_raw.get("tier2", [])],
    )

    # Agent
    agent_raw = raw.get("agent", {})
    cfg.agent = AgentConfig(
        model=agent_raw.get("model", "llama3.2"),
        news_lookback_hours=int(agent_raw.get("news_lookback_hours", 24)),
        max_news_articles=int(agent_raw.get("max_news_articles", 5)),
        analysis_depth=agent_raw.get("analysis_depth", "quick"),
    )

    # Thresholds
    thresh_raw = raw.get("thresholds", {})
    cfg.thresholds = AlertThresholds(
        price_change_pct=float(thresh_raw.get("price_change_pct", 5.0)),
        rsi_overbought=float(thresh_raw.get("rsi_overbought", 70.0)),
        rsi_oversold=float(thresh_raw.get("rsi_oversold", 30.0)),
        volume_spike_ratio=float(thresh_raw.get("volume_spike_ratio", 2.0)),
        sentiment_negative_floor=float(thresh_raw.get("sentiment_negative_floor", -0.5)),
    )

    # Schedule
    sched_raw = raw.get("schedule", {})
    cfg.schedule = ScheduleConfig(
        run_times=sched_raw.get("run_times", ["14:00", "21:00"]),
        tier1_interval_minutes=int(sched_raw.get("tier1_interval_minutes", 60)),
    )

    # Scoring weights
    scoring_raw = raw.get("scoring", {}).get("weights", {})
    cfg.scoring = ScoringWeights(
        technical=float(scoring_raw.get("technical", 0.40)),
        fundamental=float(scoring_raw.get("fundamental", 0.30)),
        sentiment=float(scoring_raw.get("sentiment", 0.30)),
    )

    # Storage paths
    storage_raw = raw.get("storage", {})
    cfg.db_path = storage_raw.get("db_path", "data/ticker_agent.db")
    cfg.reports_dir = storage_raw.get("reports_dir", "reports")
    cfg.logs_dir = storage_raw.get("logs_dir", "logs")

    # Environment overrides (highest priority)
    cfg.news_api_key = os.getenv("NEWS_API_KEY", "")
    cfg.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_env = os.getenv("OLLAMA_MODEL", "")
    if model_env:
        cfg.agent.model = model_env

    return cfg
