"""Rich-powered console renderer for ticker analysis results."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

if TYPE_CHECKING:
    from ticker_agent.agents.orchestrator import TickerAnalysis

console = Console()

_SIGNAL_STYLES = {
    "STRONG_BUY":  "bold green",
    "BUY":         "green",
    "HOLD":        "yellow",
    "SELL":        "red",
    "STRONG_SELL": "bold red",
}

_SENTIMENT_STYLES = {
    "bullish": "green",
    "neutral": "yellow",
    "bearish": "red",
}


def _signal_badge(signal: str) -> Text:
    style = _SIGNAL_STYLES.get(signal, "white")
    return Text(f" {signal} ", style=f"reverse {style}")


def render_analysis(analysis: "TickerAnalysis") -> None:
    """Render a full TickerAnalysis to the terminal."""
    snap = analysis.snapshot
    rep = analysis.report
    news = analysis.news_result

    if not analysis.success:
        console.print(f"[red]✗ {analysis.ticker}: {analysis.error}[/red]")
        return

    # ── Header panel ────────────────────────────────────────────────────────
    price_str = f"${snap.price:.2f}" if snap and snap.price else "N/A"
    chg_str = ""
    if snap and snap.change_pct is not None:
        chg_color = "green" if snap.change_pct >= 0 else "red"
        chg_str = f"  [{chg_color}]{snap.change_pct:+.2f}%[/{chg_color}]"

    badge = _signal_badge(rep.signal) if rep else Text("N/A")
    title = Text()
    title.append(f"  {analysis.ticker}  ", style="bold white")
    title.append(f"{price_str}", style="bold cyan")
    title.append(chg_str)
    title.append("   ")
    title.append_text(badge)
    title.append(f"  Score: {rep.composite_score:.0f}/100  " if rep else "")
    title.append(f"Confidence: {rep.confidence}" if rep else "")

    console.print(Panel(title, box=box.ROUNDED, border_style="bright_blue"))

    # ── Score table ──────────────────────────────────────────────────────────
    if rep:
        score_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold blue")
        score_table.add_column("Technical", justify="center")
        score_table.add_column("Fundamental", justify="center")
        score_table.add_column("Sentiment", justify="center")
        score_table.add_column("Composite", justify="center", style="bold")

        def _score_style(s: float) -> str:
            if s >= 70:
                return "green"
            if s >= 40:
                return "yellow"
            return "red"

        score_table.add_row(
            Text(f"{rep.composite_score:.0f}", style=_score_style(rep.technical_score))
            if False else f"[{_score_style(rep.composite_score)}]{rep.technical_score:.0f}[/]",
            f"[{_score_style(rep.fundamental_score)}]{rep.fundamental_score:.0f}[/]",
            f"[{_score_style(rep.sentiment_score)}]{rep.sentiment_score:.0f}[/]",
            f"[bold {_score_style(rep.composite_score)}]{rep.composite_score:.0f}[/bold {_score_style(rep.composite_score)}]",
        )
        console.print(score_table)

    # ── Fundamentals ─────────────────────────────────────────────────────────
    if snap:
        fund_table = Table(box=box.SIMPLE, show_header=False)
        fund_table.add_column("Metric", style="dim")
        fund_table.add_column("Value")
        rows = [
            ("Market Cap", f"${snap.market_cap/1e9:.1f}B" if snap.market_cap else "N/A"),
            ("P/E (TTM)", f"{snap.pe_ratio:.1f}" if snap.pe_ratio else "N/A"),
            ("Forward P/E", f"{snap.forward_pe:.1f}" if snap.forward_pe else "N/A"),
            ("EPS", f"${snap.eps:.2f}" if snap.eps else "N/A"),
            ("52W High", f"${snap.week_52_high:.2f}" if snap.week_52_high else "N/A"),
            ("52W Low", f"${snap.week_52_low:.2f}" if snap.week_52_low else "N/A"),
            ("Beta", f"{snap.beta:.2f}" if snap.beta else "N/A"),
            ("Div Yield", f"{snap.dividend_yield*100:.2f}%" if snap.dividend_yield else "N/A"),
        ]
        for label, val in rows:
            fund_table.add_row(label, val)
        console.print(Panel(fund_table, title="[bold]Fundamentals[/bold]", border_style="blue"))

    # ── News sentiment ────────────────────────────────────────────────────────
    if news:
        sent_color = _SENTIMENT_STYLES.get(news.aggregate_label, "white")
        sent_panel = Text()
        sent_panel.append(f"Sentiment: ", style="dim")
        sent_panel.append(f"{news.aggregate_label.upper()}  ", style=f"bold {sent_color}")
        sent_panel.append(f"(score: {news.aggregate_score:+.2f})\n\n", style="dim")
        sent_panel.append(news.summary or "")
        console.print(Panel(sent_panel, title="[bold]News Sentiment[/bold]", border_style="blue"))

    # ── LLM Narrative ─────────────────────────────────────────────────────────
    if rep and rep.narrative:
        console.print(Panel(rep.narrative, title="[bold]Market Intelligence[/bold]", border_style="bright_blue"))

    # ── Catalysts & Risks ─────────────────────────────────────────────────────
    if rep and (rep.key_catalysts or rep.key_risks):
        cr_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        cr_table.add_column("Catalysts", style="green")
        cr_table.add_column("Risks", style="red")
        max_rows = max(len(rep.key_catalysts), len(rep.key_risks))
        for i in range(max_rows):
            cat = rep.key_catalysts[i] if i < len(rep.key_catalysts) else ""
            risk = rep.key_risks[i] if i < len(rep.key_risks) else ""
            cr_table.add_row(f"• {cat}" if cat else "", f"• {risk}" if risk else "")
        console.print(cr_table)

    if rep and rep.price_target_comment:
        console.print(f"[dim italic]{rep.price_target_comment}[/dim italic]\n")


def render_batch_summary(analyses: "list[TickerAnalysis]") -> None:
    """Render a compact summary table for a batch of tickers."""
    table = Table(
        title=f"Market Summary — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Score", justify="center")
    table.add_column("Signal")
    table.add_column("Sentiment")
    table.add_column("Confidence")

    for a in analyses:
        if not a.success:
            table.add_row(a.ticker, "—", "—", "—", f"[red]ERROR: {a.error[:30]}[/red]", "—", "—")
            continue
        snap = a.snapshot
        rep = a.report
        news = a.news_result

        price = f"${snap.price:.2f}" if snap and snap.price else "N/A"
        chg = f"{snap.change_pct:+.2f}%" if snap and snap.change_pct else "N/A"
        chg_style = "green" if snap and snap.change_pct and snap.change_pct >= 0 else "red"
        score = f"{rep.composite_score:.0f}" if rep else "N/A"
        sig_style = _SIGNAL_STYLES.get(rep.signal, "white") if rep else "white"
        signal = f"[{sig_style}]{rep.signal}[/]" if rep else "N/A"
        sent_label = news.aggregate_label if news else "N/A"
        sent_style = _SENTIMENT_STYLES.get(sent_label, "white")
        confidence = rep.confidence if rep else "N/A"

        table.add_row(
            a.ticker,
            price,
            f"[{chg_style}]{chg}[/]",
            score,
            signal,
            f"[{sent_style}]{sent_label}[/]",
            confidence,
        )

    console.print(table)
