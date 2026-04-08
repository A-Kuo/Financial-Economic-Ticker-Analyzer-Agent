"""Markdown report generator — saves analysis results to the reports/ directory."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def generate_report(results: list, output_dir: str = "reports") -> str:
    """
    Write a Markdown report for the given results list.
    Returns the absolute path of the saved file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow()
    filename = f"analysis_{ts.strftime('%Y%m%d_%H%M%S')}.md"
    path = os.path.join(output_dir, filename)

    lines: list[str] = []
    _header(lines, ts)
    _summary_table(lines, results)
    _divider(lines)
    _detailed_sections(lines, results)
    _footer(lines)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


# ── Section builders ───────────────────────────────────────────────────────────

def _header(lines: list[str], ts: datetime) -> None:
    lines += [
        "# Financial Ticker Analysis Report",
        f"*Generated: {ts.strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
    ]


def _summary_table(lines: list[str], results: list) -> None:
    lines.append("## Summary Rankings")
    lines.append("")
    lines.append("| # | Ticker | Price | Signal | Score | Tech | Fund | Sent | Confidence |")
    lines.append("|---|--------|-------|--------|-------|------|------|------|------------|")

    sorted_results = sorted(
        results,
        key=lambda r: (r.score.composite_score if r.score else -1),
        reverse=True,
    )

    for rank, r in enumerate(sorted_results, 1):
        if r.error:
            lines.append(f"| {rank} | **{r.symbol}** | ERROR | — | — | — | — | — | — |")
            continue
        q = r.quote
        sc = r.score
        lines.append(
            f"| {rank} | **{r.symbol}** | ${q.price:,.2f} | **{sc.signal}** "
            f"| {sc.composite_score:.1f} "
            f"| {sc.technical_score:.0f} "
            f"| {sc.fundamental_score:.0f} "
            f"| {sc.sentiment_score:.0f} "
            f"| {sc.confidence:.0%} |"
        )
    lines.append("")


def _detailed_sections(lines: list[str], results: list) -> None:
    lines.append("## Detailed Analysis")
    lines.append("")

    sorted_results = sorted(
        results,
        key=lambda r: (r.score.composite_score if r.score else -1),
        reverse=True,
    )

    for r in sorted_results:
        q = r.quote
        sc = r.score
        s = r.signals

        lines.append(f"### {r.symbol}")
        if r.error:
            lines.append(f"> **Error:** {r.error}")
            lines.append("")
            continue

        # Metadata line
        meta_parts = [f"**Price:** ${q.price:,.2f}"]
        if q.sector:
            meta_parts.append(f"**Sector:** {q.sector}")
        if q.market_cap:
            meta_parts.append(f"**Mkt Cap:** ${q.market_cap / 1e9:.1f}B")
        if q.tier:
            meta_parts.append(f"**Tier:** {q.tier}")
        lines.append("  |  ".join(meta_parts))
        lines.append("")

        # Verdict
        if sc:
            lines.append(
                f"> **{sc.signal}**  ·  Score: **{sc.composite_score:.1f}/100**  "
                f"·  Confidence: {sc.confidence:.0%}"
            )
            lines.append("")

        # Technical indicators
        if s:
            lines.append("**Technical Indicators**")
            lines.append("")
            lines.append("| Indicator | Value | Note |")
            lines.append("|-----------|-------|------|")
            if s.rsi_14 is not None:
                note = "Oversold ▲" if s.rsi_14 < 30 else ("Overbought ▼" if s.rsi_14 > 70 else "Neutral")
                lines.append(f"| RSI(14) | {s.rsi_14:.1f} | {note} |")
            if s.macd is not None:
                note = "Bullish momentum" if (s.macd_histogram or 0) > 0 else "Bearish momentum"
                lines.append(
                    f"| MACD / Hist | {s.macd:.4f} / {s.macd_histogram:+.4f} | {note} |"
                )
            if s.sma_50 and s.sma_200:
                cross = "Golden Cross ▲" if s.sma_50 > s.sma_200 else "Death Cross ▼"
                lines.append(
                    f"| SMA 50/200 | ${s.sma_50:.2f} / ${s.sma_200:.2f} | {cross} |"
                )
            if s.volume_ratio is not None:
                note = "Volume spike" if s.volume_ratio > 1.5 else "Normal"
                lines.append(f"| Volume ratio | {s.volume_ratio:.2f}× | {note} |")
            if s.price_vs_52wk_high_pct is not None:
                lines.append(f"| vs 52-wk high | {s.price_vs_52wk_high_pct:+.1f}% | — |")
            lines.append("")

        # Fundamental
        lines.append("**Fundamental Metrics**")
        lines.append("")
        fund_parts: list[str] = []
        if q.pe_ratio:
            fund_parts.append(f"P/E: {q.pe_ratio:.1f}")
        if q.eps:
            fund_parts.append(f"EPS: ${q.eps:.2f}")
        if q.beta:
            fund_parts.append(f"Beta: {q.beta:.2f}")
        if q.dividend_yield:
            fund_parts.append(f"Yield: {q.dividend_yield * 100:.2f}%")
        if q.fifty_two_week_low and q.fifty_two_week_high:
            fund_parts.append(f"52wk: ${q.fifty_two_week_low:.2f}–${q.fifty_two_week_high:.2f}")
        lines.append("  ·  ".join(fund_parts) if fund_parts else "*No fundamental data available*")
        lines.append("")

        # News
        if r.news_summary:
            lines.append(f"**News Sentiment:** {r.sentiment_score:+.2f}")
            lines.append("")
            lines.append(f"> {r.news_summary}")
            lines.append("")

        # AI reasoning
        if r.reasoning:
            lines.append("**AI Analysis**")
            lines.append("")
            lines.append(r.reasoning)
            lines.append("")

        # Alerts
        if r.alerts_fired:
            lines.append("**⚠ Alerts**")
            lines.append("")
            for alert in r.alerts_fired:
                lines.append(f"- {alert}")
            lines.append("")

        lines.append("---")
        lines.append("")


def _divider(lines: list[str]) -> None:
    lines += ["---", ""]


def _footer(lines: list[str]) -> None:
    lines += [
        "",
        "---",
        "*Generated by Financial-Economic Ticker Analyzer Agent*",
        "*Data sources: yfinance (price/fundamentals), NewsAPI (news)*",
        "*AI analysis powered by Ollama (local LLM)*",
    ]
