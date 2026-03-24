# Financial-Economic-Ticker-Analyzer-Agent

> **Agentic market intelligence for real-time ticker analysis**
> _Market Intelligence Layer — Stage 2 of the FinancialPipeline_

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20llama3.2-orange)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What This Does

Given a stock ticker symbol, this agent:

1. **Fetches** real-time price + fundamentals via `yfinance`
2. **Fetches** recent news via NewsAPI
3. **Computes** technical indicators (RSI, MACD, Bollinger Bands, SMA/EMA crossovers, ATR)
4. **Scores** fundamentals (P/E, ROE, profit margin, D/E, beta, 52-week position)
5. **Analyses** news sentiment using a local Ollama LLM (`llama3.2`)
6. **Blends** all three into a composite 0–100 score → signal (`STRONG_BUY` … `STRONG_SELL`)
7. **Generates** a structured market intelligence narrative via Ollama
8. **Persists** everything to SQLite and **exports** reports (JSON/Markdown)
9. **Runs** as a CLI one-shot tool _or_ a two-tier background daemon

---

## FinancialPipeline Architecture

This repo is **Stage 2** in a three-stage financial intelligence pipeline:

```
┌─────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│   FinDocAnalyzer    │────▶│  Ticker-Analyzer-Agent   │────▶│  Agentic-Viz        │
│   (Stage 1)         │     │  (Stage 2 — this repo)   │     │  Framework (Stage 3)│
│                     │     │                          │     │                     │
│  SEC filing text    │     │  Ticker symbol           │     │  Structured JSON    │
│  ──────────────▶    │     │  + market data           │     │  ──────────────▶    │
│  Structured JSON    │     │  ──────────────▶         │     │  Interactive        │
│  + ticker symbol    │     │  Market intelligence     │     │  dashboards         │
└─────────────────────┘     └──────────────────────────┘     └─────────────────────┘
         │                              │                              │
         ▼                              ▼                              ▼
    SEC EDGAR filings           Yahoo Finance + NewsAPI         Plotly / Streamlit
    QLoRA fine-tuned LLM        Ollama llama3.2 (local)        Any structured data
```

### How the Three Repos Differ

| Aspect | [FinDocAnalyzer](https://github.com/A-Kuo/Fine-Tuned-SEC-Filing-Extraction-Pipeline) | **Ticker-Analyzer-Agent** ← you are here | [Agentic-Viz-Framework](https://github.com/A-Kuo/Agentic-Visualization-Framework) |
|--------|------------------------|--------------------------|----------------------|
| **Input** | Document (10-K/10-Q text) | Ticker symbol + live market data | Any structured JSON / API |
| **Output** | Structured financials JSON | Market insights, signals, sentiment | Dashboards, charts, drill-downs |
| **Timeframe** | Historical (quarterly/annual filings) | Real-time / current | N/A (presentation) |
| **LLM role** | QLoRA fine-tuned Llama 3.1 8B for extraction | Ollama llama3.2 for sentiment + narrative | Optional (agent-driven chart selection) |
| **Data source** | SEC EDGAR | Yahoo Finance, NewsAPI | Upstream stage outputs |
| **Audience** | Financial data engineers, compliance | Traders, analysts, quant devs | Data viz engineers, dashboards |

### Related Repositories

| Repository | Role | Consumes | Produces |
|-----------|------|----------|----------|
| [FinDocAnalyzer](https://github.com/A-Kuo/Fine-Tuned-SEC-Filing-Extraction-Pipeline) | Stage 1 — SEC filing extraction | Raw EDGAR filings | Structured financial JSON + ticker |
| **[Ticker-Analyzer-Agent](https://github.com/A-Kuo/Financial-Economic-Ticker-Analyzer-Agent)** | **Stage 2 — Market intelligence** | Ticker symbol + market data | Signals, sentiment, narratives |
| [Agentic-Viz-Framework](https://github.com/A-Kuo/Agentic-Visualization-Framework) | Stage 3 — Presentation | Structured JSON from Stage 1 or 2 | Interactive dashboards |

---

## Project Structure

```
Financial-Economic-Ticker-Analyzer-Agent/
├── cli.py                          # Click CLI entry point
├── pyproject.toml                  # Package metadata + tooling config
├── .env.example                    # Environment variable template
├── .gitignore
│
├── config/
│   └── settings.yaml               # Tickers, intervals, LLM, scoring weights
│
├── src/ticker_agent/
│   ├── config.py                   # YAML loader + env overrides
│   │
│   ├── data/
│   │   ├── models.py               # SQLAlchemy ORM: TickerSnapshot, NewsArticle, AnalysisResult, Alert
│   │   ├── database.py             # Engine, session_scope, init_db
│   │   ├── stock_fetcher.py        # yfinance wrapper (snapshot + OHLCV history)
│   │   └── news_fetcher.py         # NewsAPI wrapper
│   │
│   ├── analysis/
│   │   ├── technical.py            # RSI, MACD, Bollinger Bands, SMA/EMA, ATR, volume
│   │   ├── fundamental.py          # P/E, ROE, D/E, beta, 52-week position scoring
│   │   └── scoring.py              # Composite blender → 0-100 score + signal
│   │
│   ├── agents/
│   │   ├── base_agent.py           # Abstract Ollama agent (retry, timeout, logging)
│   │   ├── news_agent.py           # Sentiment analysis per article + aggregate
│   │   ├── analysis_agent.py       # Full market intelligence narrative generator
│   │   └── orchestrator.py         # Two-tier pipeline coordinator + persistence
│   │
│   ├── output/
│   │   ├── console.py              # Rich terminal renderer
│   │   └── reports.py              # JSON / Markdown report writer
│   │
│   └── scheduler/
│       └── runner.py               # Two-tier daemon (schedule library + signal handling)
│
├── data/                           # SQLite database (runtime, gitignored)
├── logs/                           # Log files (runtime, gitignored)
├── reports/                        # Generated reports (runtime, gitignored)
└── scripts/
    └── cron_example.txt            # Cron scheduling examples
```

---

## Two-Tier Monitoring

```
Market Hours (9:30am–4:00pm ET)
          │
          ├── Tier 1 (every 5 min)  ──▶  AAPL, NVDA, TSLA, MSFT
          │   Price + technicals + fast score (no LLM narrative)
          │
          └── Tier 2 (every 30 min) ──▶  GOOGL, AMZN, META, JPM, V, BRK-B
              Full pipeline: price + news + LLM sentiment + LLM narrative
```

---

## Prerequisites

- **Python 3.10+**
- **[Ollama](https://ollama.com/)** running locally with `llama3.2` pulled
- **NewsAPI key** (free tier at [newsapi.org](https://newsapi.org/register))

---

## Setup

```bash
git clone https://github.com/A-Kuo/Financial-Economic-Ticker-Analyzer-Agent.git
cd Financial-Economic-Ticker-Analyzer-Agent

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .

cp .env.example .env
# Edit .env: set NEWS_API_KEY

# Pull the LLM
ollama pull llama3.2
```

---

## Usage

### One-shot analysis

```bash
# Analyse a single ticker (full Tier-2 report)
ticker-agent analyse AAPL

# Multiple tickers — batch summary table
ticker-agent analyse AAPL MSFT NVDA TSLA GOOGL

# Fast mode (no LLM narrative, scores only)
ticker-agent analyse AAPL --tier 1 --no-llm

# Save Markdown report
ticker-agent analyse AAPL MSFT --format markdown
```

### Background daemon

```bash
# Two-tier daemon with default tickers from config/settings.yaml
ticker-agent watch

# Custom tickers
ticker-agent watch --tier1 AAPL NVDA --tier2 MSFT GOOGL AMZN
```

### Other commands

```bash
ticker-agent health          # Check Ollama + database connectivity
ticker-agent report --last 5 # List most recent saved reports
ticker-agent --help
```

---

## Scoring Methodology

### Sub-scores (each 0–100)

| Sub-score | Weight | Key signals |
|-----------|--------|-------------|
| **Technical** | 40% | RSI zone, MACD histogram direction, price vs SMA-20/50, golden/death cross, Bollinger %B |
| **Fundamental** | 35% | P/E vs fair-value thresholds, profit margin, ROE, D/E leverage, beta, 52-week discount |
| **Sentiment** | 25% | NewsAPI headlines → Ollama llama3.2 → per-article score → aggregate |

### Signal thresholds

| Score | Signal |
|-------|--------|
| 80–100 | `STRONG_BUY` |
| 60–79 | `BUY` |
| 40–59 | `HOLD` |
| 20–39 | `SELL` |
| 0–19 | `STRONG_SELL` |

---

## Pipeline Integration

### Receiving data from FinDocAnalyzer (Stage 1)

FinDocAnalyzer can POST extracted ticker symbols to this service via webhook. Configure in `.env`:

```env
FINDOC_WEBHOOK_SECRET=your_secret
```

The orchestrator exposes a `/ingest` endpoint (coming in v0.2) that accepts the inter-service JSON schema.

### Sending data to Agentic-Viz-Framework (Stage 3)

Each `TickerAnalysis` serialises to the pipeline payload format via `to_pipeline_payload()`:

```json
{
  "ticker": "AAPL",
  "analysed_at": "2026-03-24T14:30:00",
  "market_context": {
    "current_price": 189.52,
    "composite_score": 74.2,
    "signal": "BUY",
    "sentiment_label": "bullish"
  },
  "narrative": "...",
  "key_catalysts": ["..."],
  "key_risks": ["..."]
}
```

---

## Configuration

All settings live in `config/settings.yaml` with `.env` override support.

Key sections:

| Section | Controls |
|---------|---------|
| `tickers` | Default ticker watchlist |
| `monitoring` | Tier intervals, market hours, timezone |
| `data` | History lookback, NewsAPI article count |
| `analysis.technical` | RSI/MACD/BB periods |
| `analysis.scoring` | Sub-score weights + alert thresholds |
| `llm` | Ollama model, temperature, timeout |
| `output` | Console colour, report format, retention |
| `pipeline` | Webhook paths for FinDocAnalyzer + Viz integration |

---

## License

MIT — see [LICENSE](LICENSE).
