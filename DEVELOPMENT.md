# Development Guide

## Setup for Contributors

```bash
git clone https://github.com/A-Kuo/Financial-Economic-Ticker-Analyzer-Agent
cd Financial-Economic-Ticker-Analyzer-Agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ollama pull llama3.2
cp .env.example .env
```

## Running Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=src/ticker_agent --cov-report=html

# Run specific test file
pytest tests/test_scoring.py -v

# Run with verbose output
pytest -vv
```

## Code Quality Checks

```bash
# Type checking
mypy src/ticker_agent --ignore-missing-imports

# Linting
ruff check src/ticker_agent tests
ruff check --fix src/ticker_agent  # Auto-fix

# All checks
mypy src/ticker_agent --ignore-missing-imports && ruff check src/ticker_agent
```

## Project Architecture

```
ticker_agent/
├── data/          — Data fetching and persistence
│   ├── models.py       — Dataclasses (StockQuote, TechnicalSignals, etc.)
│   ├── database.py     — SQLite schema and CRUD operations
│   ├── stock_fetcher.py  — yfinance wrapper with retry logic
│   └── news_fetcher.py   — NewsAPI wrapper
│
├── analysis/      — Pure computation layer (no I/O)
│   ├── technical.py    — RSI, MACD, Bollinger Bands, SMA
│   ├── fundamental.py  — P/E, 52-week, beta, dividend scoring
│   └── scoring.py      — Composite score + signal mapping
│
├── agents/        — AI-powered analysis via Ollama
│   ├── base_agent.py   — Ollama client wrapper
│   ├── news_agent.py   — News summarisation + sentiment
│   ├── analysis_agent.py — Investment reasoning
│   └── orchestrator.py  — Full pipeline coordinator
│
├── output/        — Results rendering
│   ├── console.py      — Rich terminal tables
│   └── reports.py      — Markdown report generation
│
├── cli.py         — Click command-line interface
├── config.py      — Configuration loading + validation
└── scheduler/runner.py — Scheduled daemon using schedule library
```

## Key Design Patterns

### Data Flow
```
StockFetcher ──→ TechnicalSignals
    ↓
StockQuote ──→ FundamentalScore ──→ CompositeScore ──→ Signal
    ↓
NewsFetcher ──→ NewsAgent ──→ Sentiment ──┘
```

### Error Handling
- **Graceful degradation:** Missing Ollama → fallback heuristics
- **Validation:** Config is validated on load; bad settings fail fast
- **Logging:** Warnings for edge cases (clamped values, missing data), errors for critical failures
- **No silent failures:** All edge cases are logged

### Type Safety
- Python 3.11+ with type hints on public APIs
- `mypy` configured for strict checking of well-typed modules
- Dataclasses for all data models (strong typing, immutability defaults)

## Adding a New Analysis Feature

### Example: Add a momentum indicator

1. **Add to TechnicalSignals** (`data/models.py`):
   ```python
   @dataclass
   class TechnicalSignals:
       # ...existing fields...
       momentum_score: float | None = None
   ```

2. **Compute in technical.py** (`analysis/technical.py`):
   ```python
   def compute_momentum(closes: pd.Series, period: int = 14) -> float | None:
       """Momentum = current close - close N periods ago."""
       if len(closes) < period + 1:
           return None
       return float(closes.iloc[-1] - closes.iloc[-(period+1)])
   ```

3. **Update compute_signals**:
   ```python
   def compute_signals(symbol: str, df: pd.DataFrame, ...) -> TechnicalSignals:
       # ...existing code...
       return TechnicalSignals(
           # ...existing fields...
           momentum_score=compute_momentum(closes),
       )
   ```

4. **Add to technical score** (`analysis/scoring.py`):
   ```python
   def score_technical(signals: TechnicalSignals) -> float:
       # ...existing votes...
       if signals.momentum_score is not None:
           if signals.momentum_score > 0:
               votes.append(65.0)  # Positive momentum is bullish
           else:
               votes.append(35.0)  # Negative momentum is bearish
       # ...
   ```

5. **Test it** (`tests/test_technical.py`):
   ```python
   def test_momentum_positive(self):
       df = pd.DataFrame({"Close": list(range(100, 120))})
       signals = compute_signals("TEST", df)
       assert signals.momentum_score > 0
   ```

## Adding a New Command

### Example: Add `ticker backtest` command

1. Add to CLI (`cli.py`):
   ```python
   @cli.command()
   @click.argument("symbol")
   @click.option("--start-date", "-s", required=True, help="YYYY-MM-DD")
   @click.option("--end-date", "-e", required=True, help="YYYY-MM-DD")
   @click.pass_context
   def backtest(ctx: click.Context, symbol: str, start_date: str, end_date: str) -> None:
       """Run historical backtest on a symbol."""
       from ticker_agent.backtest import run_backtest
       results = run_backtest(symbol, start_date, end_date)
       console.print(results)
   ```

2. Create the backtest module (`src/ticker_agent/backtest.py`)
3. Add tests (`tests/test_backtest.py`)
4. Update README with usage example

## Debugging Tips

### Enable verbose logging
```bash
ticker --verbose analyze AAPL
```

### Check config loaded correctly
```bash
ticker status
```

### Inspect database
```bash
sqlite3 data/ticker_agent.db "SELECT * FROM analysis_reports LIMIT 5;"
```

### Test a single ticker interactively
```python
from ticker_agent.config import load_config
from ticker_agent.agents.orchestrator import Orchestrator

cfg = load_config()
orch = Orchestrator(cfg)
result = orch.analyze_ticker("AAPL")
print(result.score)
```

## Common Pitfalls

1. **Sentiment out of bounds:** The NewsAgent's LLM might output 0.2 instead of 0.02. Always validate bounds.
2. **Null quote:** `fetch_quote()` returns None on network error. Always check before using `.price`, `.pe_ratio`, etc.
3. **Insufficient history:** Technical indicators need minimum periods (RSI needs 14+ data points). Check for None returns.
4. **SQLite concurrency:** The database isn't designed for concurrent writes. Don't run multiple daemons on the same DB.
5. **Time zones:** All timestamps are UTC. Don't mix naive and aware datetimes.

## Performance Notes

- **Stock fetching:** ~1–2 seconds per ticker (yfinance + HTTP latency)
- **News fetching:** ~0.5–1 second per ticker (NewsAPI)
- **Ollama inference:** ~5–15 seconds per ticker (depends on model and hardware)
- **Full run (55 tickers):** ~5–15 minutes for local Ollama, longer for remote
- **Daemon:** Tier 1 runs hourly (~2 min), full runs daily (~15 min)

## CI/CD

GitHub Actions runs:
1. **Test suite** (pytest with coverage) on every push
2. **Type checking** (mypy) on every push
3. **Linting** (ruff) on every push
4. **CodeQL security scan** weekly

All must pass for merge to main.

## Release Process

1. Update version in `pyproject.toml` and `src/ticker_agent/__init__.py`
2. Update `CHANGELOG.md` (if it exists)
3. Tag the commit: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions auto-creates a release
6. Create a PyPI package (future: add build workflow)

## Contact & Contributing

Open issues on GitHub for bugs or feature requests. PRs welcome — ensure tests pass and type checks succeed before submitting.
