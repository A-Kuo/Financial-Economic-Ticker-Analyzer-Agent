"""Two-tier background daemon runner using the `schedule` library.

Tier 1 tickers are checked every N minutes (default 5) during market hours.
Tier 2 tickers are checked every M minutes (default 30) during market hours.
The daemon checks once per minute whether market hours apply, then fires the
appropriate jobs.
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import schedule

from ticker_agent.agents.orchestrator import Orchestrator
from ticker_agent.config import get, setup_logging
from ticker_agent.output import console as con
from ticker_agent.output import reports

logger = logging.getLogger(__name__)


def _market_open() -> bool:
    """Return True if current time is within configured market hours."""
    cfg = get("monitoring", {})
    tz_name = cfg.get("timezone", "America/New_York")
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz).time()

    open_str = cfg.get("market_open", "09:30")
    close_str = cfg.get("market_close", "16:00")

    def _parse(t: str) -> dtime:
        h, m = t.split(":")
        return dtime(int(h), int(m))

    return _parse(open_str) <= now <= _parse(close_str)


class TierRunner:
    """Wraps the orchestrator and renders/saves output for a tier."""

    def __init__(self, tickers: list[str], tier: int, orchestrator: Orchestrator) -> None:
        self.tickers = tickers
        self.tier = tier
        self.orchestrator = orchestrator

    def run(self) -> None:
        if not _market_open():
            logger.debug("Tier %d run skipped — market is closed", self.tier)
            return

        logger.info("Running tier %d for: %s", self.tier, ", ".join(self.tickers))
        analyses = self.orchestrator.analyse_batch(self.tickers, tier=self.tier)
        con.render_batch_summary(analyses)
        reports.save(analyses)


def run_daemon(
    tier1_tickers: list[str] | None = None,
    tier2_tickers: list[str] | None = None,
    use_llm: bool = True,
) -> None:
    """Start the two-tier monitoring daemon (blocks until SIGINT/SIGTERM)."""
    setup_logging()
    cfg = get("monitoring", {})

    t1_tickers = tier1_tickers or cfg.get("tier1_tickers", [])
    t2_tickers = tier2_tickers or cfg.get("tier2_tickers", [])
    t1_interval = int(cfg.get("tier1_interval_minutes", 5))
    t2_interval = int(cfg.get("tier2_interval_minutes", 30))

    orchestrator = Orchestrator(use_llm=use_llm)
    t1_runner = TierRunner(t1_tickers, tier=1, orchestrator=orchestrator)
    t2_runner = TierRunner(t2_tickers, tier=2, orchestrator=orchestrator)

    schedule.every(t1_interval).minutes.do(t1_runner.run)
    schedule.every(t2_interval).minutes.do(t2_runner.run)

    logger.info(
        "Daemon started — Tier 1 (%s) every %dm | Tier 2 (%s) every %dm",
        ",".join(t1_tickers), t1_interval,
        ",".join(t2_tickers), t2_interval,
    )

    # Run once immediately at startup
    t1_runner.run()
    t2_runner.run()

    _stop = False

    def _handle_signal(signum, frame):
        nonlocal _stop
        logger.info("Received signal %s — shutting down daemon", signum)
        _stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not _stop:
        schedule.run_pending()
        time.sleep(30)

    logger.info("Daemon stopped.")
