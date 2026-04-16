"""Tests for database operations and schema."""
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from ticker_agent.data import database as db
from ticker_agent.data.models import StockQuote, TechnicalSignals, NewsArticle, CompositeScore


class TestDatabaseInit:
    def test_init_creates_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db.init_db(db_path)
            assert Path(db_path).exists()

            # Verify tables exist
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            assert "stock_snapshots" in tables
            assert "technical_indicators" in tables
            assert "news_items" in tables
            assert "analysis_reports" in tables
            assert "alerts" in tables


class TestSnapshotPersistence:
    @pytest.fixture
    def db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            db.init_db(path)
            yield path

    def test_save_snapshot(self, db_path):
        quote = StockQuote(
            symbol="TEST",
            price=100.0,
            open=95.0,
            high=102.0,
            low=94.0,
            volume=1000000,
            pe_ratio=15.0,
            tier=1,
        )
        with db.get_connection(db_path) as conn:
            snapshot_id = db.save_snapshot(conn, quote)
            assert snapshot_id > 0

    def test_get_latest_snapshot(self, db_path):
        quote1 = StockQuote(
            symbol="TEST",
            price=100.0,
            open=95.0,
            high=102.0,
            low=94.0,
            volume=1000000,
        )
        quote2 = StockQuote(
            symbol="TEST",
            price=101.0,
            open=100.0,
            high=103.0,
            low=99.0,
            volume=1100000,
        )
        with db.get_connection(db_path) as conn:
            db.save_snapshot(conn, quote1)
            db.save_snapshot(conn, quote2)
            latest = db.get_latest_snapshot(conn, "TEST")
            assert latest is not None
            assert latest["price"] == 101.0


class TestSignalsPersistence:
    @pytest.fixture
    def db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            db.init_db(path)
            yield path

    def test_save_signals(self, db_path):
        signals = TechnicalSignals(
            symbol="TEST",
            rsi_14=55.0,
            macd=0.5,
            macd_signal=0.4,
            macd_histogram=0.1,
        )
        with db.get_connection(db_path) as conn:
            indicator_id = db.save_signals(conn, signals)
            assert indicator_id > 0


class TestNewsPersistence:
    @pytest.fixture
    def db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            db.init_db(path)
            yield path

    def test_save_news_item(self, db_path):
        article = NewsArticle(
            symbol="TEST",
            title="Test headline",
            source="TestNews",
            url="https://example.com/test",
            published_at=datetime.utcnow(),
            description="Test description",
        )
        with db.get_connection(db_path) as conn:
            db.save_news_item(conn, article)
            # Verify it was saved
            rows = db.get_recent_news(conn, "TEST")
            assert len(rows) > 0
            assert rows[0]["title"] == "Test headline"

    def test_news_deduplication_by_url(self, db_path):
        url = "https://example.com/test"
        article1 = NewsArticle(
            symbol="TEST",
            title="Test headline",
            source="TestNews",
            url=url,
            published_at=datetime.utcnow(),
        )
        article2 = NewsArticle(
            symbol="TEST",
            title="Different title",
            source="TestNews",
            url=url,
            published_at=datetime.utcnow(),
        )
        with db.get_connection(db_path) as conn:
            db.save_news_item(conn, article1)
            db.save_news_item(conn, article2)  # Should be ignored
            rows = db.get_recent_news(conn, "TEST")
            assert len(rows) == 1


class TestReportPersistence:
    @pytest.fixture
    def db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            db.init_db(path)
            yield path

    def test_save_report(self, db_path):
        score = CompositeScore(
            symbol="TEST",
            technical_score=75.0,
            fundamental_score=70.0,
            sentiment_score=65.0,
            composite_score=70.0,
            signal="BUY",
            confidence=0.85,
        )
        with db.get_connection(db_path) as conn:
            report_id = db.save_report(conn, score, tier=1, price=100.0)
            assert report_id > 0

    def test_get_recent_reports(self, db_path):
        score1 = CompositeScore(
            symbol="TEST",
            composite_score=70.0,
            signal="BUY",
        )
        score2 = CompositeScore(
            symbol="TEST",
            composite_score=75.0,
            signal="STRONG_BUY",
        )
        with db.get_connection(db_path) as conn:
            db.save_report(conn, score1, tier=1, price=100.0)
            db.save_report(conn, score2, tier=1, price=101.0)
            reports = db.get_recent_reports(conn, "TEST", limit=10)
            assert len(reports) == 2
