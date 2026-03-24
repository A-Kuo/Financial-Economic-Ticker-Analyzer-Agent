"""Database session management and helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ticker_agent.config import get
from ticker_agent.data.models import Base

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal: sessionmaker | None = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = get("database.url", "sqlite:///data/ticker_agent.db")
        echo = get("database.echo", False)
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        _engine = create_engine(db_url, echo=echo, connect_args=connect_args)
        logger.info("Database engine created: %s", db_url)
    return _engine


def init_db() -> None:
    """Create all tables (idempotent — safe to call on every startup)."""
    engine = _get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables initialised")


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional session scope with automatic rollback on error."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def health_check() -> bool:
    """Return True if the database is reachable."""
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
