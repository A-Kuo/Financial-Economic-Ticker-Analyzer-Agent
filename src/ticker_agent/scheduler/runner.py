"""Scheduled daemon — runs analysis passes on a configurable timetable."""
from __future__ import annotations

import logging
import time
from datetime import datetime

import schedule

from ticker_agent.config import AppConfig
from ticker_agent.data import database as db
from ticker_agent.output.console import console, print_summary_table
from ticker_agent.output.reports import generate_report

logger = logging.getLogger(__name__)


def run_analysis_pass(config: AppConfig, tier: int | None = None) -> None:
    """
    Execute one full analysis pass, persist results, and save a report.
    Called both by the scheduler and directly from the CLI.
    """
    from ticker_agent.agents.orchestrator import Orchestrator  # avoid import cycle

    label = f"Tier {tier}" if tier is not None else "All Tickers"
    console.rule(f"[bold cyan]Analysis run — {label}  ·  {datetime.utcnow().strftime('%H:%M UTC')}[/bold cyan]")

    orch = Orchestrator(config)
    results = orch.analyze_all(tier=tier)

    print_summary_table(results, title=f"Results — {label}")

    # Persist to SQLite
    with db.get_connection(config.db_path) as conn:
        for r in results:
            try:
                if r.quote:
                    db.save_snapshot(conn, r.quote)
                if r.signals:
                    db.save_signals(conn, r.signals)
                for article in r.articles:
                    db.save_news_item(conn, article)
                if r.score and r.quote:
                    tier_num = config.tickers.tier_of(r.symbol)
                    db.save_report(conn, r.score, tier_num, r.quote.price)
                for alert_msg in r.alerts_fired:
                    parts = alert_msg.split(":", 1)
                    alert_type = parts[0].strip() if len(parts) > 1 else "ALERT"
                    db.save_alert(conn, r.symbol, alert_type, alert_msg)
            except Exception as exc:
                logger.error("DB persist error for %s: %s", r.symbol, exc)

    # Save Markdown report
    try:
        path = generate_report(results, output_dir=config.reports_dir)
        console.print(f"[dim]Report → {path}[/dim]")
    except Exception as exc:
        logger.error("Report generation failed: %s", exc)

    # Summary stats
    scored = [r for r in results if r.score]
    if scored:
        buys = sum(1 for r in scored if r.score.signal in ("BUY", "STRONG_BUY"))
        sells = sum(1 for r in scored if r.score.signal in ("SELL", "STRONG_SELL"))
        avg = sum(r.score.composite_score for r in scored) / len(scored)
        total_alerts = sum(len(r.alerts_fired) for r in results)
        console.print(
            f"[dim]Scored {len(scored)} tickers  ·  "
            f"Buys: {buys}  Sells: {sells}  "
            f"Avg score: {avg:.1f}  "
            f"Alerts: {total_alerts}[/dim]"
        )


def run_daemon(config: AppConfig) -> None:
    """
    Start the daemon. Blocks indefinitely, running scheduled analysis passes.

    Schedule:
      - Daily full runs at each time listed in config.schedule.run_times (UTC)
      - Tier 1 re-run every config.schedule.tier1_interval_minutes
    """
    db.init_db(config.db_path)

    console.rule("[bold green]Ticker Agent Daemon Starting[/bold green]")
    console.print(f"  Model:        [cyan]{config.agent.model}[/cyan]")
    console.print(f"  Ollama host:  [cyan]{config.ollama_host}[/cyan]")
    console.print(f"  DB:           [cyan]{config.db_path}[/cyan]")
    console.print(f"  Tier 1:       [cyan]{', '.join(config.tickers.tier1)}[/cyan]")
    console.print(f"  Tier 2:       [cyan]{len(config.tickers.tier2)} tickers[/cyan]")
    console.print()

    # Schedule full-basket daily runs
    for run_time in config.schedule.run_times:
        schedule.every().day.at(run_time).do(run_analysis_pass, config=config, tier=None)
        console.print(f"  Scheduled full run at [yellow]{run_time}[/yellow] UTC daily")

    # Schedule high-frequency Tier 1 runs
    interval = config.schedule.tier1_interval_minutes
    schedule.every(interval).minutes.do(run_analysis_pass, config=config, tier=1)
    console.print(f"  Scheduled Tier 1 run every [yellow]{interval}[/yellow] minutes")

    console.print()
    console.print("[dim]Daemon running — press Ctrl+C to stop[/dim]")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon stopped.[/yellow]")
