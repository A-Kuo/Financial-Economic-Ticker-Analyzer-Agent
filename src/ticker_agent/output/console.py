"""Rich terminal output — summary tables, detailed ticker panels, and alert displays."""
from __future__ import annotations

from datetime import datetime

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ── Signal styling ─────────────────────────────────────────────────────────────

_SIGNAL_STYLE: dict[str, str] = {
    "STRONG_BUY": "bold bright_green",
    "BUY": "green",
    "HOLD": "yellow",
    "SELL": "red",
    "STRONG_SELL": "bold bright_red",
}

_SIGNAL_ICON: dict[str, str] = {
    "STRONG_BUY": "▲▲",
    "BUY": "▲",
    "HOLD": "■",
    "SELL": "▼",
    "STRONG_SELL": "▼▼",
}


def _signal_text(signal: str) -> Text:
    icon = _SIGNAL_ICON.get(signal, "?")
    style = _SIGNAL_STYLE.get(signal, "white")
    return Text(f"{icon} {signal}", style=style)


def _rsi_text(rsi: float) -> Text:
    if rsi < 30:
        return Text(f"{rsi:.1f}", style="bold bright_green")
    if rsi > 70:
        return Text(f"{rsi:.1f}", style="bold bright_red")
    return Text(f"{rsi:.1f}", style="white")


def _score_text(score: float) -> Text:
    if score >= 70:
        return Text(f"{score:.1f}", style="bold bright_green")
    if score >= 55:
        return Text(f"{score:.1f}", style="green")
    if score >= 45:
        return Text(f"{score:.1f}", style="yellow")
    if score >= 30:
        return Text(f"{score:.1f}", style="red")
    return Text(f"{score:.1f}", style="bold bright_red")


def _sentiment_text(score: float) -> Text:
    label = f"{score:+.2f}"
    if score >= 0.4:
        return Text(label, style="bright_green")
    if score >= 0.1:
        return Text(label, style="green")
    if score <= -0.4:
        return Text(label, style="bright_red")
    if score <= -0.1:
        return Text(label, style="red")
    return Text(label, style="dim white")


# ── Summary table ──────────────────────────────────────────────────────────────

def print_summary_table(results: list, title: str = "Ticker Analysis") -> None:
    """Compact ranked summary table across all analysed tickers."""
    from ticker_agent.agents.orchestrator import AnalysisResult  # avoid circular

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    table = Table(
        title=f"{title}  ·  {ts}",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Ticker", style="bold white", width=7)
    table.add_column("Tier", width=4, justify="center")
    table.add_column("Price", justify="right", width=10)
    table.add_column("RSI", justify="right", width=6)
    table.add_column("MACD Hist", justify="right", width=10)
    table.add_column("Vol×", justify="right", width=6)
    table.add_column("Tech", justify="right", width=5)
    table.add_column("Fund", justify="right", width=5)
    table.add_column("Sent", justify="right", width=7)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Signal", width=14)
    table.add_column("Conf", justify="right", width=5)

    # Sort by composite score descending (errors last)
    sorted_results = sorted(
        results,
        key=lambda r: (r.score.composite_score if r.score else -1),
        reverse=True,
    )

    for rank, r in enumerate(sorted_results, 1):
        if r.error:
            table.add_row(
                str(rank), r.symbol, "—",
                Text("ERROR", style="red"),
                *["—"] * 10,
            )
            continue

        q = r.quote
        s = r.signals
        sc = r.score

        tier_str = f"T{q.tier}" if q and q.tier else "—"
        price_str = f"${q.price:,.2f}" if q else "—"
        rsi_cell = _rsi_text(s.rsi_14) if s and s.rsi_14 is not None else Text("—", style="dim")
        hist_str = (
            Text(f"{s.macd_histogram:+.4f}", style="green" if s.macd_histogram > 0 else "red")
            if s and s.macd_histogram is not None
            else Text("—", style="dim")
        )
        vol_str = (
            Text(f"{s.volume_ratio:.1f}×", style="yellow" if s.volume_ratio > 1.5 else "")
            if s and s.volume_ratio is not None
            else Text("—", style="dim")
        )

        table.add_row(
            str(rank),
            r.symbol,
            tier_str,
            price_str,
            rsi_cell,
            hist_str,
            vol_str,
            Text(f"{sc.technical_score:.0f}") if sc else Text("—"),
            Text(f"{sc.fundamental_score:.0f}") if sc else Text("—"),
            _sentiment_text(r.sentiment_score),
            _score_text(sc.composite_score) if sc else Text("—"),
            _signal_text(sc.signal) if sc else Text("—"),
            Text(f"{sc.confidence:.0%}") if sc else Text("—"),
        )

    console.print(table)

    # Print any fired alerts inline
    all_alerts = [a for r in results for a in getattr(r, "alerts_fired", [])]
    if all_alerts:
        console.print()
        for alert in all_alerts:
            console.print(f"  [bold yellow]⚠  {alert}[/bold yellow]")


# ── Detailed single-ticker panel ───────────────────────────────────────────────

def print_detail(result) -> None:
    """Full detail panel for a single ticker result."""
    q = result.quote
    s = result.signals
    sc = result.score

    # Header
    header_parts: list[str] = [f"[bold cyan]{result.symbol}[/bold cyan]"]
    if q:
        header_parts.append(f"  [bold white]${q.price:,.2f}[/bold white]")
        if q.sector:
            header_parts.append(f"  [dim]{q.sector}[/dim]")
        if q.market_cap:
            header_parts.append(f"  [dim]${q.market_cap / 1e9:.1f}B[/dim]")
    console.print(Panel("".join(header_parts), expand=False, border_style="cyan"))

    if result.error:
        console.print(f"[bold red]Error:[/bold red] {result.error}\n")
        return

    # Split technical + fundamental side by side
    tech_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tech_table.add_column("Metric", style="dim", min_width=18)
    tech_table.add_column("Value", min_width=20)
    if s:
        if s.rsi_14 is not None:
            tech_table.add_row("RSI(14)", _rsi_text(s.rsi_14))
        if s.macd is not None:
            hist_style = "green" if (s.macd_histogram or 0) > 0 else "red"
            tech_table.add_row(
                "MACD / Hist",
                Text(f"{s.macd:.4f} / {s.macd_histogram:+.4f}", style=hist_style),
            )
        if s.sma_20 and s.sma_50 and s.sma_200:
            cross = "GOLDEN" if s.sma_50 > s.sma_200 else "DEATH"
            cross_style = "green" if cross == "GOLDEN" else "red"
            tech_table.add_row(
                "SMA 20/50/200",
                Text(f"${s.sma_20:.2f} / ${s.sma_50:.2f} / ${s.sma_200:.2f}  [{cross}]",
                     style=cross_style),
            )
        if s.bb_upper is not None:
            tech_table.add_row(
                "Bollinger (L/M/U)",
                f"${s.bb_lower:.2f} / ${s.bb_middle:.2f} / ${s.bb_upper:.2f}",
            )
        if s.volume_ratio is not None:
            vr_style = "yellow" if s.volume_ratio > 1.5 else ""
            tech_table.add_row("Volume ratio", Text(f"{s.volume_ratio:.2f}×", style=vr_style))
        if s.price_vs_52wk_high_pct is not None:
            pct_style = "green" if s.price_vs_52wk_high_pct > -5 else ""
            tech_table.add_row(
                "vs 52-wk high",
                Text(f"{s.price_vs_52wk_high_pct:+.1f}%", style=pct_style),
            )

    fund_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    fund_table.add_column("Metric", style="dim", min_width=18)
    fund_table.add_column("Value", min_width=18)
    if q:
        if q.pe_ratio:
            fund_table.add_row("P/E (trailing)", f"{q.pe_ratio:.1f}")
        if q.eps:
            fund_table.add_row("EPS", f"${q.eps:.2f}")
        if q.beta:
            fund_table.add_row("Beta", f"{q.beta:.2f}")
        if q.dividend_yield:
            fund_table.add_row("Dividend yield", f"{q.dividend_yield * 100:.2f}%")
        if q.fifty_two_week_low and q.fifty_two_week_high:
            fund_table.add_row(
                "52-wk range",
                f"${q.fifty_two_week_low:.2f} – ${q.fifty_two_week_high:.2f}",
            )
        if q.industry:
            fund_table.add_row("Industry", q.industry)

    console.print(
        Columns(
            [
                Panel(tech_table, title="Technical", border_style="blue"),
                Panel(fund_table, title="Fundamentals", border_style="magenta"),
            ],
            equal=True,
            expand=True,
        )
    )

    # News
    if result.news_summary:
        sent_text = _sentiment_text(result.sentiment_score)
        console.print(
            Panel(
                f"[bold]Sentiment:[/bold] {sent_text}  "
                f"[dim]({len(result.articles)} articles)[/dim]\n\n{result.news_summary}",
                title="News Analysis",
                border_style="yellow",
            )
        )

    # AI reasoning
    if result.reasoning:
        console.print(
            Panel(result.reasoning, title="AI Analysis", border_style="cyan")
        )

    # Score verdict
    if sc:
        signal_style = _SIGNAL_STYLE.get(sc.signal, "white")
        score_bar = _build_score_bar(sc.composite_score)
        console.print(
            Panel(
                f"{score_bar}\n\n"
                f"[bold]Signal:[/bold]  [{signal_style}]{_SIGNAL_ICON.get(sc.signal, '')} {sc.signal}[/{signal_style}]\n"
                f"[bold]Score:[/bold]   {sc.composite_score:.1f} / 100  "
                f"[dim](Tech {sc.technical_score:.0f} · Fund {sc.fundamental_score:.0f} · Sent {sc.sentiment_score:.0f})[/dim]\n"
                f"[bold]Confidence:[/bold] {sc.confidence:.0%}",
                title="Verdict",
                border_style=signal_style,
            )
        )

    # Alerts
    if result.alerts_fired:
        for alert in result.alerts_fired:
            console.print(f"  [bold yellow]⚠  {alert}[/bold yellow]")

    console.print()


def _build_score_bar(score: float, width: int = 40) -> str:
    """ASCII progress bar for the composite score."""
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "bright_green" if score >= 60 else ("yellow" if score >= 40 else "red")
    return f"[{color}]{bar}[/{color}]  [{color}]{score:.1f}[/{color}]"


# ── Alerts ─────────────────────────────────────────────────────────────────────

def print_alerts(alerts: list) -> None:
    if not alerts:
        console.print("[dim]No active alerts.[/dim]")
        return
    table = Table(title="Active Alerts", box=box.ROUNDED, header_style="bold red")
    table.add_column("Time", width=16)
    table.add_column("Symbol", width=8)
    table.add_column("Type", width=20)
    table.add_column("Message")
    for a in alerts:
        table.add_row(
            str(a["triggered_at"])[:16],
            a["symbol"],
            a["alert_type"],
            a["message"],
        )
    console.print(table)


# ── Leaderboard ────────────────────────────────────────────────────────────────

def print_leaderboard(rows: list, title: str = "All-Time Leaderboard") -> None:
    """Print stored scores ranked by composite score."""
    if not rows:
        console.print("[dim]No stored analysis data yet. Run: ticker analyze[/dim]")
        return
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Symbol", width=8)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Signal", width=14)
    table.add_column("Confidence", justify="right", width=10)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Last Updated", width=16)
    for rank, row in enumerate(rows, 1):
        table.add_row(
            str(rank),
            row["symbol"],
            _score_text(row["composite_score"]),
            _signal_text(row["signal"]),
            f"{row['confidence']:.0%}",
            f"${row['price_at_analysis']:.2f}",
            str(row["generated_at"])[:16],
        )
    console.print(table)
