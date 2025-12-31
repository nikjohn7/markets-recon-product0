#!/usr/bin/env python
"""Generate a static HTML report pack from Markets Recon JSON outputs.

Usage:
    python scripts/generate_report_pack.py --input outputs/ --output-dir reports/
    python scripts/generate_report_pack.py --input outputs/ --output-dir reports/ --pdf-dir pdfs/ --copy-pdfs
    python scripts/generate_report_pack.py --input outputs/ --output-dir reports/ --copy-json
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.calls import AllocationCall
from src.models.confidence import ConfidenceResult
from src.models.core import Citation
from src.models.output import ProcessedDocument
from src.models.summaries import DocumentSummaries
from src.models.tags import Tag, TagSet
from src.taxonomy.hierarchy import (
    get_category_display_name,
    get_sub_asset_display_name,
)


@dataclass(frozen=True)
class ReportEntry:
    """Resolved report entry for rendering."""

    doc: ProcessedDocument
    source_json: Path
    report_file: Path
    pdf_path: Path | None
    pdf_rel: str | None
    json_rel: str | None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate static HTML reports from Markets Recon JSON outputs."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Path to a JSON file or directory of JSON outputs",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("reports"),
        help="Output directory for the HTML report pack (default: reports/)",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        help="Optional directory containing source PDFs (matched by filename)",
    )
    parser.add_argument(
        "--copy-pdfs",
        action="store_true",
        help="Copy matched PDFs into the report pack for sharing",
    )
    parser.add_argument(
        "--copy-json",
        action="store_true",
        help="Copy JSON files into the report pack for reference",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search for JSON files recursively when input is a directory",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Markets Recon Report Pack",
        help="Title shown on the index page",
    )
    return parser.parse_args()


def collect_json_paths(input_path: Path, recursive: bool) -> list[Path]:
    """Collect JSON files from a file or directory."""
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    if recursive:
        return sorted(p for p in input_path.rglob("*.json") if p.is_file())
    return sorted(p for p in input_path.glob("*.json") if p.is_file())


def load_document(path: Path) -> ProcessedDocument:
    """Load and validate a ProcessedDocument JSON file."""
    try:
        return ProcessedDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface error with context
        raise ValueError(f"Invalid Markets Recon JSON output: {path}") from exc


def slugify(value: str) -> str:
    """Return a filesystem-safe slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9\\s_-]", "", value)
    collapsed = re.sub(r"[\\s_-]+", "-", cleaned).strip("-").lower()
    return collapsed


def unique_slug(base: str, used: set[str]) -> str:
    """Return a unique slug for filenames."""
    slug = base or "report"
    if slug not in used:
        used.add(slug)
        return slug
    index = 2
    while f"{slug}-{index}" in used:
        index += 1
    final = f"{slug}-{index}"
    used.add(final)
    return final


def find_pdf(source_json: Path, pdf_dir: Path | None) -> Path | None:
    """Locate a PDF matching the JSON filename."""
    candidates: list[Path] = []
    stem = source_json.stem
    stem_no_pdf = stem[:-4] if stem.lower().endswith(".pdf") else stem
    name_variants = [stem, stem_no_pdf]
    search_dirs = [d for d in [pdf_dir, source_json.parent] if d is not None]
    for directory in search_dirs:
        for base in name_variants:
            for suffix in (".pdf", ".PDF"):
                candidates.append(directory / f"{base}{suffix}")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def copy_file(source: Path, dest_dir: Path) -> Path:
    """Copy a file into a directory and return the new path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / source.name
    if destination.exists():
        stem = source.stem
        suffix = source.suffix
        index = 2
        while (dest_dir / f"{stem}-{index}{suffix}").exists():
            index += 1
        destination = dest_dir / f"{stem}-{index}{suffix}"
    shutil.copy2(source, destination)
    return destination


def humanize_token(value: str | None) -> str:
    """Render enum-like tokens into readable text."""
    if not value:
        return "Not stated"
    return value.replace("_", " ").title()


def get_display_name(code: str, is_category: bool = False) -> str:
    """Get human-readable display name for asset class codes.

    Falls back to humanize_token if no display name is defined.
    """
    if is_category:
        display = get_category_display_name(code)
    else:
        display = get_sub_asset_display_name(code)
    return display if display else humanize_token(code)


def format_date(value: date | None) -> str:
    """Format a date for display."""
    if value is None:
        return "Not stated"
    return value.strftime("%b %d, %Y")


def format_datetime(value: datetime | None) -> str:
    """Format a datetime for display."""
    if value is None:
        return "Not stated"
    dt = value
    if dt.tzinfo is None:
        return dt.isoformat(sep=" ", timespec="seconds")
    return dt.astimezone(timezone.utc).isoformat(sep=" ", timespec="seconds")


def format_seconds(value: float) -> str:
    """Format seconds with two decimal places."""
    return f"{value:.2f}s"


def format_percent(value: float | None) -> str:
    """Format a confidence score as percent."""
    if value is None:
        return "Not stated"
    return f"{value * 100:.0f}%"


def escape_text(value: str | None) -> str:
    """Escape text for HTML, preserving line breaks."""
    if not value:
        return '<span class="muted">Not stated</span>'
    return html.escape(value, quote=True).replace("\n", "<br>")


def render_list(items: Sequence[str]) -> str:
    """Render a list of strings as HTML bullets."""
    if not items:
        return '<span class="muted">Not stated</span>'
    bullets = "\n".join(f"<li>{html.escape(item, quote=True)}</li>" for item in items)
    return f"<ul>{bullets}</ul>"


def render_pills(items: Sequence[str]) -> str:
    """Render a list of strings as pill tags."""
    if not items:
        return '<span class="muted">Not stated</span>'
    pills = "\n".join(f'<span class="pill">{html.escape(item, quote=True)}</span>' for item in items)
    return f'<div class="pill-row">{pills}</div>'


def render_citations(citations: Sequence[Citation]) -> str:
    """Render citations with page references and excerpts.

    Only shows excerpt text if available; otherwise just shows page number.
    """
    if not citations:
        return '<p class="muted">No citations provided.</p>'
    rendered: list[str] = []
    for citation in citations:
        meta = f"Page {citation.page}"
        if citation.text_span:
            # Show full citation with excerpt
            excerpt = html.escape(citation.text_span, quote=True)
            rendered.append(
                "<div class=\"citation\">"
                f"<div class=\"citation-meta\">{html.escape(meta, quote=True)}</div>"
                f"<div class=\"citation-text\">{excerpt}</div>"
                "</div>"
            )
        else:
            # No excerpt - just show page reference inline
            rendered.append(f"<span class=\"citation-meta\">{html.escape(meta, quote=True)}</span>")
    return "\n".join(rendered)


def badge_class(value: str) -> str:
    """Map sentiment/call direction/confidence to a badge class."""
    positive = {"OVERWEIGHT", "NET_POSITIVE", "HIGH"}
    negative = {"UNDERWEIGHT", "NET_NEGATIVE", "LOW"}
    warning = {"UNCERTAIN", "MEDIUM"}
    if value in positive:
        return "badge badge--positive"
    if value in negative:
        return "badge badge--negative"
    if value in warning:
        return "badge badge--warning"
    return "badge badge--neutral"


def render_call(call: AllocationCall, index: int) -> str:
    """Render a single allocation call detail block."""
    call_direction = call.call.value
    direction_badge = f'<span class="{badge_class(call_direction)}">{humanize_token(call_direction)}</span>'
    conviction_text = humanize_token(call.conviction.value) if call.conviction else "Not stated"
    review_flag = ""
    if call.needs_analyst_review:
        review_reason = escape_text(call.review_reason) if call.review_reason else "Review required"
        review_flag = f'<span class="badge badge--alert">Review</span> {review_reason}'

    indicators = ""
    if call.key_indicators:
        indicator_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(ind.name, quote=True)}</td>"
            f"<td>{html.escape(humanize_token(ind.direction.value), quote=True)}</td>"
            f"<td>{escape_text(ind.why_it_matters)}</td>"
            "</tr>"
            for ind in call.key_indicators
        )
        indicators = (
            "<table class=\"table\">"
            "<thead><tr><th>Indicator</th><th>Direction</th><th>Why it matters</th></tr></thead>"
            f"<tbody>{indicator_rows}</tbody></table>"
        )
    else:
        indicators = '<p class="muted">No indicators listed.</p>'

    # Use human-readable display names for asset classes
    sub_asset_display = get_display_name(call.sub_asset_class, is_category=False)
    category_display = get_display_name(call.asset_class_category, is_category=True)

    return (
        "<details class=\"call-card\">"
        "<summary>"
        f"<div class=\"call-title\">Call {index}: {html.escape(sub_asset_display, quote=True)}</div>"
        "<div class=\"call-badges\">"
        f"{direction_badge}"
        f"<span class=\"badge badge--outline\">{html.escape(category_display, quote=True)}</span>"
        f"<span class=\"badge badge--outline\">Conviction {html.escape(conviction_text, quote=True)}</span>"
        f"<span class=\"badge badge--outline\">Confidence {format_percent(call.confidence)}</span>"
        "</div>"
        "</summary>"
        "<div class=\"call-body\">"
        f"<div class=\"call-meta\"><div><strong>Time horizon:</strong> {escape_text(call.time_horizon)}</div>"
        f"<div><strong>Tooltip:</strong> {escape_text(call.tooltip_text)}</div></div>"
        f"<div class=\"call-review\">{review_flag}</div>"
        "<div class=\"call-grid\">"
        "<div><h4>Rationale</h4>"
        f"{render_list(call.rationale_bullets)}</div>"
        "<div><h4>Key Risks</h4>"
        f"{render_list(call.key_risks)}</div>"
        "<div><h4>Actionable Takeaways</h4>"
        f"{render_list(call.actionable_takeaways)}</div>"
        "</div>"
        "<div class=\"call-indicators\"><h4>Key Indicators</h4>"
        f"{indicators}</div>"
        "<div class=\"call-citations\"><h4>Citations</h4>"
        f"{render_citations(call.citations)}</div>"
        "</div>"
        "</details>"
    )


def render_summary_block(summaries: DocumentSummaries) -> str:
    """Render the document summary section."""
    takeaways = []
    for takeaway in summaries.key_takeaways:
        takeaways.append(
            "<div class=\"takeaway\">"
            f"<div class=\"takeaway-text\">{escape_text(takeaway.text)}</div>"
            f"<div class=\"takeaway-citations\">{render_citations(takeaway.citations)}</div>"
            "</div>"
        )
    takeaways_html = "\n".join(takeaways) if takeaways else '<p class="muted">No takeaways.</p>'
    return (
        "<div class=\"card\">"
        "<h3>Executive Summary</h3>"
        "<div class=\"grid\">"
        f"<div><div class=\"metric-label\">Summary confidence</div>"
        f"<div class=\"metric-value\">{format_percent(summaries.confidence)}</div></div>"
        "</div>"
        f"<p>{escape_text(summaries.executive_summary)}</p>"
        "<h4>Search Descriptor</h4>"
        f"<p>{escape_text(summaries.search_descriptor)}</p>"
        "<h4>Key Takeaways</h4>"
        f"{takeaways_html}"
        "</div>"
    )


def render_tag_block(tags: TagSet) -> str:
    """Render tags and classifications."""
    return (
        "<div class=\"card\">"
        "<h3>Tags</h3>"
        "<div class=\"grid\">"
        f"<div><div class=\"metric-label\">Tag confidence</div>"
        f"<div class=\"metric-value\">{format_percent(tags.confidence)}</div></div>"
        "</div>"
        "<div class=\"tag-group\"><h4>Asset Classes</h4>"
        f"{render_pills(tags.asset_class_tags)}</div>"
        "<div class=\"tag-group\"><h4>Regions</h4>"
        f"{render_pills(tags.region_tags)}</div>"
        "<div class=\"tag-group\"><h4>Themes</h4>"
        f"{render_pills(tags.theme_tags)}</div>"
        "<div class=\"tag-group\"><h4>Risks</h4>"
        f"{render_pills(tags.risk_tags)}</div>"
        "<div class=\"tag-group\"><h4>Instruments</h4>"
        f"{render_pills(tags.instrument_tags)}</div>"
        "<div class=\"tag-group\"><h4>Styles</h4>"
        f"{render_pills(tags.style_tags)}</div>"
        "<div class=\"tag-group\"><h4>Macro Regimes</h4>"
        f"{render_pills(tags.macro_regime_tags)}</div>"
        "<h4>All Tags</h4>"
        f"{render_all_tags(tags.all_tags)}"
        "</div>"
    )


def render_all_tags(tags: Sequence[Tag]) -> str:
    """Render detailed tags table."""
    if not tags:
        return '<p class="muted">No tags listed.</p>'
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(humanize_token(tag.tag_type.value), quote=True)}</td>"
        f"<td>{html.escape(tag.value, quote=True)}</td>"
        f"<td>{format_percent(tag.confidence)}</td>"
        f"<td>{html.escape(tag.source, quote=True)}</td>"
        "</tr>"
        for tag in tags
    )
    return (
        "<table class=\"table\">"
        "<thead><tr><th>Type</th><th>Value</th><th>Confidence</th><th>Source</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def render_confidence_block(confidence: ConfidenceResult) -> str:
    """Render confidence summary and field-level details."""
    reasons = render_list(confidence.attention_reasons)
    verification = (
        f"<div><strong>Verification agreement:</strong> {format_percent(confidence.verification_agreement)}</div>"
        if confidence.verification_agreement is not None
        else "<div><strong>Verification agreement:</strong> Not stated</div>"
    )
    disagreed = render_list(confidence.disagreed_fields)
    field_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(field.field_name, quote=True)}</td>"
        f"<td>{format_percent(field.confidence)}</td>"
        f"<td>{format_percent(field.evidence_strength)}</td>"
        f"<td>{'Yes' if field.has_explicit_evidence else 'No'}</td>"
        f"<td>{', '.join(html.escape(r, quote=True) for r in field.reasons) if field.reasons else ''}</td>"
        "</tr>"
        for field in confidence.field_confidences
    )
    return (
        "<div class=\"card\">"
        "<h3>Confidence and Review Status</h3>"
        "<div class=\"grid\">"
        f"<div><div class=\"metric-label\">Overall confidence</div>"
        f"<div class=\"metric-value\">{format_percent(confidence.overall_confidence)}</div></div>"
        f"<div><div class=\"metric-label\">Confidence band</div>"
        f"<div class=\"metric-value\">"
        f"<span class=\"{badge_class(confidence.confidence_band.value)}\">"
        f"{humanize_token(confidence.confidence_band.value)}</span></div></div>"
        f"<div><div class=\"metric-label\">Attention required</div>"
        f"<div class=\"metric-value\">{'Yes' if confidence.analyst_attention_required else 'No'}</div></div>"
        f"<div><div class=\"metric-label\">Extraction coverage</div>"
        f"<div class=\"metric-value\">{format_percent(confidence.extraction_coverage)}</div></div>"
        "</div>"
        "<h4>Attention Reasons</h4>"
        f"{reasons}"
        "<h4>Verification</h4>"
        f"{verification}"
        "<div><strong>Disagreed fields:</strong></div>"
        f"{disagreed}"
        "<h4>Field Confidences</h4>"
        "<table class=\"table\">"
        "<thead><tr><th>Field</th><th>Confidence</th><th>Evidence</th><th>Explicit</th><th>Reasons</th></tr></thead>"
        f"<tbody>{field_rows}</tbody></table>"
        "</div>"
    )


def render_profile_block(doc: ProcessedDocument) -> str:
    """Render document profile metadata."""
    profile = doc.profile
    asset_classes = render_pills(profile.asset_classes_covered)
    regions = render_pills(profile.regions)
    flags = (
        "<ul>"
        f"<li>Manager uncertain: {'Yes' if profile.manager_name_uncertain else 'No'}</li>"
        f"<li>Publication date uncertain: {'Yes' if profile.publication_date_uncertain else 'No'}</li>"
        f"<li>As-of date uncertain: {'Yes' if profile.as_of_date_uncertain else 'No'}</li>"
        "</ul>"
    )
    return (
        "<div class=\"card\">"
        "<h3>Document Profile</h3>"
        "<div class=\"grid\">"
        f"<div><div class=\"metric-label\">Manager</div><div class=\"metric-value\">{escape_text(profile.manager_name)}</div></div>"
        f"<div><div class=\"metric-label\">Title</div><div class=\"metric-value\">{escape_text(profile.title)}</div></div>"
        f"<div><div class=\"metric-label\">Document type</div><div class=\"metric-value\">{humanize_token(profile.document_type.value)}</div></div>"
        f"<div><div class=\"metric-label\">Publication date</div><div class=\"metric-value\">{format_date(profile.publication_date)}</div></div>"
        f"<div><div class=\"metric-label\">As-of date</div><div class=\"metric-value\">{format_date(profile.as_of_date)}</div></div>"
        f"<div><div class=\"metric-label\">Time horizon</div><div class=\"metric-value\">{escape_text(profile.time_horizon)}</div></div>"
        f"<div><div class=\"metric-label\">Intended audience</div><div class=\"metric-value\">{escape_text(profile.intended_audience)}</div></div>"
        "</div>"
        "<h4>Asset classes covered</h4>"
        f"{asset_classes}"
        "<h4>Regions</h4>"
        f"{regions}"
        "<h4>Uncertainty Flags</h4>"
        f"{flags}"
        "<h4>Profile Citations</h4>"
        f"{render_citations(profile.citations)}"
        "</div>"
    )


def render_sentiment_block(doc: ProcessedDocument) -> str:
    """Render overall sentiment with rationale and citations."""
    sentiment = doc.overall_sentiment.value
    return (
        "<div class=\"card\">"
        "<h3>Overall Sentiment</h3>"
        f"<p><span class=\"{badge_class(sentiment)}\">{humanize_token(sentiment)}</span></p>"
        "<h4>Rationale</h4>"
        f"{render_list(doc.sentiment_rationale)}"
        "<h4>Citations</h4>"
        f"{render_citations(doc.sentiment_citations)}"
        "</div>"
    )


def render_calls_block(calls: Sequence[AllocationCall]) -> str:
    """Render all allocation calls."""
    if not calls:
        return "<div class=\"card\"><h3>Allocation Calls</h3><p>No calls extracted.</p></div>"
    call_details = "\n".join(render_call(call, idx + 1) for idx, call in enumerate(calls))
    overview_rows = "\n".join(
        "<tr>"
        f"<td>{idx + 1}</td>"
        f"<td>{html.escape(get_display_name(call.asset_class_category, is_category=True), quote=True)}</td>"
        f"<td>{html.escape(get_display_name(call.sub_asset_class, is_category=False), quote=True)}</td>"
        f"<td>{humanize_token(call.call.value)}</td>"
        f"<td>{humanize_token(call.conviction.value) if call.conviction else 'Not stated'}</td>"
        f"<td>{format_percent(call.confidence)}</td>"
        f"<td>{'Yes' if call.needs_analyst_review else 'No'}</td>"
        "</tr>"
        for idx, call in enumerate(calls)
    )
    overview = (
        "<table class=\"table\">"
        "<thead><tr><th>#</th><th>Category</th><th>Sub-Asset</th><th>Call</th>"
        "<th>Conviction</th><th>Confidence</th><th>Review</th></tr></thead>"
        f"<tbody>{overview_rows}</tbody></table>"
    )
    return (
        "<div class=\"card\">"
        "<h3>Allocation Calls</h3>"
        "<h4>Overview</h4>"
        f"{overview}"
        "<h4>Call Details</h4>"
        f"{call_details}"
        "</div>"
    )


def render_metadata_block(doc: ProcessedDocument, entry: ReportEntry) -> str:
    """Render processing metadata."""
    pdf_info = '<span class="muted">Source PDF not bundled.</span>'
    if entry.pdf_rel:
        pdf_info = f'<a href="{html.escape(entry.pdf_rel, quote=True)}">Open PDF</a>'
    elif entry.pdf_path:
        pdf_info = f'<span class="muted">Original path: {html.escape(str(entry.pdf_path), quote=True)}</span>'

    json_info = '<span class="muted">Raw JSON not bundled.</span>'
    if entry.json_rel:
        json_info = f'<a href="{html.escape(entry.json_rel, quote=True)}">Download JSON</a>'

    component_ids = (
        "<ul>"
        f"<li>Profile: {html.escape(doc.profile.document_id, quote=True)}</li>"
        f"<li>Summaries: {html.escape(doc.summaries.document_id, quote=True)}</li>"
        f"<li>Tags: {html.escape(doc.tags.document_id, quote=True)}</li>"
        f"<li>Confidence: {html.escape(doc.confidence.document_id, quote=True)}</li>"
        "</ul>"
    )
    return (
        "<div class=\"card\">"
        "<h3>Processing Metadata</h3>"
        "<div class=\"grid\">"
        f"<div><div class=\"metric-label\">Document ID</div><div class=\"metric-value\">"
        f"{html.escape(doc.document_id, quote=True)}</div></div>"
        f"<div><div class=\"metric-label\">Pipeline version</div><div class=\"metric-value\">"
        f"{html.escape(doc.pipeline_version, quote=True)}</div></div>"
        f"<div><div class=\"metric-label\">Processed at</div><div class=\"metric-value\">"
        f"{format_datetime(doc.processing_timestamp)}</div></div>"
        f"<div><div class=\"metric-label\">Processing time</div><div class=\"metric-value\">"
        f"{format_seconds(doc.total_processing_time_seconds)}</div></div>"
        f"<div><div class=\"metric-label\">Source PDF</div><div class=\"metric-value\">{pdf_info}</div></div>"
        f"<div><div class=\"metric-label\">Raw JSON</div><div class=\"metric-value\">{json_info}</div></div>"
        "</div>"
        "<h4>Component IDs</h4>"
        f"{component_ids}"
        "</div>"
    )


def base_css() -> str:
    """Base CSS for all report pages."""
    return """
    :root {
        --ink: #1f1b16;
        --muted: #6d6a63;
        --paper: #f6f2eb;
        --card: #ffffff;
        --line: #e2dbd1;
        --accent: #0c4a4a;
        --accent-2: #b25a26;
        --positive: #1f6f4a;
        --negative: #9b2c2c;
        --warning: #b06b18;
        --neutral: #5b646c;
        --alert: #b9372c;
        --shadow: 0 4px 12px rgba(31, 27, 22, 0.06), 0 1px 2px rgba(31, 27, 22, 0.04);
        --shadow-hover: 0 12px 24px rgba(31, 27, 22, 0.1), 0 4px 8px rgba(31, 27, 22, 0.04);
    }
    * { box-sizing: border-box; }
    body {
        margin: 0;
        color: var(--ink);
        font-family: "Inter", "Segoe UI", "BF Pro", "Avenir Next", "Gill Sans", sans-serif;
        background:
            radial-gradient(900px 600px at 5% -10%, #efe2d3 0%, transparent 60%),
            radial-gradient(800px 500px at 95% 10%, #dfeae6 0%, transparent 55%),
            linear-gradient(180deg, #f8f4ee 0%, #f0ebe3 100%);
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    h1, h2, h3, h4 {
        font-family: "Iowan Old Style", "Palatino Linotype", serif;
        margin-top: 0;
        font-feature-settings: "onum" 1, "kern" 1;
    }
    h3 {
        margin-bottom: 20px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--line);
        font-weight: 600;
        letter-spacing: -0.01em;
    }
    h4 {
        margin-top: 28px;
        margin-bottom: 12px;
        font-size: 0.85rem;
        color: var(--neutral);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }
    h4:first-child {
        margin-top: 0;
    }
    a { color: var(--accent); text-decoration: none; transition: color 0.15s; }
    a:hover { text-decoration: underline; color: var(--accent-2); }
    .page {
        max-width: 1120px;
        margin: 0 auto;
        padding: 40px 24px 64px;
    }
    .hero {
        background: var(--card);
        border: 1px solid var(--line);
        border-left: 6px solid var(--accent);
        padding: 32px 40px;
        border-radius: 12px;
        box-shadow: var(--shadow);
        position: relative;
        overflow: hidden;
    }
    .hero::after {
        content: "";
        position: absolute;
        inset: auto -40% -40% auto;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle at center, rgba(12, 74, 74, 0.08), transparent 70%);
        pointer-events: none;
    }
    .hero .subtitle {
        color: var(--muted);
        margin-top: 4px;
        font-size: 1.1em;
    }
    .hero .meta-line {
        color: var(--muted);
        margin-top: 12px;
        font-size: 0.9rem;
        display: flex;
        gap: 20px;
    }
    .hero .meta-line div {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .nav-link {
        display: inline-block;
        margin-top: 16px;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 28px 32px;
        box-shadow: var(--shadow);
        margin-top: 24px;
    }
    .card p {
        line-height: 1.6;
        margin: 12px 0;
        max-width: 70ch;
    }
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 24px;
    }
    .grid + h4 { margin-top: 32px; }
    .table + h4 {
        margin-top: 40px;
        padding-top: 24px;
        border-top: 1px solid var(--line);
    }
    .metric-label {
        color: var(--muted);
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.06em;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--ink);
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.01em;
    }
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        background: #eef1f1;
        color: var(--neutral);
        white-space: nowrap;
        border: 1px solid transparent;
    }
    .badge--positive { background: #e6f0eb; color: var(--positive); border-color: rgba(31, 111, 74, 0.1); }
    .badge--negative { background: #fdf2f2; color: var(--negative); border-color: rgba(155, 44, 44, 0.1); }
    .badge--warning { background: #fff8eb; color: var(--warning); border-color: rgba(176, 107, 24, 0.1); }
    .badge--neutral { background: #f3f5f6; color: var(--neutral); border-color: rgba(91, 100, 108, 0.1); }
    .badge--outline {
        background: transparent;
        border: 1px solid var(--line);
        color: var(--muted);
    }
    .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
    }
    .pill {
        border: 1px solid var(--line);
        background: #fbfaf7;
        padding: 4px 10px;
        border-radius: 99px;
        font-size: 0.78rem;
        color: var(--ink);
        transition: background 0.1s;
    }
    .pill:hover { background: #f0ebe3; }
    .table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 16px;
        font-size: 0.9rem;
    }
    .table th {
        color: var(--muted);
        font-weight: 600;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        text-align: left;
        padding: 12px 10px;
        border-bottom: 2px solid var(--line);
    }
    .table td {
        padding: 12px 10px;
        border-bottom: 1px solid var(--line);
        font-variant-numeric: tabular-nums;
        vertical-align: top;
    }
    /* Simple zebra striping for data density */
    .table tbody tr:nth-child(even) {
        background-color: rgba(0,0,0,0.015);
    }
    .table tbody tr:hover {
        background: rgba(12, 74, 74, 0.03);
    }
    
    ul { margin: 8px 0 0 20px; padding: 0; }
    ul li { margin-bottom: 6px; line-height: 1.5; padding-left: 4px; }
    
    .call-card {
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        background: #fcfbf8;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .call-card:hover { border-color: #d0c9be; box-shadow: var(--shadow); transform: translateY(-1px); }
    .call-card summary {
        cursor: pointer;
        list-style: none;
        display: flex;
        flex-direction: column;
        gap: 12px;
        position: relative;
        padding-right: 32px;
    }
    .call-card summary::-webkit-details-marker { display: none; }
    .call-card summary::after {
        content: "+";
        position: absolute;
        right: 0;
        top: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 400;
        font-size: 1.5rem;
        color: var(--muted);
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        line-height: 1;
    }
    .call-card[open] summary::after {
        transform: rotate(45deg);
    }
    .call-title { font-weight: 700; font-size: 1.05rem; }
    .call-badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .call-body {
        margin-top: 24px;
        padding-top: 20px;
        border-top: 1px solid var(--line);
        display: grid;
        gap: 24px;
        animation: slideDown 0.3s ease-out;
    }
    @keyframes slideDown { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
    
    .call-grid {
        display: grid;
        gap: 32px;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }
    .call-meta {
        display: flex;
        gap: 24px;
        color: var(--muted);
        font-size: 0.85rem;
        padding: 12px 16px;
        background: rgba(12, 74, 74, 0.04);
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .citation {
        border-left: 3px solid var(--accent);
        padding-left: 16px;
        margin-bottom: 20px;
        background: linear-gradient(to right, rgba(12, 74, 74, 0.02), transparent);
        padding: 8px 16px;
        border-radius: 0 4px 4px 0;
    }
    .citation-meta {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
        margin-bottom: 4px;
        font-weight: 700;
    }
    .citation-text {
        font-size: 0.92rem;
        line-height: 1.6;
        color: var(--ink);
        font-style: italic;
        font-family: Georgia, serif;
    }
    .takeaway {
        border: 1px solid rgba(12, 74, 74, 0.15);
        border-left: 4px solid var(--accent);
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
        background: #fbf9f4;
    }
    footer {
        color: var(--muted);
        font-size: 0.82rem;
        margin-top: 64px;
        padding-top: 32px;
        border-top: 1px solid var(--line);
        text-align: center;
        letter-spacing: 0.02em;
    }
    .reveal {
        animation: rise 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
        opacity: 0;
        transform: translateY(20px);
    }
    @keyframes rise {
        to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
        .reveal { animation: none; opacity: 1; transform: none; }
    }
    @media print {
        body { background: white; color: black; }
        .page { max-width: 100%; padding: 0; margin: 0; }
        .hero, .card, .call-card { box-shadow: none; border: 1px solid #ccc; break-inside: avoid; }
        .reveal { animation: none; opacity: 1; transform: none; }
        .call-card[open] .call-body { display: block; }
        details { display: block; }
        a { text-decoration: none; color: black; }
        @page { margin: 2cm; }
    }
    @media (max-width: 720px) {
        .page { padding: 24px 16px; }
        .hero { padding: 24px 20px; }
        .card { padding: 24px 20px; }
    }
    """


def render_page(title: str, body: str) -> str:
    """Wrap body content in a full HTML page."""
    css = base_css()
    return (
        "<!doctype html>"
        "<html lang=\"en\">"
        "<head>"
        "<meta charset=\"utf-8\" />"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        f"<title>{html.escape(title, quote=True)}</title>"
        f"<style>{css}</style>"
        "</head>"
        "<body>"
        f"{body}"
        "</body>"
        "</html>"
    )


def wrap_reveal(content: str, delay: float) -> str:
    """Wrap content with a staggered reveal animation."""
    return f'<div class="reveal" style="animation-delay:{delay:.2f}s">{content}</div>'


def render_document(
    entry: ReportEntry, pack_title: str, generated_at: datetime, show_index_link: bool = True
) -> str:
    """Render a single document report page."""
    doc = entry.doc
    profile = doc.profile
    title = f"{profile.manager_name} - {profile.title}"

    overview = (
        "<div class=\"card\">"
        "<div class=\"grid\">"
        f"<div><div class=\"metric-label\">Calls extracted</div>"
        f"<div class=\"metric-value\">{len(doc.allocation_calls)}</div></div>"
        f"<div><div class=\"metric-label\">Overall sentiment</div>"
        f"<div class=\"metric-value\"><span class=\"{badge_class(doc.overall_sentiment.value)}\">"
        f"{humanize_token(doc.overall_sentiment.value)}</span></div></div>"
        f"<div><div class=\"metric-label\">Confidence band</div>"
        f"<div class=\"metric-value\"><span class=\"{badge_class(doc.confidence.confidence_band.value)}\">"
        f"{humanize_token(doc.confidence.confidence_band.value)}</span></div></div>"
        f"<div><div class=\"metric-label\">Attention required</div>"
        f"<div class=\"metric-value\">{'Yes' if doc.confidence.analyst_attention_required else 'No'}</div></div>"
        "</div>"
        "</div>"
    )

    sections = [
        overview,
        render_profile_block(doc),
        render_summary_block(doc.summaries),
        render_sentiment_block(doc),
        render_calls_block(doc.allocation_calls),
        render_tag_block(doc.tags),
        render_confidence_block(doc.confidence),
        render_metadata_block(doc, entry),
    ]
    staggered = "\n".join(wrap_reveal(section, 0.08 + idx * 0.06) for idx, section in enumerate(sections))
    # Only show "Back to index" link when there are multiple documents
    index_link = '<a class="nav-link" href="index.html">Back to index</a>' if show_index_link else ""
    body = (
        "<div class=\"page\">"
        "<header class=\"hero reveal\">"
        f"<h1>{escape_text(profile.manager_name)}</h1>"
        f"<div class=\"subtitle\">{escape_text(profile.title)}</div>"
        "<div class=\"meta-line\">"
        f"{humanize_token(profile.document_type.value)}"
        f" | Published {format_date(profile.publication_date)}"
        f" | As of {format_date(profile.as_of_date)}"
        "</div>"
        "<div class=\"meta-line\">"
        f"Document ID {html.escape(doc.document_id, quote=True)}"
        "</div>"
        f"{index_link}"
        "</header>"
        f"{staggered}"
        "<footer>"
        f"Generated {format_datetime(generated_at)} | {html.escape(pack_title, quote=True)}"
        "</footer>"
        "</div>"
    )
    return render_page(title, body)


def render_index(entries: Sequence[ReportEntry], pack_title: str, generated_at: datetime) -> str:
    """Render the index page for the report pack."""
    rows = "\n".join(
        "<tr>"
        f"<td><a href=\"{html.escape(entry.report_file.name, quote=True)}\">"
        f"{escape_text(entry.doc.profile.manager_name)}</a></td>"
        f"<td>{escape_text(entry.doc.profile.title)}</td>"
        f"<td>{humanize_token(entry.doc.profile.document_type.value)}</td>"
        f"<td>{format_date(entry.doc.profile.publication_date)}</td>"
        f"<td>{len(entry.doc.allocation_calls)}</td>"
        f"<td><span class=\"{badge_class(entry.doc.overall_sentiment.value)}\">"
        f"{humanize_token(entry.doc.overall_sentiment.value)}</span></td>"
        f"<td><span class=\"{badge_class(entry.doc.confidence.confidence_band.value)}\">"
        f"{humanize_token(entry.doc.confidence.confidence_band.value)}</span></td>"
        f"<td>{'Yes' if entry.doc.confidence.analyst_attention_required else 'No'}</td>"
        "</tr>"
        for entry in entries
    )
    body = (
        "<div class=\"page\">"
        "<header class=\"hero reveal\">"
        f"<h1>{html.escape(pack_title, quote=True)}</h1>"
        "<div class=\"subtitle\">Client-ready summaries of processed fund manager PDFs.</div>"
        f"<div class=\"meta-line\">Generated {format_datetime(generated_at)}</div>"
        "</header>"
        "<div class=\"card reveal\" style=\"animation-delay:0.1s\">"
        "<h3>Document Overview</h3>"
        "<table class=\"table\">"
        "<thead><tr><th>Manager</th><th>Title</th><th>Type</th><th>Publication</th>"
        "<th>Calls</th><th>Sentiment</th><th>Confidence</th><th>Review</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "</div>"
        "<footer>"
        "Open any report to see full calls, citations, and confidence details."
        "</footer>"
        "</div>"
    )
    return render_page(pack_title, body)


def resolve_entries(
    json_paths: Sequence[Path],
    output_dir: Path,
    pdf_dir: Path | None,
    copy_pdfs: bool,
    copy_json: bool,
) -> list[ReportEntry]:
    """Load and resolve report entries."""
    entries: list[ReportEntry] = []
    used_slugs: set[str] = set()
    pdf_output_dir = output_dir / "pdfs" if copy_pdfs else None
    json_output_dir = output_dir / "json" if copy_json else None

    for path in json_paths:
        try:
            doc = load_document(path)
        except ValueError as exc:
            print(f"Skipping {path}: {exc}", file=sys.stderr)
            continue
        slug_base = slugify(f"{doc.profile.manager_name}-{doc.profile.document_type.value}")
        slug = unique_slug(slug_base or doc.document_id, used_slugs)
        report_file = output_dir / f"{slug}.html"

        pdf_path = find_pdf(path, pdf_dir)
        pdf_rel: str | None = None
        if pdf_path and copy_pdfs and pdf_output_dir:
            copied = copy_file(pdf_path, pdf_output_dir)
            pdf_rel = f"pdfs/{copied.name}"

        json_rel: str | None = None
        if copy_json and json_output_dir:
            copied_json = copy_file(path, json_output_dir)
            json_rel = f"json/{copied_json.name}"

        entries.append(
            ReportEntry(
                doc=doc,
                source_json=path,
                report_file=report_file,
                pdf_path=pdf_path,
                pdf_rel=pdf_rel,
                json_rel=json_rel,
            )
        )
    return entries


def write_reports(entries: Sequence[ReportEntry], pack_title: str, output_dir: Path) -> None:
    """Write HTML reports and index.

    Only generates index.html when there are multiple documents.
    """
    generated_at = datetime.now(timezone.utc)
    show_index_link = len(entries) > 1
    for entry in entries:
        html_content = render_document(entry, pack_title, generated_at, show_index_link)
        entry.report_file.write_text(html_content, encoding="utf-8")
    # Only generate index.html for multiple documents
    if show_index_link:
        index_html = render_index(entries, pack_title, generated_at)
        (output_dir / "index.html").write_text(index_html, encoding="utf-8")


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_paths = collect_json_paths(args.input, args.recursive)
    if not json_paths:
        print("No JSON files found to process.", file=sys.stderr)
        return 1

    entries = resolve_entries(
        json_paths=json_paths,
        output_dir=output_dir,
        pdf_dir=args.pdf_dir,
        copy_pdfs=args.copy_pdfs,
        copy_json=args.copy_json,
    )
    if not entries:
        print("No valid Markets Recon outputs found.", file=sys.stderr)
        return 1

    write_reports(entries, args.title, output_dir)
    print(f"Wrote {len(entries)} report(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
