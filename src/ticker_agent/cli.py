"""CLI entry point — `ticker` command group powered by Click + Rich."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Root group ─────────────────────────────────────────────────────────────────

@click.group()
@click.option(
    "--config", "config_path", default=None,
    help="Path to a custom settings.yaml file.",
    metavar="PATH",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None, verbose: bool) -> None:
    """Financial/Economic Ticker Analyzer Agent.

    \b
    Examples:
      ticker status
      ticker analyze AAPL MSFT --detail
      ticker analyze --tier 1 --save-report
      ticker watch AAPL
      ticker leaderboard
      ticker daemon
    """
    _setup_logging(verbose)
    ctx.ensure_object(dict)

    from ticker_agent.config import load_config
    from ticker_agent.data.database import init_db

    cfg = load_config(config_path)
    init_db(cfg.db_path)
    ctx.obj["config"] = cfg


# ── analyze ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("symbols", nargs=-1, metavar="[SYMBOL ...]")
@click.option(
    "--tier", type=click.Choice(["1", "2", "all"]), default="all", show_default=True,
    help="Which tier to run (ignored if SYMBOLS are given).",
)
@click.option("--detail", "-d", is_flag=True, help="Show full per-ticker panels.")
@click.option("--save-report", "-r", is_flag=True, help="Save a Markdown report to reports/.")
@click.pass_context
def analyze(
    ctx: click.Context,
    symbols: tuple[str, ...],
    tier: str,
    detail: bool,
    save_report: bool,
) -> None:
    """Run analysis on tickers.

    \b
    Examples:
      ticker analyze                    # all tickers
      ticker analyze --tier 1           # Tier 1 only
      ticker analyze AAPL NVDA --detail # specific tickers with full output
    """
    from ticker_agent.agents.orchestrator import Orchestrator
    from ticker_agent.data import database as db
    from ticker_agent.output.console import print_summary_table, print_detail
    from ticker_agent.output.reports import generate_report

    cfg = ctx.obj["config"]
    orch = Orchestrator(cfg)

    with console.status("[cyan]Fetching data and running agents…[/cyan]"):
        if symbols:
            results = [orch.analyze_ticker(s.upper()) for s in symbols]
        else:
            tier_num = None if tier == "all" else int(tier)
            results = orch.analyze_all(tier=tier_num)

    if detail:
        for r in results:
            print_detail(r)
    else:
        print_summary_table(results)

    # Persist
    with db.get_connection(cfg.db_path) as conn:
        for r in results:
            if r.quote:
                db.save_snapshot(conn, r.quote)
            if r.signals:
                db.save_signals(conn, r.signals)
            for article in r.articles:
                db.save_news_item(conn, article)
            if r.score and r.quote:
                t = cfg.tickers.tier_of(r.symbol)
                db.save_report(conn, r.score, t, r.quote.price)
            for alert_msg in r.alerts_fired:
                parts = alert_msg.split(":", 1)
                alert_type = parts[0].strip() if len(parts) > 1 else "ALERT"
                db.save_alert(conn, r.symbol, alert_type, alert_msg)

    if save_report:
        from ticker_agent.output.reports import generate_report
        path = generate_report(results, output_dir=cfg.reports_dir)
        console.print(f"[green]Report saved:[/green] {path}")


# ── daemon ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def daemon(ctx: click.Context) -> None:
    """Start the scheduled background daemon.

    Runs Tier 1 analysis on a short interval and full-basket analysis at
    configured daily times. Press Ctrl+C to stop.
    """
    from ticker_agent.scheduler.runner import run_daemon
    run_daemon(ctx.obj["config"])


# ── watch ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("symbol")
@click.option("--limit", "-n", default=10, show_default=True, help="Number of past reports to show.")
@click.pass_context
def watch(ctx: click.Context, symbol: str, limit: int) -> None:
    """Show stored analysis history and recent news for a ticker.

    \b
    Example:
      ticker watch AAPL
    """
    from ticker_agent.data import database as db

    cfg = ctx.obj["config"]
    sym = symbol.upper()

    with db.get_connection(cfg.db_path) as conn:
        reports = db.get_recent_reports(conn, sym, limit=limit)
        news = db.get_recent_news(conn, sym, limit=5)

    if not reports:
        console.print(f"[yellow]No stored history for {sym}. Run: ticker analyze {sym}[/yellow]")
        return

    from ticker_agent.output.console import _signal_text, _score_text

    table = Table(
        title=f"{sym} — Analysis History",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Date (UTC)", width=16)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Signal", width=14)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Tech", justify="right", width=5)
    table.add_column("Fund", justify="right", width=5)
    table.add_column("Sent", justify="right", width=5)
    table.add_column("Conf", justify="right", width=5)
    for row in reports:
        table.add_row(
            str(row["generated_at"])[:16],
            f"${row['price_at_analysis']:.2f}",
            _signal_text(row["signal"]),
            _score_text(row["composite_score"]),
            f"{row['technical_score']:.0f}",
            f"{row['fundamental_score']:.0f}",
            f"{row['sentiment_score']:.0f}",
            f"{row['confidence']:.0%}",
        )
    console.print(table)

    if news:
        console.print()
        console.print(f"[bold]Recent News for {sym}[/bold]")
        for n in news:
            sentiment = n["sentiment_score"]
            sent_icon = "+" if (sentiment or 0) > 0.1 else ("-" if (sentiment or 0) < -0.1 else "·")
            console.print(
                f"  [{str(n['published_at'])[:10]}] [{sent_icon}] {n['title'] or '(no title)'}"
            )


# ── leaderboard ────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def leaderboard(ctx: click.Context) -> None:
    """Show the current ranked leaderboard from stored analysis data."""
    from ticker_agent.data import database as db
    from ticker_agent.output.console import print_leaderboard

    cfg = ctx.obj["config"]
    with db.get_connection(cfg.db_path) as conn:
        rows = db.get_all_latest_scores(conn)

    print_leaderboard(rows)


# ── alerts ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--ack-all", is_flag=True, help="Acknowledge (dismiss) all active alerts.")
@click.pass_context
def alerts(ctx: click.Context, ack_all: bool) -> None:
    """Show unacknowledged alerts. Use --ack-all to clear them."""
    from ticker_agent.data import database as db
    from ticker_agent.output.console import print_alerts

    cfg = ctx.obj["config"]
    with db.get_connection(cfg.db_path) as conn:
        active = db.get_unacknowledged_alerts(conn)
        if ack_all and active:
            conn.execute("UPDATE alerts SET acknowledged = 1 WHERE acknowledged = 0")
            console.print(f"[green]Acknowledged {len(active)} alerts.[/green]")
            return

    print_alerts(active)


# ── status ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show system status: config, connectivity, and database stats."""
    from ticker_agent.agents.base_agent import BaseAgent
    from ticker_agent.data import database as db

    cfg = ctx.obj["config"]

    console.print()
    console.rule("[bold]Ticker Agent — System Status[/bold]")
    console.print()

    # Config
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Key", style="dim", min_width=20)
    table.add_column("Value")
    table.add_row("Ollama model", f"[cyan]{cfg.agent.model}[/cyan]")
    table.add_row("Ollama host", cfg.ollama_host)
    table.add_row("Database", cfg.db_path)
    table.add_row("Reports dir", cfg.reports_dir)
    table.add_row("NewsAPI key", "[green]configured[/green]" if cfg.news_api_key else "[yellow]not set — news disabled[/yellow]")
    table.add_row("Tier 1 tickers", f"{', '.join(cfg.tickers.tier1)}")
    table.add_row("Tier 2 tickers", f"{len(cfg.tickers.tier2)} tickers")
    table.add_row("Scoring weights", f"Tech {cfg.scoring.technical:.0%} · Fund {cfg.scoring.fundamental:.0%} · Sent {cfg.scoring.sentiment:.0%}")
    console.print(table)
    console.print()

    # Ollama connectivity check
    console.print("[dim]Checking Ollama connectivity…[/dim]", end=" ")
    agent = BaseAgent(model=cfg.agent.model, host=cfg.ollama_host)
    if agent.check_connectivity():
        console.print(f"[bold green]ONLINE[/bold green] ({cfg.agent.model})")
    else:
        console.print(f"[bold red]OFFLINE[/bold red] — start Ollama and pull the model:")
        console.print(f"  [dim]ollama pull {cfg.agent.model}[/dim]")

    # DB stats
    console.print()
    if Path(cfg.db_path).exists():
        import sqlite3
        with sqlite3.connect(cfg.db_path) as conn:
            def count(table: str) -> int:
                return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            try:
                console.print(
                    f"[dim]DB stats:[/dim] "
                    f"snapshots={count('stock_snapshots')}  "
                    f"reports={count('analysis_reports')}  "
                    f"news={count('news_items')}  "
                    f"alerts={count('alerts')}"
                )
            except Exception:
                pass
    else:
        console.print("[dim]Database not yet created — will be initialised on first run.[/dim]")

    console.print()


if __name__ == "__main__":
    cli()
