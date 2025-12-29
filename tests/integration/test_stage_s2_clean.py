"""Integration tests for Stage 2 - Clean."""

from __future__ import annotations

import pytest
from src.models.document import DocumentBlock, DocumentJSON
from src.models.enums import BlockType
from src.models.pipeline import CleanedDocument, Section
from src.pipeline.stages.s2_clean import stage_clean
from src.retrieval.indexer import chunk_document


@pytest.mark.asyncio
async def test_stage_clean_removes_boilerplate_and_flags_disclaimer():
    """Stage 2 should normalize text, remove boilerplate, and detect disclaimers."""
    blocks = [
        DocumentBlock(
            block_id="1_0",
            page=1,
            text="Confidential",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_1",
            page=1,
            text="Macro Outlook",
            block_type=BlockType.HEADING,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_2",
            page=1,
            text="We expect invest-\nment growth to cool.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_3",
            page=1,
            text="This document is for informational purposes only.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="2_0",
            page=2,
            text="Confidential",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="2_1",
            page=2,
            text="Equities",
            block_type=BlockType.HEADING,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="2_2",
            page=2,
            text="We prefer US equities.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="3_0",
            page=3,
            text="Confidential",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="3_1",
            page=3,
            text="Fixed Income",
            block_type=BlockType.HEADING,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="3_2",
            page=3,
            text="We are overweight duration.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
    ]

    doc_json = DocumentJSON(
        document_id="doc_clean",
        blob_id="blob123",
        file_hash="hash123",
        blocks=blocks,
        tables=[],
        page_count=3,
        extraction_coverage=1.0,
        ocr_pages=[],
        vision_pages=[],
    )

    cleaned = await stage_clean(doc_json)

    assert cleaned.removed_boilerplate_count == 2
    assert cleaned.disclaimer_block_id == "1_0"
    assert "2_0" not in {block.block_id for block in cleaned.blocks}
    assert "3_0" not in {block.block_id for block in cleaned.blocks}

    normalized_text = next(block.text for block in cleaned.blocks if block.block_id == "1_2")
    assert "investment" in normalized_text

    disclaimer_block = next(block for block in cleaned.blocks if block.block_id == "1_3")
    assert disclaimer_block.block_type == BlockType.DISCLAIMER

    section_types = {section.section_type for section in cleaned.sections}
    assert "macro" in section_types


@pytest.mark.asyncio
async def test_stage_clean_page_triage_reduces_downstream_chunks_for_large_docs():
    """Stage 2 triage should reduce Stage 3 chunking workload on large documents."""
    long_text = ("We are overweight equities and underweight duration. " * 100).strip()
    blocks = [
        DocumentBlock(
            block_id=f"{page}_0",
            page=page,
            text=f"Page {page}: {long_text}",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        )
        for page in range(1, 51)
    ]

    doc_json = DocumentJSON(
        document_id="triage_chunk_doc",
        blob_id="blob123",
        file_hash="hash123",
        blocks=blocks,
        tables=[],
        page_count=50,
        extraction_coverage=1.0,
        ocr_pages=[],
        vision_pages=[],
    )

    triaged = await stage_clean(doc_json)
    triaged_chunks = chunk_document(triaged)

    baseline = CleanedDocument(
        document_id="triage_chunk_doc_baseline",
        blocks=blocks,
        sections=[
            Section(
                section_id="triage_chunk_doc_baseline_sec_0",
                title=None,
                start_block_id=blocks[0].block_id,
                end_block_id=blocks[-1].block_id,
                section_type=None,
            )
        ],
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )
    baseline_chunks = chunk_document(baseline)

    assert len(triaged.blocks) < len(baseline.blocks)
    assert len(triaged_chunks) < len(baseline_chunks)
