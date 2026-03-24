"""Report writer — serialises TickerAnalysis results to JSON / Markdown / HTML."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ticker_agent.config import get

if TYPE_CHECKING:
    from ticker_agent.agents.orchestrator import TickerAnalysis

logger = logging.getLogger(__name__)


def _reports_dir() -> Path:
    d = Path(get("output.reports.dir", "reports"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prune_old_reports(directory: Path, keep: int) -> None:
    files = sorted(directory.glob("report_*.json"), key=os.path.getmtime)
    for old in files[: max(0, len(files) - keep)]:
        old.unlink(missing_ok=True)


def _analysis_to_dict(analysis: "TickerAnalysis") -> dict[str, Any]:
    snap = analysis.snapshot
    rep = analysis.report
    news = analysis.news_result
    return {
        "ticker": analysis.ticker,
        "analysed_at": analysis.analysed_at.isoformat(),
        "success": analysis.success,
        "error": analysis.error,
        "snapshot": {
            "price": snap.price,
            "change_pct": snap.change_pct,
            "volume": snap.volume,
            "market_cap": snap.market_cap,
            "pe_ratio": snap.pe_ratio,
            "forward_pe": snap.forward_pe,
            "eps": snap.eps,
            "beta": snap.beta,
            "week_52_high": snap.week_52_high,
            "week_52_low": snap.week_52_low,
        } if snap else None,
        "scores": {
            "technical": rep.composite_score if rep else None,
            "fundamental": rep.fundamental_score if rep else None,
            "sentiment": rep.sentiment_score if rep else None,
            "composite": rep.composite_score if rep else None,
            "signal": rep.signal if rep else None,
            "confidence": rep.confidence if rep else None,
        } if rep else None,
        "report": {
            "narrative": rep.narrative,
            "key_catalysts": rep.key_catalysts,
            "key_risks": rep.key_risks,
            "price_target_comment": rep.price_target_comment,
        } if rep else None,
        "news": {
            "aggregate_score": news.aggregate_score,
            "aggregate_label": news.aggregate_label,
            "summary": news.summary,
            "articles": [
                {"title": a.title, "sentiment": a.sentiment, "score": a.score}
                for a in news.articles
            ],
        } if news else None,
        "pipeline_payload": analysis.to_pipeline_payload(),
    }


def save_json(analyses: "list[TickerAnalysis]") -> Path:
    """Write a JSON report for a batch of analyses. Returns the file path."""
    directory = _reports_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"report_{ts}.json"

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "ticker_count": len(analyses),
        "analyses": [_analysis_to_dict(a) for a in analyses],
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    logger.info("Report saved → %s", path)

    keep = int(get("output.reports.keep_last", 30))
    _prune_old_reports(directory, keep)
    return path


def save_markdown(analyses: "list[TickerAnalysis]") -> Path:
    """Write a Markdown report. Returns the file path."""
    directory = _reports_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"report_{ts}.md"

    lines = [
        f"# Market Intelligence Report",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
        "---\n",
    ]

    for a in analyses:
        lines.append(f"## {a.ticker}")
        if not a.success:
            lines.append(f"> Error: {a.error}\n")
            continue

        snap = a.snapshot
        rep = a.report
        news = a.news_result

        if snap:
            lines.append(f"**Price:** ${snap.price:.2f}  |  **Change:** {snap.change_pct:+.2f}%\n")

        if rep:
            lines.append(f"**Signal:** `{rep.signal}`  |  **Score:** {rep.composite_score:.0f}/100  |  **Confidence:** {rep.confidence}\n")

        if news:
            lines.append(f"**News sentiment:** {news.aggregate_label} ({news.aggregate_score:+.2f})\n")
            lines.append(f"> {news.summary}\n")

        if rep and rep.narrative:
            lines.append("### Analysis\n")
            lines.append(rep.narrative + "\n")

        if rep and rep.key_catalysts:
            lines.append("### Catalysts\n")
            for c in rep.key_catalysts:
                lines.append(f"- {c}")
            lines.append("")

        if rep and rep.key_risks:
            lines.append("### Risks\n")
            for r in rep.key_risks:
                lines.append(f"- {r}")
            lines.append("")

        if rep and rep.price_target_comment:
            lines.append(f"_{rep.price_target_comment}_\n")

        lines.append("---\n")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Markdown report saved → %s", path)
    return path


def save(analyses: "list[TickerAnalysis]") -> Path:
    """Save report in the format specified by config (json / markdown / html)."""
    fmt = get("output.reports.format", "json").lower()
    if fmt == "markdown":
        return save_markdown(analyses)
    return save_json(analyses)
