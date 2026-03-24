"""Command-line interface for the ticker agent.

Usage examples:
  ticker-agent analyse AAPL MSFT TSLA
  ticker-agent analyse AAPL --tier 1 --no-llm
  ticker-agent watch --tier1 AAPL NVDA --tier2 MSFT GOOGL
  ticker-agent report --last 5
"""

from __future__ import annotations

import sys

import click
from rich.console import Console

from ticker_agent.config import setup_logging

console = Console()


@click.group()
@click.version_option(package_name="ticker-agent")
def main() -> None:
    """Ticker Agent — agentic market intelligence for real-time ticker analysis."""
    setup_logging()


@main.command()
@click.argument("tickers", nargs=-1, required=True)
@click.option("--tier", type=click.Choice(["1", "2"]), default="2",
              help="1=fast/no-LLM-narrative, 2=full LLM report (default: 2)")
@click.option("--no-llm", is_flag=True, default=False,
              help="Disable Ollama calls (scores only, no narrative)")
@click.option("--save/--no-save", default=True,
              help="Save report to reports/ directory (default: save)")
@click.option("--format", "fmt", type=click.Choice(["json", "markdown"]), default="json")
def analyse(tickers: tuple[str, ...], tier: str, no_llm: bool, save: bool, fmt: str) -> None:
    """Analyse one or more tickers and display a market intelligence report."""
    from ticker_agent.agents.orchestrator import Orchestrator
    from ticker_agent.output import console as con
    from ticker_agent.output import reports

    orchestrator = Orchestrator(use_llm=not no_llm)
    ticker_list = [t.upper() for t in tickers]

    console.print(f"\n[bold blue]Analysing {', '.join(ticker_list)}…[/bold blue]\n")

    if len(ticker_list) == 1:
        result = orchestrator.analyse_ticker(ticker_list[0], tier=int(tier))
        con.render_analysis(result)
        results = [result]
    else:
        results = orchestrator.analyse_batch(ticker_list, tier=int(tier))
        con.render_batch_summary(results)

    if save:
        if fmt == "markdown":
            path = reports.save_markdown(results)
        else:
            path = reports.save_json(results)
        console.print(f"\n[dim]Report saved → {path}[/dim]")


@main.command()
@click.option("--tier1", multiple=True, metavar="TICKER",
              help="Tier-1 (high-frequency) tickers. Repeatable: --tier1 AAPL --tier1 TSLA")
@click.option("--tier2", multiple=True, metavar="TICKER",
              help="Tier-2 (standard) tickers.")
@click.option("--no-llm", is_flag=True, default=False,
              help="Disable Ollama (fast mode)")
def watch(tier1: tuple[str, ...], tier2: tuple[str, ...], no_llm: bool) -> None:
    """Start the two-tier monitoring daemon (blocks until Ctrl-C)."""
    from ticker_agent.scheduler.runner import run_daemon

    t1 = [t.upper() for t in tier1] or None
    t2 = [t.upper() for t in tier2] or None
    console.print("[bold green]Starting daemon…[/bold green]  Press Ctrl-C to stop.\n")
    run_daemon(tier1_tickers=t1, tier2_tickers=t2, use_llm=not no_llm)


@main.command()
@click.option("--last", default=5, show_default=True,
              help="Number of most recent reports to list")
def report(last: int) -> None:
    """List the most recent saved reports."""
    import os
    from pathlib import Path
    from rich.table import Table

    reports_dir = Path("reports")
    if not reports_dir.exists():
        console.print("[yellow]No reports directory found.[/yellow]")
        return

    files = sorted(reports_dir.glob("report_*.*"), key=os.path.getmtime, reverse=True)[:last]
    if not files:
        console.print("[yellow]No reports found.[/yellow]")
        return

    table = Table(title="Recent Reports")
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Modified")

    for f in files:
        stat = f.stat()
        table.add_row(
            f.name,
            f"{stat.st_size / 1024:.1f} KB",
            str(f.stat().st_mtime),
        )
    console.print(table)


@main.command()
def health() -> None:
    """Check connectivity to Ollama and the database."""
    from ticker_agent.data.database import health_check
    import ollama
    from ticker_agent.config import get

    db_ok = health_check()
    console.print(f"Database: {'[green]OK[/green]' if db_ok else '[red]FAIL[/red]'}")

    try:
        client = ollama.Client(host=get("llm.base_url", "http://localhost:11434"))
        models = client.list()
        model_names = [m["name"] for m in models.get("models", [])]
        console.print(f"Ollama: [green]OK[/green]  ({len(model_names)} models: {', '.join(model_names[:5])})")
    except Exception as exc:
        console.print(f"Ollama: [red]FAIL[/red]  ({exc})")
        sys.exit(1)


if __name__ == "__main__":
    main()
