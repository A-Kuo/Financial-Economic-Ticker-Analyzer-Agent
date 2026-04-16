# Financial/Economic Ticker Analyzer Agent

A local AI-powered stock monitoring system. Tracks two tiers of equities, computes technical and fundamental scores, fetches real-time news, and generates buy/hold/sell signals via a locally running Ollama LLM.

---

## Features

- **Two-tier coverage** — 10 high-priority blue-chips (Tier 1) + 45-stock S&P-like basket (Tier 2)
- **Technical analysis** — RSI, MACD, Bollinger Bands, SMA 20/50/200, volume spikes, golden/death cross
- **Fundamental scoring** — P/E ratio, 52-week range positioning, beta, dividend yield
- **AI news analysis** — fetches headlines via NewsAPI, summarises with Ollama, derives sentiment score
- **AI reasoning** — Ollama generates prose analysis combining all signals
- **Composite score** — weighted 0–100 score → STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
- **Alerts** — fires on price spikes, RSI extremes, volume spikes, negative sentiment
- **Scheduled daemon** — Tier 1 runs hourly, full basket runs at configurable daily times
- **SQLite storage** — full history of snapshots, indicators, news, reports, and alerts
- **Rich terminal UI** — colour-coded ranked table + detailed per-ticker panels
- **Markdown reports** — auto-saved to `reports/` on every run

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running locally
- NewsAPI key (free at [newsapi.org](https://newsapi.org/register)) — optional but recommended

### 2. Install

```bash
git clone <repo-url>
cd Financial-Economic-Ticker-Analyzer-Agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

### 3. Pull the model

```bash
ollama pull llama3.2
```

> Use `llama3.3` for larger context or `mistral` for faster inference.
> Change the model in `config/settings.yaml` or set `OLLAMA_MODEL=llama3.3` in `.env`.

### 4. Configure

```bash
cp .env.example .env
# Edit .env and add your NEWS_API_KEY
```

### 5. Verify setup

```bash
ticker status
```

---

## Usage

### Analyze specific tickers
```bash
ticker analyze AAPL MSFT NVDA --detail
```

### Analyze Tier 1 (blue-chips) with report
```bash
ticker analyze --tier 1 --save-report
```

### Analyze everything
```bash
ticker analyze --save-report
```

### View stored history for a ticker
```bash
ticker watch AAPL
```

### Show ranked leaderboard (from DB)
```bash
ticker leaderboard
```

### Show active alerts
```bash
ticker alerts
ticker alerts --ack-all    # clear all alerts
```

### Run as a scheduled daemon
```bash
ticker daemon
```

> The daemon runs Tier 1 every hour and full-basket at configured times.
> See `scripts/cron_example.txt` for cron/systemd alternatives.

---

## Configuration

Edit `config/settings.yaml` to customise:

| Key | Description |
|-----|-------------|
| `tickers.tier1` | High-priority tickers (analysed most frequently) |
| `tickers.tier2` | Broader basket |
| `agent.model` | Ollama model name |
| `agent.news_lookback_hours` | How far back to pull news |
| `thresholds.*` | Alert trigger levels |
| `schedule.run_times` | UTC times for daily full-basket runs |
| `schedule.tier1_interval_minutes` | Tier 1 re-run frequency |
| `scoring.weights` | Relative weight of tech/fundamental/sentiment |

---

## Architecture

```
CLI (click)
  └── Orchestrator
        ├── StockFetcher  (yfinance)
        ├── NewsFetcher   (NewsAPI)
        ├── TechnicalAnalysis  (pandas — RSI, MACD, BB, SMA)
        ├── FundamentalScoring (P/E, 52wk, beta, yield)
        ├── NewsAgent     (Ollama — summarise + sentiment)
        ├── AnalysisAgent (Ollama — reasoning prose)
        └── CompositeScoring → signal + confidence
              └── Database (SQLite) + Reports (Markdown)
```

### Scoring pipeline

```
OHLCV history  → TechnicalSignals → technical_score  (0–100)
StockQuote     → FundamentalScore → fundamental_score (0–100)
NewsArticles   → NewsAgent        → sentiment_score   (0–100)

composite = 0.4 × tech + 0.3 × fund + 0.3 × sentiment

score ≥ 75 → STRONG_BUY
score ≥ 60 → BUY
score ≥ 40 → HOLD
score ≥ 25 → SELL
score  < 25 → STRONG_SELL
```

---

## Project Structure

```
├── config/settings.yaml       Tickers, thresholds, schedule
├── src/ticker_agent/
│   ├── cli.py                 Click entry point
│   ├── config.py              AppConfig loader
│   ├── data/
│   │   ├── models.py          Dataclasses (StockQuote, TechnicalSignals, …)
│   │   ├── database.py        SQLite schema + CRUD
│   │   ├── stock_fetcher.py   yfinance wrapper
│   │   └── news_fetcher.py    NewsAPI wrapper
│   ├── analysis/
│   │   ├── technical.py       RSI, MACD, BB, SMA
│   │   ├── fundamental.py     P/E, 52wk, beta, yield scoring
│   │   └── scoring.py         Composite score + signal mapping
│   ├── agents/
│   │   ├── base_agent.py      Ollama chat loop + tool-use support
│   │   ├── news_agent.py      News summarisation + sentiment
│   │   ├── analysis_agent.py  Investment reasoning
│   │   └── orchestrator.py    Full pipeline coordinator
│   ├── output/
│   │   ├── console.py         Rich terminal tables + panels
│   │   └── reports.py         Markdown report generator
│   └── scheduler/
│       └── runner.py          schedule-library daemon
├── data/                      SQLite DB (auto-created, gitignored)
├── logs/                      Log files (gitignored)
├── reports/                   Generated Markdown reports (gitignored)
└── scripts/cron_example.txt   Cron / systemd setup reference
```

---

## Technical Assumptions & Limitations

### Data Ranges
- **RSI:** 0–100 (oversold < 30, overbought > 70)
- **Sentiment score:** -1.0 (bearish) to +1.0 (bullish), mapped to 0–100 for composite score
- **P/E ratio:** Positive values assumed; negative earnings (loss-making) scored as neutral
- **Dividend yield:** Expressed as decimal (e.g., 0.03 = 3%)
- **Beta:** Market beta; values < 0.5 or > 2.0 are extreme outliers

### AI (Ollama) Assumptions
- The selected Ollama model outputs structured text with fixed format (SUMMARY, SENTIMENT, CATALYSTS, OUTLOOK)
- Sentiment values are clamped to [-1, 1]; out-of-range values are logged as warnings
- If Ollama is unavailable, sentiment reverts to keyword-based heuristic (may be less accurate)
- No financial AI training occurs; the system uses general-purpose LLMs (llama3.2, mistral, etc.)

### Analysis Constraints
- **No backtesting framework** — results are based on current/recent data only
- **No portfolio optimization** — each ticker is analyzed independently
- **No transaction costs** — signals don't account for fees, slippage, or taxes
- **Not suitable for algorithmic trading** — designed for human-in-the-loop research
- **Historical data:** 6 months OHLCV for technical analysis; configurable news lookback

### Data Sources
- **Prices & fundamentals:** yfinance (free, no API key, ~15-min delay, no intraday)
- **News:** NewsAPI (free tier = 25 req/day, limited to major outlets)
- **AI reasoning:** Ollama (local, offline-capable)

### Validation & Edge Cases
- Configuration is validated on startup; invalid config will raise an error with clear messages
- Missing data (e.g., no quote fetched) degrades to neutral scores (50.0) with logging
- Database is SQLite; not suitable for concurrent writes (single-user/single-machine only)
- Scheduled daemon assumes system clock is accurate for UTC scheduling

---

## Disclaimer

This tool is for **informational and educational purposes only**. It does not constitute financial advice. Always do your own research before making investment decisions. **Past performance is not indicative of future results.**
