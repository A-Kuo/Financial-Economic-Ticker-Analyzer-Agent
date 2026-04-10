# Financial-Economic-Ticker-Analyzer-Agent

**Agentic market intelligence for real-time ticker analysis**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20llama3.2-orange)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production--Grade-brightgreen.svg)]()

> *"A stock price is a number. Market intelligence is context — why the number moved, what the signal means, and what comes next. This agent produces the latter."*

---

## What This Agent Does

Given a stock ticker symbol, this system runs a full agentic analysis pipeline:

1. **Fetches** real-time price data and fundamentals via `yfinance`
2. **Fetches** recent news headlines via NewsAPI
3. **Computes** technical indicators — RSI, MACD, Bollinger Bands, SMA/EMA crossovers, ATR, volume analysis
4. **Scores** fundamentals — P/E ratio, ROE, profit margin, debt/equity, beta, 52-week position
5. **Analyzes** news sentiment using a locally-running Ollama LLM (`llama3.2`) — no cloud API required
6. **Blends** all three signal streams into a composite 0–100 score mapped to a trading signal (`STRONG_BUY` → `STRONG_SELL`)
7. **Generates** a structured market intelligence narrative explaining the signal in plain language
8. **Persists** everything to SQLite and exports structured reports (JSON and Markdown)
9. **Runs** as a one-shot CLI tool or a two-tier background daemon for continuous monitoring

The result is not a spreadsheet of numbers — it is a structured, reasoned judgment about a security that incorporates quantitative signals and qualitative context simultaneously.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TICKER-ANALYZER-AGENT                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   DATA LAYER     │ │  ANALYSIS LAYER  │ │   AGENT LAYER    │
│                  │ │                  │ │                  │
│  stock_fetcher   │ │  technical.py    │ │  news_agent.py   │
│  (yfinance)      │ │  RSI, MACD,      │ │  Per-article     │
│                  │ │  Bollinger,      │ │  sentiment via   │
│  news_fetcher    │ │  SMA/EMA, ATR    │ │  Ollama llama3.2 │
│  (NewsAPI)       │ │                  │ │                  │
│                  │ │  fundamental.py  │ │  analysis_agent  │
│  SQLAlchemy ORM  │ │  P/E, ROE, D/E,  │ │  Full narrative  │
│  (SQLite)        │ │  beta, 52-wk pos │ │  generation      │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                   ┌──────────────────┐
                   │  scoring.py      │
                   │  Composite blend │
                   │  0-100 score     │
                   │  → SIGNAL        │
                   └────────┬─────────┘
                            │
               ┌────────────┼────────────┐
               ▼            ▼            ▼
    ┌──────────────┐  ┌──────────┐  ┌──────────────┐
    │  Console     │  │  SQLite  │  │  JSON/MD     │
    │  Rich output │  │  Persist │  │  Reports     │
    └──────────────┘  └──────────┘  └──────────────┘
```

### Two-Tier Monitoring Architecture

The daemon mode implements a two-tier scheduling strategy that mirrors professional trading desk workflows:

```
Market Hours (9:30am–4:00pm ET)
          │
          ├── Tier 1 (every 5 min) ──▶  High-priority: AAPL, NVDA, TSLA, MSFT
          │   Price + technicals + fast score
          │   (no LLM narrative — low latency)
          │
          └── Tier 2 (every 30 min) ──▶  Full watchlist: GOOGL, AMZN, META, JPM, V, BRK-B
              Full pipeline: price + news + LLM sentiment + LLM narrative
              (complete analysis — accepts higher latency)
```

Tier 1 gives you fast signals with no model invocation overhead. Tier 2 gives you complete context at a cadence appropriate for LLM inference.

---

## Integration with the Financial Intelligence Pipeline

This agent is the **market intelligence layer** in a five-repo financial intelligence stack. It sits at the analytical core — receiving structured financial data from the document extraction layer and producing enriched market intelligence that feeds downstream sentiment and temporal modeling.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    FINANCIAL INTELLIGENCE PIPELINE                        │
└──────────────────────────────────────────────────────────────────────────┘

  [1] SEC EXTRACTION          [2] ABSA SENTIMENT          [3] THIS REPO
  ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
  │ Fine-Tuned-SEC-  │        │ Transformer-ABSA │        │ Financial-       │
  │ Filing-Extraction│──────▶│ Aspect sentiment │──────▶│ Economic-Ticker  │
  │ Pipeline         │        │ on MD&A, risk    │        │ Analyzer-Agent   │
  │                  │        │ factors, earnings│        │                  │
  │ QLoRA Llama 3.1  │        │ calls            │        │ Technical +      │
  │ → structured     │        │ → per-aspect     │        │ fundamental +    │
  │   financial JSON │        │   sentiment maps │        │ LLM sentiment    │
  └──────────────────┘        └──────────────────┘        └────────┬─────────┘
                                                                    │
                                    ┌───────────────────────────────┘
                                    ▼
  [4] TEMPORAL MODELING       [5] PLATFORM ANALYTICS
  ┌──────────────────┐        ┌──────────────────┐
  │ Tax-Data-System  │        │ App-Store-Metrics │
  │ with S4          │        │                  │
  │ Architecture     │        │ Mobile market    │
  │                  │        │ dynamics and     │
  │ S4 state-space   │        │ platform         │
  │ models for long- │        │ analytics for    │
  │ range time series│        │ alternative data │
  └──────────────────┘        └──────────────────┘
```

### How upstream data flows into this agent

**From Fine-Tuned-SEC-Filing-Extraction-Pipeline:**
The SEC extraction pipeline produces structured JSON containing ticker symbols, revenue figures, net income, and other fundamentals extracted from 10-K/10-Q/8-K filings. This agent can receive that data in two modes:

- **Database-linked**: FinDocAnalyzer writes to PostgreSQL; this agent polls for new ticker symbols
- **Webhook**: FinDocAnalyzer POSTs to this agent's `/ingest` endpoint when a new filing is processed

```python
# The inter-service payload FinDocAnalyzer sends:
{
  "extraction_id": "uuid",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "financials": {
    "revenue": 394_328_000_000,
    "net_income": 99_803_000_000,
    "filing_date": "2024-09-28"
  }
}
# → This agent enriches with real-time market context and LLM analysis
```

**From Transformer-Aspect-Based-Sentiment-Analysis:**
The ABSA pipeline extracts aspect-level sentiment signals from SEC filings — *which specific business dimensions* management is positive or negative about. This agent can ingest those signals as a fourth input to the composite score:

```python
# ABSA aspect sentiment signals feeding the composite score:
{
  "supply_chain": "negative",     # → adjusts fundamental score down
  "revenue_outlook": "positive",  # → adjusts fundamental score up
  "regulatory": "neutral"         # → no adjustment
}
# When ABSA signals are available, scoring.py weights them at 15%
# (reducing technical weight from 40% to 35%, fundamental from 35% to 30%)
```

### Scoring Methodology

| Sub-score | Default Weight | Key Signals |
|-----------|----------------|-------------|
| **Technical** | 40% | RSI zone, MACD histogram direction, price vs SMA-20/50, golden/death cross, Bollinger %B |
| **Fundamental** | 35% | P/E vs fair-value thresholds, profit margin, ROE, D/E leverage, beta, 52-week discount |
| **Sentiment** | 25% | NewsAPI headlines → Ollama llama3.2 → per-article score → aggregate |

| Score | Signal |
|-------|--------|
| 80–100 | `STRONG_BUY` |
| 60–79 | `BUY` |
| 40–59 | `HOLD` |
| 20–39 | `SELL` |
| 0–19 | `STRONG_SELL` |

---

## Technical Approach

### Agent Architecture

The system uses a **multi-agent pipeline** pattern rather than a monolithic analyzer:

- `base_agent.py` — Abstract Ollama agent with retry logic, timeout handling, and structured logging
- `news_agent.py` — Specialized agent that processes individual articles, scores sentiment (-1 to +1), and produces an aggregate sentiment label
- `analysis_agent.py` — Synthesis agent that takes all computed signals and generates a structured market intelligence narrative
- `orchestrator.py` — Pipeline coordinator that sequences agents, manages persistence, and handles the two-tier scheduling

Each agent calls Ollama locally with structured prompts. No cloud API keys are needed for inference. The LLM reasoning layer runs entirely on the local machine.

### Data Sources

| Source | Data | Update Frequency |
|--------|------|-----------------|
| Yahoo Finance (`yfinance`) | Price, volume, OHLCV history, fundamentals | Real-time / daily |
| NewsAPI | Headlines and article metadata | Hourly |
| SEC EDGAR (via FinDocAnalyzer) | Quarterly/annual fundamental data | Quarterly |
| Transformer-ABSA | Aspect sentiment from filing text | On new filing |

### Output Format

Each analysis produces a `TickerAnalysis` object that serializes to the pipeline payload:

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
  "sub_scores": {
    "technical": 78.1,
    "fundamental": 71.4,
    "sentiment": 68.9
  },
  "narrative": "AAPL presents a BUY signal at current levels...",
  "key_catalysts": ["iPhone 17 cycle setup", "Services revenue acceleration"],
  "key_risks": ["China macro exposure", "Elevated P/E vs. peers"],
  "raw_indicators": { "rsi": 58.2, "macd_histogram": 0.34, "bb_position": 0.61 }
}
```

---

## Business Value

### Who Uses This

**Individual quant developers and traders** who want institutional-quality analysis without paying for Bloomberg Terminal data subscriptions. The system replicates the workflow of a junior sell-side analyst — data gathering, technical screening, fundamental scoring, news triage, and report generation — in a local, automated, and customizable package.

**Financial data engineers** integrating SEC filing data with live market context. The pipeline architecture makes it straightforward to trigger market analysis automatically when new quarterly filings are processed.

**Research teams and fintech startups** building on top of the pipeline. The structured JSON output format and webhook integration points make this a composable component in larger financial intelligence systems.

### Why Local LLM

Running Ollama llama3.2 locally rather than calling OpenAI's API provides three advantages relevant to financial use cases:

1. **No data leakage** — sensitive ticker positions and portfolio composition never leave the machine
2. **No per-call cost** — high-frequency Tier 1 monitoring is not economically viable at API pricing
3. **Deterministic deployment** — the analysis behavior does not change with OpenAI model updates

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

ollama pull llama3.2
```

---

## Usage Examples

### One-Shot Analysis

```bash
# Analyze a single ticker — full report
ticker-agent analyse AAPL

# Batch summary table for a watchlist
ticker-agent analyse AAPL MSFT NVDA TSLA GOOGL

# Fast mode: technical + fundamental only, no LLM (Tier 1)
ticker-agent analyse AAPL --tier 1 --no-llm

# Export Markdown report
ticker-agent analyse AAPL MSFT --format markdown
```

Sample output:
```
╔══════════════════════════════════════════════════════════╗
║  AAPL  Apple Inc.  |  $189.52  |  BUY  (74.2/100)      ║
╠══════════════════════════════════════════════════════════╣
║  Technical: 78.1   Fundamental: 71.4   Sentiment: 68.9   ║
╠══════════════════════════════════════════════════════════╣
║  RSI: 58.2  MACD: +0.34  Bollinger: 61%               ║
╠══════════════════════════════════════════════════════════╣
║  Catalysts: iPhone 17 cycle, Services acceleration       ║
║  Risks: China exposure, elevated P/E                     ║
╚══════════════════════════════════════════════════════════╝
```

### Continuous Monitoring Daemon

```bash
# Run two-tier daemon with default watchlist from config/settings.yaml
ticker-agent watch

# Custom tier configuration
ticker-agent watch --tier1 AAPL NVDA --tier2 MSFT GOOGL AMZN
```

### Python API

```python
from ticker_agent.agents.orchestrator import TickerOrchestrator
from ticker_agent.config import load_config

config = load_config("config/settings.yaml")
orchestrator = TickerOrchestrator(config)

# Single analysis
result = orchestrator.analyze("AAPL")
print(f"Signal: {result.market_context['signal']}")
print(f"Score: {result.market_context['composite_score']:.1f}")
print(f"Narrative: {result.narrative[:200]}...")

# With ABSA sentiment overlay from upstream pipeline
absa_signals = {"supply_chain": "negative", "revenue": "positive"}
result = orchestrator.analyze("AAPL", absa_signals=absa_signals)
```

### Other Commands

```bash
ticker-agent health          # Check Ollama + database connectivity
ticker-agent report --last 5 # List most recent saved reports
ticker-agent --help
```

---

## Project Structure

```
Financial-Economic-Ticker-Analyzer-Agent/
├── cli.py                         # Click CLI entry point
├── pyproject.toml
├── .env.example                   # NEWS_API_KEY and optional pipeline tokens
│
├── config/
│   └── settings.yaml              # Tickers, intervals, LLM, scoring weights
│
└── src/ticker_agent/
    ├── config.py
    │
    ├── data/
    │   ├── models.py              # SQLAlchemy ORM: TickerSnapshot, NewsArticle, AnalysisResult, Alert
    │   ├── database.py            # Engine, session_scope, init_db
    │   ├── stock_fetcher.py       # yfinance wrapper
    │   └── news_fetcher.py        # NewsAPI wrapper
    │
    ├── analysis/
    │   ├── technical.py           # RSI, MACD, Bollinger Bands, SMA/EMA, ATR
    │   ├── fundamental.py         # P/E, ROE, D/E, beta scoring
    │   └── scoring.py             # Composite blender → 0-100 score + signal
    │
    ├── agents/
    │   ├── base_agent.py          # Abstract Ollama agent
    │   ├── news_agent.py          # Sentiment per article + aggregate
    │   ├── analysis_agent.py      # Market intelligence narrative
    │   └── orchestrator.py        # Two-tier pipeline coordinator
    │
    ├── output/
    │   ├── console.py             # Rich terminal renderer
    │   └── reports.py             # JSON / Markdown report writer
    │
    └── scheduler/
        └── runner.py              # Two-tier daemon
```

---

## Configuration

All settings in `config/settings.yaml` with `.env` override support:

| Section | Controls |
|---------|---------|
| `tickers` | Default watchlist |
| `monitoring` | Tier intervals, market hours, timezone |
| `data` | History lookback, NewsAPI article count |
| `analysis.technical` | RSI/MACD/BB periods |
| `analysis.scoring` | Sub-score weights + alert thresholds |
| `llm` | Ollama model, temperature, timeout |
| `output` | Console color, report format, retention |
| `pipeline` | Webhook paths for FinDocAnalyzer + ABSA integration |

---

## Related Repositories

| Repository | Role in Pipeline |
|-----------|-----------------|
| [Fine-Tuned-SEC-Filing-Extraction-Pipeline](https://github.com/A-Kuo/Fine-Tuned-SEC-Filing-Extraction-Pipeline) | Upstream: extracts structured financials from SEC filings, provides ticker symbols |
| [Transformer-Aspect-Based-Sentiment-Analysis](https://github.com/A-Kuo/Transformer-Aspect-Based-Sentiment-Analysis) | Upstream: aspect-level sentiment on filing text, feeds sentiment signals |
| [Agentic-Visualization-Framework](https://github.com/A-Kuo/Agentic-Visualization-Framework) | Downstream: consumes structured analysis output for interactive dashboards |
| [Tax-Data-System-with-S4-Architecture](https://github.com/A-Kuo/Tax-Data-System-with-S4-Architecture) | Temporal: S4 state-space models for long-range financial time series |
| [App-Store-Metrics](https://github.com/A-Kuo/App-Store-Metrics) | Alternative data: mobile market dynamics as complementary signal layer |

---

## Citation

```bibtex
@software{financial_ticker_agent_2026,
  author = {A-Kuo},
  title = {Financial-Economic-Ticker-Analyzer-Agent},
  url = {https://github.com/A-Kuo/Financial-Economic-Ticker-Analyzer-Agent},
  year = {2026}
}
```

---

*The signal matters. The context around the signal matters more. April 2026.*
