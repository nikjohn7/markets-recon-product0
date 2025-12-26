"""Pipeline orchestrator and CLI.

Executes stages 0-10 in sequence, handles failures gracefully, and persists results.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.logging import configure_logging
from src.exceptions import ExtractionError, LLMError, PipelineError, StorageError, ValidationError
from src.llm.client import LLMClient, PipelineStage
from src.models.output import ProcessedDocument
from src.pipeline.stages.s0_ingest import stage_ingest
from src.pipeline.stages.s1_extract import stage_extract
from src.pipeline.stages.s2_clean import stage_clean
from src.pipeline.stages.s3_index import stage_index
from src.pipeline.stages.s4_metadata import stage_metadata
from src.pipeline.stages.s5_candidates import stage_candidates
from src.pipeline.stages.s6_calls import stage_calls
from src.pipeline.stages.s7_summaries import stage_summaries
from src.pipeline.stages.s8_tooltips import stage_tooltips
from src.pipeline.stages.s9_tags import stage_tags
from src.pipeline.stages.s10_confidence import stage_confidence
from src.storage.database import Database

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.1.0"


async def process_pdf(
    pdf_path: str | Path,
    source_metadata: dict[str, Any] | None = None,
    db: Database | None = None,
    llm_client: LLMClient | None = None,
) -> ProcessedDocument:
    """Process a PDF through the full pipeline (stages 0-10).

    Args:
        pdf_path: Path to PDF file
        source_metadata: Optional metadata about the document source
        db: Optional database instance (for testing)
        llm_client: Optional LLM client (for testing)

    Returns:
        ProcessedDocument with all extracted data

    Raises:
        PipelineError: If pipeline execution fails
        FileNotFoundError: If PDF file doesn't exist
    """
    start_time = time.monotonic()
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_bytes = pdf_path.read_bytes()
    metadata = source_metadata or {"filename": pdf_path.name}

    if db is None:
        db = Database()
    if llm_client is None:
        llm_client = LLMClient()

    run_id = str(uuid.uuid4())
    document_id: str | None = None
    stages_completed: list[str] = []

    try:
        # Stage 0: Ingest
        logger.info("[Stage 0] Ingesting PDF")
        ingest_result = await stage_ingest(pdf_bytes, metadata)
        document_id = ingest_result.document_id
        stages_completed.append("s0_ingest")
        _record_run_start(db, run_id, document_id, llm_client)

        # Stage 1: Extract
        logger.info("[Stage 1] Extracting text")
        doc_json = await stage_extract(ingest_result)
        stages_completed.append("s1_extract")

        # Stage 2: Clean
        logger.info("[Stage 2] Cleaning document")
        cleaned_doc = await stage_clean(doc_json)
        stages_completed.append("s2_clean")

        # Stage 3: Index
        logger.info("[Stage 3] Building retrieval index")
        index = await stage_index(cleaned_doc)
        stages_completed.append("s3_index")

        # Stage 4: Metadata
        logger.info("[Stage 4] Extracting metadata")
        profile = await stage_metadata(cleaned_doc, index, llm_client)
        stages_completed.append("s4_metadata")

        # Stage 5: Candidates
        logger.info("[Stage 5] Retrieving candidates")
        candidate_set = await stage_candidates(cleaned_doc, index, llm_client)
        stages_completed.append("s5_candidates")

        # Stage 6: Calls
        logger.info("[Stage 6] Extracting calls")
        call_output = await stage_calls(profile, candidate_set, llm_client)
        stages_completed.append("s6_calls")

        # Stage 7: Summaries
        logger.info("[Stage 7] Generating summaries")
        summaries = await stage_summaries(
            document_id, index, call_output, profile, llm_client
        )
        stages_completed.append("s7_summaries")

        # Stage 8: Tooltips
        logger.info("[Stage 8] Generating tooltips")
        call_output = await stage_tooltips(call_output, llm_client)
        stages_completed.append("s8_tooltips")

        # Stage 9: Tags
        logger.info("[Stage 9] Generating tags")
        tags = await stage_tags(
            document_id, cleaned_doc, call_output, profile, index, llm_client
        )
        stages_completed.append("s9_tags")

        # Stage 10: Confidence
        logger.info("[Stage 10] Computing confidence")
        confidence = await stage_confidence(
            doc_json, profile, call_output.allocation_calls, summaries, candidate_set.candidates
        )
        stages_completed.append("s10_confidence")

        elapsed = time.monotonic() - start_time

        result = ProcessedDocument(
            document_id=document_id,
            profile=profile,
            allocation_calls=call_output.allocation_calls,
            overall_sentiment=call_output.overall_sentiment,
            sentiment_rationale=call_output.sentiment_rationale,
            sentiment_citations=call_output.sentiment_citations,
            summaries=summaries,
            tags=tags,
            confidence=confidence,
            processing_timestamp=datetime.now(UTC),
            pipeline_version=PIPELINE_VERSION,
            total_processing_time_seconds=elapsed,
        )

        _persist_results(db, result, run_id, stages_completed, elapsed)
        logger.info(f"Pipeline complete in {elapsed:.2f}s: {document_id}")
        return result

    except (ExtractionError, ValidationError, LLMError, StorageError) as e:
        elapsed = time.monotonic() - start_time
        _record_run_failure(db, run_id, document_id, stages_completed, elapsed, str(e))
        raise PipelineError(f"Pipeline failed at {stages_completed[-1] if stages_completed else 'start'}: {e}") from e


def _record_run_start(db: Database, run_id: str, document_id: str, llm_client: LLMClient) -> None:
    """Record pipeline run start in database."""
    provider = llm_client.get_provider_for_stage(PipelineStage.CALLS)
    config = llm_client.get_config(provider)
    db.execute(
        db.pipeline_runs.insert().values(
            id=run_id,
            document_id=document_id,
            pipeline_version=PIPELINE_VERSION,
            llm_model=config.model_name,
            llm_provider=provider.value,
            started_at=datetime.now(UTC).isoformat(),
            status="running",
            stages_completed="[]",
        )
    )


def _record_run_failure(
    db: Database,
    run_id: str,
    document_id: str | None,
    stages: list[str],
    elapsed: float,
    error: str,
) -> None:
    """Record pipeline run failure."""
    if document_id is None:
        return
    db.execute(
        db.pipeline_runs.update()
        .where(db.pipeline_runs.c.id == run_id)
        .values(
            completed_at=datetime.now(UTC).isoformat(),
            total_runtime_seconds=elapsed,
            status="failed",
            error_message=error[:500],
            stages_completed=json.dumps(stages),
        )
    )


def _persist_results(
    db: Database,
    result: ProcessedDocument,
    run_id: str,
    stages: list[str],
    elapsed: float,
) -> None:
    """Persist pipeline results to database atomically."""
    with db.get_connection() as conn:
        # Update pipeline run
        conn.execute(
            db.pipeline_runs.update()
            .where(db.pipeline_runs.c.id == run_id)
            .values(
                completed_at=datetime.now(UTC).isoformat(),
                total_runtime_seconds=elapsed,
                status="completed",
                stages_completed=json.dumps(stages),
            )
        )

        # Update document record
        conn.execute(
            db.documents.update()
            .where(db.documents.c.id == result.document_id)
            .values(
                title=result.profile.title,
                publication_date=result.profile.publication_date,
                as_of_date=result.profile.as_of_date,
                document_type=result.profile.document_type.value,
                overall_confidence=result.confidence.overall_confidence,
                analyst_attention_required=result.confidence.analyst_attention_required,
                status="completed",
            )
        )

        # Insert allocation calls
        for call in result.allocation_calls:
            conn.execute(
                db.allocation_calls.insert().values(
                    document_id=result.document_id,
                    asset_class_category=call.asset_class_category,
                    sub_asset_class=call.sub_asset_class,
                    call=call.call.value,
                    conviction=call.conviction.value if call.conviction else None,
                    time_horizon=call.time_horizon,
                    rationale_bullets=json.dumps(call.rationale_bullets),
                    key_indicators=json.dumps([i.model_dump() for i in call.key_indicators]),
                    key_risks=json.dumps(call.key_risks),
                    tooltip_text=call.tooltip_text,
                    citations=json.dumps([c.model_dump() for c in call.citations]),
                    confidence=call.confidence,
                    needs_analyst_review=call.needs_analyst_review,
                )
            )

        # Insert summary
        conn.execute(
            db.summaries.insert().values(
                document_id=result.document_id,
                executive_summary=result.summaries.executive_summary,
                search_descriptor=result.summaries.search_descriptor,
                key_takeaways=json.dumps([t.model_dump() for t in result.summaries.key_takeaways]),
                overall_sentiment=result.overall_sentiment.value,
                sentiment_rationale=json.dumps(result.sentiment_rationale),
                sentiment_citations=json.dumps([c.model_dump() for c in result.sentiment_citations]),
            )
        )

        # Insert tags
        for tag in result.tags.all_tags:
            conn.execute(
                db.document_tags.insert().values(
                    document_id=result.document_id,
                    tag_type=tag.tag_type.value,
                    tag_value=tag.value,
                    confidence=tag.confidence,
                )
            )

        conn.commit()


# =============================================================================
# CLI Interface
# =============================================================================


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.run",
        description="Markets Recon Pipeline - Process fund manager outlook PDFs",
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
        help="Output JSON file path (default: stdout)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PIPELINE_VERSION}",
    )
    return parser


def main() -> None:
    """CLI entrypoint for pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    # Validate PDF exists first (before loading settings)
    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    # Configure logging
    import os
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"
    try:
        configure_logging()
    except Exception:
        # Fall back to basic logging if settings fail
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    # Run pipeline
    try:
        result = asyncio.run(process_pdf(args.pdf))
    except PipelineError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    # Output result
    output_json = result.model_dump_json(indent=2)
    if args.output:
        args.output.write_text(output_json)
        print(f"Output written to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
