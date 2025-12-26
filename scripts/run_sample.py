#!/usr/bin/env python
"""Sample script demonstrating full pipeline execution.

Usage:
    python scripts/run_sample.py --pdf <path_to_pdf>
    python scripts/run_sample.py --pdf <path_to_pdf> --output results.json
    python scripts/run_sample.py --pdf <path_to_pdf> --verbose

This script shows:
1. How to configure logging for pipeline visibility
2. How to run the full pipeline
3. How to inspect and work with results
4. How to export results for different use cases
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any

from src.config.logging import configure_logging
from src.exceptions import PipelineError
from src.pipeline.run import process_pdf


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def print_subsection(title: str) -> None:
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")


async def run_pipeline(pdf_path: Path, verbose: bool = False) -> dict[str, Any]:
    """Run the pipeline and return the result."""
    import os

    # Configure logging based on verbosity
    if verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"
    else:
        os.environ["LOG_LEVEL"] = "INFO"

    try:
        configure_logging()
    except Exception:
        # Fall back to basic logging if settings fail (missing API keys, etc.)
        import logging

        logging.basicConfig(
            level="DEBUG" if verbose else "INFO",
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )

    print_section("PROCESSING PDF")
    print(f"Input: {pdf_path}")
    print(f"Verbose: {verbose}")

    result = await process_pdf(pdf_path)
    return result.model_dump()


def inspect_profile(result: dict[str, Any]) -> None:
    """Display document profile information."""
    print_section("DOCUMENT PROFILE")
    profile = result["profile"]

    print(f"Manager:       {profile['manager_name']}")
    print(f"Title:         {profile.get('title', 'N/A')}")
    print(f"Document Type: {profile['document_type']}")
    print(f"Published:     {profile.get('publication_date', 'Unknown')}")
    print(f"As of Date:    {profile.get('as_of_date', 'Unknown')}")

    if profile.get("regions"):
        print(f"Regions:       {', '.join(profile['regions'])}")

    # Show uncertainty flags
    print_subsection("Uncertainty Flags")
    print(f"Manager uncertain:       {profile['manager_name_uncertain']}")
    print(f"Publication uncertain:   {profile['publication_date_uncertain']}")
    print(f"As-of date uncertain:    {profile['as_of_date_uncertain']}")


def inspect_calls(result: dict[str, Any]) -> None:
    """Display allocation calls."""
    print_section("ALLOCATION CALLS")

    calls = result["allocation_calls"]
    if not calls:
        print("No allocation calls extracted.")
        return

    print(f"Total calls: {len(calls)}")

    for i, call in enumerate(calls, 1):
        print_subsection(f"Call {i}: {call['sub_asset_class']}")
        print(f"  Category:   {call['asset_class_category']}")
        print(f"  Direction:  {call['call']}")
        print(f"  Conviction: {call.get('conviction', 'N/A')}")
        print(f"  Confidence: {call['confidence']:.2f}")
        print(f"  Tooltip:    {call.get('tooltip_text', 'N/A')}")

        if call.get("rationale_bullets"):
            print("  Rationale:")
            for bullet in call["rationale_bullets"]:
                print(f"    - {bullet}")

        if call.get("needs_analyst_review"):
            print("  [NEEDS ANALYST REVIEW]")


def inspect_sentiment(result: dict[str, Any]) -> None:
    """Display overall sentiment."""
    print_section("OVERALL SENTIMENT")

    print(f"Sentiment: {result['overall_sentiment']}")

    if result.get("sentiment_rationale"):
        print("Rationale:")
        for r in result["sentiment_rationale"]:
            print(f"  - {r}")


def inspect_summaries(result: dict[str, Any]) -> None:
    """Display generated summaries."""
    print_section("SUMMARIES")

    summaries = result["summaries"]

    print_subsection("Executive Summary")
    print(summaries["executive_summary"])

    print_subsection("Search Descriptor")
    print(summaries["search_descriptor"])

    print_subsection("Key Takeaways")
    for takeaway in summaries["key_takeaways"]:
        print(f"  - {takeaway['text']}")


def inspect_tags(result: dict[str, Any]) -> None:
    """Display generated tags."""
    print_section("TAGS")

    tags = result["tags"]

    if tags.get("asset_class_tags"):
        print(f"Asset Classes: {', '.join(tags['asset_class_tags'])}")
    if tags.get("region_tags"):
        print(f"Regions:       {', '.join(tags['region_tags'])}")
    if tags.get("theme_tags"):
        print(f"Themes:        {', '.join(tags['theme_tags'])}")
    if tags.get("risk_tags"):
        print(f"Risks:         {', '.join(tags['risk_tags'])}")
    if tags.get("macro_regime_tags"):
        print(f"Macro Regime:  {', '.join(tags['macro_regime_tags'])}")
    if tags.get("instrument_tags"):
        print(f"Instruments:   {', '.join(tags['instrument_tags'])}")


def inspect_confidence(result: dict[str, Any]) -> None:
    """Display confidence scoring results."""
    print_section("CONFIDENCE & REVIEW STATUS")

    confidence = result["confidence"]

    print(f"Overall Confidence:   {confidence['overall_confidence']:.2f}")
    print(f"Confidence Band:      {confidence['confidence_band']}")
    print(f"Routing:              {confidence['routing']}")
    print(f"Attention Required:   {confidence['analyst_attention_required']}")

    if confidence.get("attention_reasons"):
        print("Attention Reasons:")
        for reason in confidence["attention_reasons"]:
            print(f"  - {reason}")

    print_subsection("Field Confidences")
    fields = confidence["field_confidences"]
    for field_name, field_data in fields.items():
        score = field_data["score"]
        reasons = field_data.get("reasons", [])
        reasons_str = f" ({', '.join(reasons)})" if reasons else ""
        print(f"  {field_name}: {score:.2f}{reasons_str}")


def inspect_metadata(result: dict[str, Any]) -> None:
    """Display processing metadata."""
    print_section("PROCESSING METADATA")

    print(f"Document ID:      {result['document_id']}")
    print(f"Pipeline Version: {result['pipeline_version']}")
    print(f"Processed At:     {result['processing_timestamp']}")
    print(f"Processing Time:  {result['total_processing_time_seconds']:.2f}s")


def show_allocator_pro_format(result: dict[str, Any]) -> None:
    """Show how to format for Allocator Pro integration."""
    print_section("ALLOCATOR PRO FORMAT (Module 1/2)")

    # Reconstruct the helper output format
    profile = result["profile"]
    as_of = profile.get("as_of_date") or profile.get("publication_date")

    calls_formatted = [
        {
            "manager_name": profile["manager_name"],
            "document_id": result["document_id"],
            "as_of_date": as_of,
            "asset_class_category": call["asset_class_category"],
            "sub_asset_class": call["sub_asset_class"],
            "call": call["call"],
            "rationale": call.get("rationale_bullets", []),
            "tooltip": call.get("tooltip_text"),
        }
        for call in result["allocation_calls"]
    ]

    print(json.dumps(calls_formatted, indent=2))


def show_search_format(result: dict[str, Any]) -> None:
    """Show how to format for search indexing."""
    print_section("SEARCH INDEX FORMAT")

    profile = result["profile"]
    summaries = result["summaries"]
    tags = result["tags"]

    search_doc = {
        "document_id": result["document_id"],
        "manager_name": profile["manager_name"],
        "title": profile.get("title"),
        "publication_date": profile.get("publication_date"),
        "document_type": profile["document_type"],
        "executive_summary": summaries["executive_summary"],
        "search_descriptor": summaries["search_descriptor"],
        "key_takeaways": [t["text"] for t in summaries["key_takeaways"]],
        "overall_sentiment": result["overall_sentiment"],
        "asset_class_tags": tags.get("asset_class_tags", []),
        "region_tags": tags.get("region_tags", []),
        "theme_tags": tags.get("theme_tags", []),
        "risk_tags": tags.get("risk_tags", []),
        "calls": [
            {
                "asset_class_category": c["asset_class_category"],
                "sub_asset_class": c["sub_asset_class"],
                "call": c["call"],
                "tooltip_text": c.get("tooltip_text"),
            }
            for c in result["allocation_calls"]
        ],
    }

    print(json.dumps(search_doc, indent=2))


def main() -> None:
    """Main entry point for sample script."""
    parser = argparse.ArgumentParser(
        description="Sample script demonstrating Markets Recon pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic run with result inspection
    python scripts/run_sample.py --pdf document.pdf

    # Save full output to JSON file
    python scripts/run_sample.py --pdf document.pdf --output results.json

    # Verbose logging for debugging
    python scripts/run_sample.py --pdf document.pdf --verbose

    # Show only specific sections
    python scripts/run_sample.py --pdf document.pdf --show calls,confidence
        """,
    )

    parser.add_argument(
        "--pdf",
        type=Path,
        required=True,
        help="Path to PDF file to process",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save full JSON output to file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--show",
        type=str,
        default="all",
        help="Comma-separated sections to show: profile,calls,sentiment,summaries,tags,confidence,metadata,allocator,search (default: all)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output only raw JSON (no formatted inspection)",
    )

    args = parser.parse_args()

    # Validate PDF exists
    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    # Run pipeline
    try:
        result = asyncio.run(run_pipeline(args.pdf, verbose=args.verbose))
    except PipelineError as e:
        print(f"\nPipeline Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\nFile Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    # Save output if requested
    if args.output:
        args.output.write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nFull output saved to: {args.output}")

    # JSON-only mode
    if args.json_only:
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    # Determine which sections to show
    sections = (
        args.show.lower().split(",")
        if args.show != "all"
        else [
            "profile",
            "calls",
            "sentiment",
            "summaries",
            "tags",
            "confidence",
            "metadata",
        ]
    )

    # Inspect results
    section_handlers = {
        "profile": inspect_profile,
        "calls": inspect_calls,
        "sentiment": inspect_sentiment,
        "summaries": inspect_summaries,
        "tags": inspect_tags,
        "confidence": inspect_confidence,
        "metadata": inspect_metadata,
        "allocator": show_allocator_pro_format,
        "search": show_search_format,
    }

    for section in sections:
        section = section.strip()
        if section in section_handlers:
            section_handlers[section](result)
        else:
            print(f"\nWarning: Unknown section '{section}'", file=sys.stderr)

    print_section("DONE")
    print("Pipeline completed successfully!")


if __name__ == "__main__":
    main()
