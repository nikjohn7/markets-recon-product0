#!/usr/bin/env python
"""MVP evaluation script for Markets Recon Pipeline.

Runs the full pipeline on test PDFs and measures against MVP success metrics:
- PDFs processed without crash: >= 90%
- Calls extracted per PDF (avg): >= 3
- Citations present per call: 100%
- Processing time per PDF: < 3 min

Usage:
    # Run with mock LLM (deterministic, no API calls)
    python scripts/evaluate_mvp.py --mock

    # Run with real LLM (requires API keys)
    python scripts/evaluate_mvp.py --pdf-dir tests/fixtures/pdfs/

    # Run on specific PDFs
    python scripts/evaluate_mvp.py --pdf document1.pdf --pdf document2.pdf

    # Generate test PDFs and run evaluation
    python scripts/evaluate_mvp.py --generate 5 --mock
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fitz

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exceptions import PipelineError
from src.llm.client import PipelineStage  # noqa: TC002
from src.models.output import ProcessedDocument  # noqa: TC002
from src.pipeline.run import process_pdf
from src.storage.blob import LocalBlobStorage
from src.storage.database import Database
from tests.fixtures.llm_responses import get_mock_llm_response

# MVP Success Metrics Thresholds
MVP_CRASH_THRESHOLD = 0.90  # >= 90% success rate
MVP_CALLS_THRESHOLD = 3  # >= 3 calls per PDF average
MVP_CITATION_THRESHOLD = 1.00  # 100% calls with citations
MVP_TIME_THRESHOLD = 180.0  # < 3 minutes per PDF


@dataclass
class PDFResult:
    """Result of processing a single PDF."""

    pdf_path: str
    success: bool
    processing_time: float
    num_calls: int = 0
    calls_with_citations: int = 0
    total_citations: int = 0
    error: str | None = None
    document_id: str | None = None
    confidence_score: float = 0.0
    confidence_band: str = ""


def _percentile(values: list[float], pct: float) -> float:
    """Compute percentile of a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = (len(sorted_values) - 1) * pct / 100
    lower = int(idx)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = idx - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


@dataclass
class EvaluationMetrics:
    """Aggregated MVP evaluation metrics."""

    total_pdfs: int = 0
    successful_pdfs: int = 0
    failed_pdfs: int = 0
    total_calls: int = 0
    calls_with_citations: int = 0
    total_citations: int = 0
    total_time: float = 0.0
    results: list[PDFResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Percentage of PDFs processed without crash."""
        return self.successful_pdfs / self.total_pdfs if self.total_pdfs > 0 else 0.0

    @property
    def avg_calls_per_pdf(self) -> float:
        """Average calls extracted per PDF."""
        return self.total_calls / self.successful_pdfs if self.successful_pdfs > 0 else 0.0

    @property
    def citation_rate(self) -> float:
        """Percentage of calls with citations."""
        return self.calls_with_citations / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def avg_processing_time(self) -> float:
        """Average processing time per PDF in seconds."""
        return self.total_time / self.successful_pdfs if self.successful_pdfs > 0 else 0.0

    @property
    def processing_times(self) -> list[float]:
        """List of processing times for successful PDFs."""
        return [r.processing_time for r in self.results if r.success]

    @property
    def p50_processing_time(self) -> float:
        """Median (p50) processing time."""
        return _percentile(self.processing_times, 50)

    @property
    def p95_processing_time(self) -> float:
        """95th percentile processing time."""
        return _percentile(self.processing_times, 95)

    def passes_mvp(self) -> tuple[bool, list[str]]:
        """Check if all MVP criteria are met. Returns (passed, failures)."""
        failures = []
        if self.success_rate < MVP_CRASH_THRESHOLD:
            failures.append(f"Success rate {self.success_rate:.1%} < {MVP_CRASH_THRESHOLD:.0%}")
        if self.avg_calls_per_pdf < MVP_CALLS_THRESHOLD:
            failures.append(f"Avg calls/PDF {self.avg_calls_per_pdf:.1f} < {MVP_CALLS_THRESHOLD}")
        if self.citation_rate < MVP_CITATION_THRESHOLD:
            failures.append(
                f"Citation rate {self.citation_rate:.1%} < {MVP_CITATION_THRESHOLD:.0%}"
            )
        if self.avg_processing_time >= MVP_TIME_THRESHOLD:
            failures.append(
                f"Avg time {self.avg_processing_time:.1f}s >= {MVP_TIME_THRESHOLD:.0f}s"
            )
        return len(failures) == 0, failures

    def to_json(self) -> dict[str, Any]:
        """Return machine-readable JSON summary of metrics."""
        passed, failures = self.passes_mvp()
        return {
            "summary": {
                "total_pdfs": self.total_pdfs,
                "successful_pdfs": self.successful_pdfs,
                "failed_pdfs": self.failed_pdfs,
                "total_calls": self.total_calls,
                "calls_with_citations": self.calls_with_citations,
                "total_citations": self.total_citations,
            },
            "metrics": {
                "success_rate": round(self.success_rate, 4),
                "avg_calls_per_pdf": round(self.avg_calls_per_pdf, 2),
                "citation_rate": round(self.citation_rate, 4),
                "processing_time": {
                    "avg_seconds": round(self.avg_processing_time, 2),
                    "p50_seconds": round(self.p50_processing_time, 2),
                    "p95_seconds": round(self.p95_processing_time, 2),
                },
            },
            "thresholds": {
                "success_rate": MVP_CRASH_THRESHOLD,
                "avg_calls_per_pdf": MVP_CALLS_THRESHOLD,
                "citation_rate": MVP_CITATION_THRESHOLD,
                "max_processing_time_seconds": MVP_TIME_THRESHOLD,
            },
            "mvp_passed": passed,
            "failures": failures,
            "per_pdf_results": [
                {
                    "pdf": r.pdf_path,
                    "success": r.success,
                    "processing_time": round(r.processing_time, 2),
                    "num_calls": r.num_calls,
                    "calls_with_citations": r.calls_with_citations,
                    "confidence_score": round(r.confidence_score, 2) if r.success else None,
                    "confidence_band": r.confidence_band if r.success else None,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def create_mock_llm_client() -> AsyncMock:
    """Create a mock LLM client for deterministic testing."""

    async def _complete_json(
        *,
        prompt: str,  # noqa: ARG001
        response_model: type[Any],
        stage: PipelineStage | None = None,
        provider: Any | None = None,  # noqa: ARG001
        max_tokens: int | None = None,  # noqa: ARG001
        temperature: float | None = None,  # noqa: ARG001
        system_prompt: str | None = None,  # noqa: ARG001
    ) -> Any:
        if stage is None:
            raise ValueError("stage must be provided for mock LLM responses")
        response = get_mock_llm_response(stage)
        return response_model.model_validate(response)

    client = AsyncMock()
    client.complete_json.side_effect = _complete_json
    client.get_provider_for_stage = MagicMock(return_value=MagicMock(value="mock-provider"))
    client.get_config = MagicMock(return_value=MagicMock(model_name="mock-model"))
    return client


def generate_test_pdf(output_path: Path, variant: int = 0) -> None:
    """Generate a test PDF with asset management content."""
    summaries = [
        "We are overweight European sovereign duration as ECB easing supports demand.",
        "US equities are held at neutral due to full valuations despite stable earnings.",
        "Emerging market debt offers attractive yields with improving fundamentals.",
        "Credit spreads remain tight but high yield offers selective opportunities.",
        "Commodities are underweight as supply dynamics weigh on prices.",
    ]
    executive = summaries[variant % len(summaries)]

    pages = []

    # Page 1: Title and metadata
    # Note: Date must match MOCK_METADATA_RESPONSE for hallucination check to pass
    page1 = textwrap.fill(
        f"BlackRock Mid-Year Investment Outlook 2025. "
        f"Publication date 2025-07-15. As of 2025-06-30. "
        f"Asset classes covered: Equities, Fixed Income, Commodities. "
        f"Regions: US, Europe, Emerging Markets. "
        f"{executive} " * 3,
        width=80,
    )
    pages.append(page1)

    # Page 2: Macro outlook
    page2 = textwrap.fill(
        "The macro environment suggests a soft landing as inflation moderates. "
        "Central bank policy is pivoting toward easing with rate cuts expected. "
        "Growth remains resilient in developed markets while emerging economies accelerate. "
        "Balanced outlook with selective opportunities across asset classes. " * 3,
        width=80,
    )
    pages.append(page2)

    # Page 3: Fixed income views
    page3 = textwrap.fill(
        "We are overweight German Bunds as ECB easing supports duration demand. "
        "European sovereign duration provides defensive carry and diversification. "
        "Investment grade credit offers steady income with manageable risk. "
        "Key indicators: ECB policy rate falling, inflation expectations stable. " * 3,
        width=80,
    )
    pages.append(page3)

    # Page 4: Equity views
    page4 = textwrap.fill(
        "US equities are neutral given full valuations despite resilient earnings. "
        "European equities offer value with improving earnings momentum. "
        "Emerging market equities are overweight on China reopening tailwinds. "
        "Sector preferences: Technology, Healthcare, Financials. " * 3,
        width=80,
    )
    pages.append(page4)

    # Page 5: Risks
    page5 = textwrap.fill(
        "Key risks include inflation reacceleration and renewed volatility. "
        "Geopolitical tensions could disrupt supply chains and energy markets. "
        "Credit spread widening remains a tail risk if growth disappoints. "
        "Duration risk requires careful management as rate paths diverge. " * 3,
        width=80,
    )
    pages.append(page5)

    # Page 6: Commodities (variant-specific)
    if variant % 2 == 0:
        page6 = textwrap.fill(
            "We are underweight commodities as supply dynamics weigh on prices. "
            "Gold offers portfolio insurance against tail risks. "
            "Energy markets face headwinds from slowing demand growth. " * 3,
            width=80,
        )
    else:
        page6 = textwrap.fill(
            "We are overweight commodities on supply constraints and inflation hedging. "
            "Oil prices should remain supported by OPEC discipline. "
            "Industrial metals benefit from green transition demand. " * 3,
            width=80,
        )
    pages.append(page6)

    # Create PDF
    doc = fitz.open()
    try:
        for page_text in pages:
            page = doc.new_page()
            page.insert_text((72, 72), page_text)
        doc.save(str(output_path))
    finally:
        doc.close()


def _patch_storage_and_db(
    storage: LocalBlobStorage,
    database: Database,
) -> None:
    """Monkey-patch storage and database modules to use shared instances."""
    import src.pipeline.stages.s0_ingest as s0_ingest
    import src.pipeline.stages.s1_extract as s1_extract

    s0_ingest.LocalBlobStorage = lambda: storage  # type: ignore[misc]
    s0_ingest.Database = lambda: database  # type: ignore[misc]
    s1_extract.LocalBlobStorage = lambda: storage  # type: ignore[misc]


def _patch_fake_index() -> None:
    """Patch the document index to use a fake in-memory implementation."""
    from src.models.pipeline import Chunk, RetrievedChunk
    from src.retrieval import indexer

    async def _fake_build(self: Any, cleaned_doc: Any) -> None:
        """Build a fake index from document blocks."""
        blocks_by_page: dict[int, list[Any]] = {}
        for block in cleaned_doc.blocks:
            blocks_by_page.setdefault(block.page, []).append(block)

        chunks: list[Chunk] = []
        for page in sorted(blocks_by_page):
            page_blocks = blocks_by_page[page]
            page_text = " ".join(" ".join(block.text.split()) for block in page_blocks)
            chunks.append(
                Chunk(
                    chunk_id=f"chunk_{page}",
                    block_ids=[block.block_id for block in page_blocks],
                    page=page,
                    text=page_text,
                    section=None,
                )
            )
        self.chunks = chunks

    async def _fake_query(
        self: Any,
        query: str,  # noqa: ARG001
        top_k: int = 10,
        _filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Return fake query results from all chunks."""
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                block_ids=chunk.block_ids,
                page=chunk.page,
                text=chunk.text,
                score=0.9,
                section=chunk.section,
            )
            for chunk in self.chunks[:top_k]
        ]

    indexer.DocumentIndex.build = _fake_build  # type: ignore[method-assign]
    indexer.DocumentIndex.query = _fake_query  # type: ignore[method-assign]


async def process_single_pdf(
    pdf_path: Path,
    use_mock: bool,
    temp_dir: Path,
) -> PDFResult:
    """Process a single PDF and return results."""
    result = PDFResult(pdf_path=str(pdf_path), success=False, processing_time=0.0)
    start_time = time.monotonic()

    try:
        # Set up shared storage and database instances
        storage = LocalBlobStorage(storage_dir=temp_dir / "pdfs")
        db = Database(db_path=temp_dir / "eval.db")

        # Patch modules to use shared instances
        _patch_storage_and_db(storage, db)

        # When using mock LLM, also use fake index (no OpenAI embeddings)
        if use_mock:
            _patch_fake_index()

        llm_client = create_mock_llm_client() if use_mock else None

        # Process the PDF
        output: ProcessedDocument = await process_pdf(
            pdf_path,
            db=db,
            llm_client=llm_client,
        )

        result.success = True
        result.document_id = output.document_id
        result.num_calls = len(output.allocation_calls)
        result.confidence_score = output.confidence.overall_confidence
        result.confidence_band = output.confidence.confidence_band.value

        # Count citations
        for call in output.allocation_calls:
            if call.citations:
                result.calls_with_citations += 1
                result.total_citations += len(call.citations)

    except PipelineError as e:
        result.error = f"Pipeline error: {e}"
    except FileNotFoundError as e:
        result.error = f"File not found: {e}"
    except Exception as e:
        result.error = f"Unexpected error: {type(e).__name__}: {e}"

    result.processing_time = time.monotonic() - start_time
    return result


async def run_evaluation(
    pdf_paths: list[Path],
    use_mock: bool,
    temp_dir: Path,
) -> EvaluationMetrics:
    """Run evaluation on all PDFs and collect metrics."""
    metrics = EvaluationMetrics()

    for pdf_path in pdf_paths:
        print(f"Processing: {pdf_path.name}...", end=" ", flush=True)
        result = await process_single_pdf(pdf_path, use_mock, temp_dir)
        metrics.results.append(result)
        metrics.total_pdfs += 1

        if result.success:
            metrics.successful_pdfs += 1
            metrics.total_calls += result.num_calls
            metrics.calls_with_citations += result.calls_with_citations
            metrics.total_citations += result.total_citations
            metrics.total_time += result.processing_time
            print(
                f"OK ({result.num_calls} calls, {result.processing_time:.1f}s, "
                f"{result.confidence_band})"
            )
        else:
            metrics.failed_pdfs += 1
            print(f"FAILED: {result.error}")

    return metrics


def print_results(metrics: EvaluationMetrics) -> None:
    """Print evaluation results and MVP assessment."""
    print("\n" + "=" * 70)
    print("  MVP EVALUATION RESULTS")
    print("=" * 70)

    # Summary stats
    print(f"\nPDFs Processed: {metrics.total_pdfs}")
    print(f"  Successful:   {metrics.successful_pdfs}")
    print(f"  Failed:       {metrics.failed_pdfs}")

    print(f"\nTotal Calls Extracted: {metrics.total_calls}")
    print(f"  With Citations:      {metrics.calls_with_citations}")
    print(f"  Total Citations:     {metrics.total_citations}")

    print(f"\nTotal Processing Time: {metrics.total_time:.1f}s")

    # MVP Metrics
    print("\n" + "-" * 70)
    print("  MVP SUCCESS METRICS")
    print("-" * 70)

    # Success rate
    status = "PASS" if metrics.success_rate >= MVP_CRASH_THRESHOLD else "FAIL"
    print(
        f"\n[{status}] PDFs without crash:     {metrics.success_rate:.1%} "
        f"(target: >= {MVP_CRASH_THRESHOLD:.0%})"
    )

    # Calls per PDF
    status = "PASS" if metrics.avg_calls_per_pdf >= MVP_CALLS_THRESHOLD else "FAIL"
    print(
        f"[{status}] Avg calls per PDF:     {metrics.avg_calls_per_pdf:.1f} "
        f"(target: >= {MVP_CALLS_THRESHOLD})"
    )

    # Citation rate
    status = "PASS" if metrics.citation_rate >= MVP_CITATION_THRESHOLD else "FAIL"
    print(
        f"[{status}] Citation rate:         {metrics.citation_rate:.1%} "
        f"(target: {MVP_CITATION_THRESHOLD:.0%})"
    )

    # Processing time
    status = "PASS" if metrics.avg_processing_time < MVP_TIME_THRESHOLD else "FAIL"
    print(
        f"[{status}] Avg processing time:   {metrics.avg_processing_time:.1f}s "
        f"(target: < {MVP_TIME_THRESHOLD:.0f}s)"
    )
    print(f"      p50: {metrics.p50_processing_time:.2f}s  p95: {metrics.p95_processing_time:.2f}s")

    # Overall assessment
    passed, failures = metrics.passes_mvp()
    print("\n" + "=" * 70)
    if passed:
        print("  MVP CRITERIA: ALL PASSED")
    else:
        print("  MVP CRITERIA: FAILED")
        for failure in failures:
            print(f"    - {failure}")
    print("=" * 70)

    # Per-PDF details
    if metrics.results:
        print("\n--- Per-PDF Results ---")
        for result in metrics.results:
            pdf_name = Path(result.pdf_path).name
            if result.success:
                print(
                    f"  {pdf_name}: {result.num_calls} calls, "
                    f"{result.total_citations} citations, "
                    f"{result.processing_time:.1f}s, "
                    f"confidence={result.confidence_score:.2f} ({result.confidence_band})"
                )
            else:
                print(f"  {pdf_name}: FAILED - {result.error}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MVP evaluation script for Markets Recon Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock LLM (no API calls required)
    python scripts/evaluate_mvp.py --mock

    # Generate test PDFs and evaluate with mock
    python scripts/evaluate_mvp.py --generate 5 --mock

    # Evaluate specific PDFs with real LLM
    python scripts/evaluate_mvp.py --pdf doc1.pdf --pdf doc2.pdf

    # Evaluate all PDFs in a directory
    python scripts/evaluate_mvp.py --pdf-dir ./pdfs/
        """,
    )

    parser.add_argument(
        "--pdf",
        type=Path,
        action="append",
        default=[],
        help="Path to PDF file (can be repeated)",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        help="Directory containing PDFs to evaluate",
    )
    parser.add_argument(
        "--generate",
        type=int,
        metavar="N",
        help="Generate N test PDFs for evaluation",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM responses (no API calls)",
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=Path("/tmp/marketsrecon_eval"),
        help="Temporary directory for storage (default: /tmp/marketsrecon_eval)",
    )
    parser.add_argument(
        "--json-output",
        "-j",
        type=Path,
        help="Write machine-readable JSON summary to file",
    )

    args = parser.parse_args()

    # Collect PDF paths
    pdf_paths: list[Path] = list(args.pdf)

    if args.pdf_dir:
        if args.pdf_dir.is_dir():
            pdf_paths.extend(args.pdf_dir.glob("*.pdf"))
        else:
            print(f"Error: Directory not found: {args.pdf_dir}", file=sys.stderr)
            sys.exit(1)

    # Generate test PDFs if requested
    if args.generate:
        args.temp_dir.mkdir(parents=True, exist_ok=True)
        gen_dir = args.temp_dir / "generated_pdfs"
        gen_dir.mkdir(exist_ok=True)

        print(f"Generating {args.generate} test PDFs...")
        for i in range(args.generate):
            pdf_path = gen_dir / f"test_outlook_{i + 1}.pdf"
            generate_test_pdf(pdf_path, variant=i)
            pdf_paths.append(pdf_path)
            print(f"  Created: {pdf_path.name}")

    # Validate inputs
    if not pdf_paths:
        print("Error: No PDFs specified. Use --pdf, --pdf-dir, or --generate.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Validate PDF existence
    missing = [p for p in pdf_paths if not p.exists()]
    if missing:
        print("Error: PDFs not found:", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        sys.exit(1)

    # Set up temp directory
    args.temp_dir.mkdir(parents=True, exist_ok=True)

    # Run evaluation
    print(f"\nEvaluating {len(pdf_paths)} PDF(s)...")
    print(f"Mode: {'Mock LLM' if args.mock else 'Real LLM'}")
    print("-" * 70)

    metrics = asyncio.run(run_evaluation(pdf_paths, args.mock, args.temp_dir))

    # Print results
    print_results(metrics)

    # Write JSON output if requested
    if args.json_output:
        json_data = metrics.to_json()
        args.json_output.write_text(json.dumps(json_data, indent=2))
        print(f"\nJSON summary written to: {args.json_output}")

    # Exit with appropriate code
    passed, _ = metrics.passes_mvp()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
