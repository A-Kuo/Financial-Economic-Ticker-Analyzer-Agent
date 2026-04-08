"""SQLite database: schema creation, connection management, and CRUD helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT    NOT NULL,
    timestamp        TEXT    NOT NULL,
    price            REAL,
    open             REAL,
    high             REAL,
    low              REAL,
    volume           INTEGER,
    market_cap       REAL,
    pe_ratio         REAL,
    eps              REAL,
    fifty_two_week_high REAL,
    fifty_two_week_low  REAL,
    beta             REAL,
    dividend_yield   REAL,
    sector           TEXT,
    tier             INTEGER,
    created_at       TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS technical_indicators (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                 TEXT    NOT NULL,
    timestamp              TEXT    NOT NULL,
    rsi_14                 REAL,
    macd                   REAL,
    macd_signal            REAL,
    macd_histogram         REAL,
    bb_upper               REAL,
    bb_middle              REAL,
    bb_lower               REAL,
    sma_20                 REAL,
    sma_50                 REAL,
    sma_200                REAL,
    volume_ratio           REAL,
    price_vs_52wk_high_pct REAL,
    created_at             TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS news_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol         TEXT    NOT NULL,
    title          TEXT,
    source         TEXT,
    url            TEXT    UNIQUE,
    published_at   TEXT,
    description    TEXT,
    ai_summary     TEXT,
    sentiment_score REAL,
    fetched_at     TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol            TEXT    NOT NULL,
    generated_at      TEXT    NOT NULL,
    tier              INTEGER,
    technical_score   REAL,
    fundamental_score REAL,
    sentiment_score   REAL,
    composite_score   REAL,
    signal            TEXT,
    confidence        REAL,
    reasoning         TEXT,
    price_at_analysis REAL,
    created_at        TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT    NOT NULL,
    triggered_at TEXT    NOT NULL,
    alert_type   TEXT,
    message      TEXT,
    acknowledged INTEGER DEFAULT 0,
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_sym_ts   ON stock_snapshots(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_indicators_sym_ts  ON technical_indicators(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_news_symbol        ON news_items(symbol);
CREATE INDEX IF NOT EXISTS idx_reports_sym_ts     ON analysis_reports(symbol, generated_at);
CREATE INDEX IF NOT EXISTS idx_alerts_ack         ON alerts(acknowledged);
"""


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def init_db(db_path: str) -> None:
    """Create the database file and run the schema (idempotent)."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


@contextmanager
def get_connection(db_path: str):
    """Yield a sqlite3 connection with row_factory set, auto-commit on success."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Write helpers ──────────────────────────────────────────────────────────────

def save_snapshot(conn: sqlite3.Connection, q) -> int:
    cur = conn.execute(
        """INSERT INTO stock_snapshots
           (symbol, timestamp, price, open, high, low, volume, market_cap,
            pe_ratio, eps, fifty_two_week_high, fifty_two_week_low,
            beta, dividend_yield, sector, tier)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            q.symbol, q.timestamp.isoformat(), q.price, q.open, q.high,
            q.low, q.volume, q.market_cap, q.pe_ratio, q.eps,
            q.fifty_two_week_high, q.fifty_two_week_low,
            q.beta, q.dividend_yield, q.sector, q.tier,
        ),
    )
    return cur.lastrowid


def save_signals(conn: sqlite3.Connection, s) -> int:
    cur = conn.execute(
        """INSERT INTO technical_indicators
           (symbol, timestamp, rsi_14, macd, macd_signal, macd_histogram,
            bb_upper, bb_middle, bb_lower, sma_20, sma_50, sma_200,
            volume_ratio, price_vs_52wk_high_pct)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            s.symbol, s.timestamp.isoformat(), s.rsi_14, s.macd,
            s.macd_signal, s.macd_histogram, s.bb_upper, s.bb_middle,
            s.bb_lower, s.sma_20, s.sma_50, s.sma_200,
            s.volume_ratio, s.price_vs_52wk_high_pct,
        ),
    )
    return cur.lastrowid


def save_news_item(conn: sqlite3.Connection, article) -> None:
    """Insert a news article, silently ignoring URL duplicates."""
    conn.execute(
        """INSERT OR IGNORE INTO news_items
           (symbol, title, source, url, published_at, description,
            ai_summary, sentiment_score)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            article.symbol, article.title, article.source, article.url,
            article.published_at.isoformat(), article.description,
            article.ai_summary, article.sentiment_score,
        ),
    )


def save_report(conn: sqlite3.Connection, score, tier: int, price: float) -> int:
    cur = conn.execute(
        """INSERT INTO analysis_reports
           (symbol, generated_at, tier, technical_score, fundamental_score,
            sentiment_score, composite_score, signal, confidence,
            reasoning, price_at_analysis)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            score.symbol, score.generated_at.isoformat(), tier,
            score.technical_score, score.fundamental_score,
            score.sentiment_score, score.composite_score,
            score.signal, score.confidence, score.reasoning, price,
        ),
    )
    return cur.lastrowid


def save_alert(
    conn: sqlite3.Connection, symbol: str, alert_type: str, message: str
) -> None:
    conn.execute(
        """INSERT INTO alerts (symbol, triggered_at, alert_type, message)
           VALUES (?,?,?,?)""",
        (symbol, datetime.utcnow().isoformat(), alert_type, message),
    )


# ── Read helpers ───────────────────────────────────────────────────────────────

def get_recent_reports(
    conn: sqlite3.Connection, symbol: str, limit: int = 10
) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM analysis_reports
           WHERE symbol = ?
           ORDER BY generated_at DESC LIMIT ?""",
        (symbol, limit),
    ).fetchall()


def get_latest_snapshot(
    conn: sqlite3.Connection, symbol: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM stock_snapshots
           WHERE symbol = ?
           ORDER BY timestamp DESC LIMIT 1""",
        (symbol,),
    ).fetchone()


def get_recent_news(
    conn: sqlite3.Connection, symbol: str, limit: int = 10
) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM news_items
           WHERE symbol = ?
           ORDER BY published_at DESC LIMIT ?""",
        (symbol, limit),
    ).fetchall()


def get_unacknowledged_alerts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM alerts
           WHERE acknowledged = 0
           ORDER BY triggered_at DESC""",
    ).fetchall()


def get_all_latest_scores(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return the most recent analysis report for every symbol."""
    return conn.execute(
        """SELECT r.*
           FROM analysis_reports r
           INNER JOIN (
               SELECT symbol, MAX(generated_at) AS max_ts
               FROM analysis_reports
               GROUP BY symbol
           ) latest ON r.symbol = latest.symbol AND r.generated_at = latest.max_ts
           ORDER BY r.composite_score DESC""",
    ).fetchall()
