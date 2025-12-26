"""End-to-end pipeline tests with deterministic fixtures."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import textwrap
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exceptions import PipelineError
from src.llm.client import PipelineStage
from src.models.pipeline import Chunk, RetrievedChunk
from src.pipeline import run as pipeline_run
from src.pipeline.run import process_pdf
from src.storage.blob import LocalBlobStorage
from src.storage.database import Database
from tests.fixtures.llm_responses import MOCK_LLM_RESPONSES, MOCK_SUMMARIES_RESPONSE, get_mock_llm_response

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_OUTPUT = ROOT / "tests" / "fixtures" / "expected_outputs" / "full_pipeline.json"


def _pad_text(text: str, target_length: int = 900) -> str:
    filler = " The outlook emphasizes disciplined risk management and diversification."
    padded = text
    while len(padded) < target_length:
        padded += filler
    return textwrap.fill(padded, width=80)


def _build_standard_pages() -> list[str]:
    summary = MOCK_SUMMARIES_RESPONSE["executive_summary"]
    page1 = _pad_text(
        "BlackRock is the publisher of the Mid-Year Investment Outlook 2025. "
        "Publication date 2025-07-15. As of 2025-06-30. "
        "We are overweight on select assets. "
        f"{summary}"
    )
    page2 = _pad_text(
        "Balanced outlook with selective opportunities as policy easing supports duration."
    )
    page3 = _pad_text(
        "Macro risks include inflation surprises and renewed volatility across regions."
    )
    page4 = _pad_text(
        "We are overweight German Bunds as ECB easing supports duration demand and defensive carry."
    )
    page5 = _pad_text(
        "Portfolio construction favors diversified income and steady macro resilience."
    )
    page6 = _pad_text(
        "US equities are neutral given full valuations despite resilient earnings."
    )
    return [page1, page2, page3, page4, page5, page6]


def _build_mock_llm_client(responses: dict[PipelineStage, dict[str, Any]]) -> AsyncMock:
    async def _complete_json(
        *,
        prompt: str,
        response_model: type[Any],
        stage: PipelineStage | None = None,
        provider: Any | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ) -> Any:
        if stage is None:
            raise ValueError("stage must be provided for mock LLM responses")
        response = responses[stage]
        return response_model.model_validate(response)

    client = AsyncMock()
    client.complete_json.side_effect = _complete_json
    client.get_provider_for_stage = MagicMock(return_value=MagicMock(value="mock-provider"))
    client.get_config = MagicMock(return_value=MagicMock(model_name="mock-model"))
    return client


def _patch_storage_and_db(
    monkeypatch: pytest.MonkeyPatch,
    storage: LocalBlobStorage,
    database: Database,
) -> None:
    monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
    monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)
    monkeypatch.setattr("src.pipeline.stages.s1_extract.LocalBlobStorage", lambda: storage)


def _patch_fake_index(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_build(self: Any, cleaned_doc: Any) -> None:
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
        query: str,
        top_k: int = 10,
        _filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
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

    monkeypatch.setattr("src.retrieval.indexer.DocumentIndex.build", _fake_build)
    monkeypatch.setattr("src.retrieval.indexer.DocumentIndex.query", _fake_query)


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    return value


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    normalized["document_id"] = "<document_id>"
    normalized["processing_timestamp"] = "<timestamp>"
    normalized["total_processing_time_seconds"] = 0.0

    normalized["profile"]["document_id"] = "<document_id>"
    normalized["summaries"]["document_id"] = "<document_id>"
    normalized["tags"]["document_id"] = "<document_id>"
    normalized["confidence"]["document_id"] = "<document_id>"

    normalized["tags"]["asset_class_tags"] = sorted(normalized["tags"]["asset_class_tags"])
    normalized["tags"]["instrument_tags"] = sorted(normalized["tags"]["instrument_tags"])
    normalized["tags"]["all_tags"] = sorted(
        normalized["tags"]["all_tags"],
        key=lambda tag: (tag["tag_type"], tag["value"], tag["source"]),
    )

    return _round_floats(normalized)


@pytest.fixture
def temp_storage(tmp_path: Path) -> LocalBlobStorage:
    return LocalBlobStorage(storage_dir=tmp_path / "pdfs")


@pytest.fixture
def temp_database(tmp_path: Path) -> Database:
    return Database(db_path=tmp_path / "marketsrecon_e2e.db")


@pytest.mark.asyncio
async def test_full_pipeline_golden_output(
    pdf_file_factory,
    temp_storage: LocalBlobStorage,
    temp_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = _build_standard_pages()
    pdf_path = pdf_file_factory(pages, filename="full_pipeline.pdf")

    _patch_storage_and_db(monkeypatch, temp_storage, temp_database)
    _patch_fake_index(monkeypatch)

    responses = {stage: get_mock_llm_response(stage) for stage in MOCK_LLM_RESPONSES}
    llm_client = _build_mock_llm_client(responses)

    result = await process_pdf(pdf_path, db=temp_database, llm_client=llm_client)

    expected = json.loads(EXPECTED_OUTPUT.read_text())
    actual = result.model_dump(mode="json")

    assert _normalize_payload(actual) == _normalize_payload(expected)


@pytest.mark.asyncio
async def test_pipeline_no_calls_raises(
    pdf_file_factory,
    temp_storage: LocalBlobStorage,
    temp_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = _build_standard_pages()
    pdf_path = pdf_file_factory(pages, filename="no_calls.pdf")

    _patch_storage_and_db(monkeypatch, temp_storage, temp_database)
    _patch_fake_index(monkeypatch)

    responses = {stage: get_mock_llm_response(stage) for stage in MOCK_LLM_RESPONSES}
    responses[PipelineStage.CALLS] = {
        "allocation_calls": [],
        "overall_sentiment": "NEUTRAL",
        "sentiment_rationale": ["Balanced outlook with selective opportunities."],
        "sentiment_citations": [{"chunk_id": "chunk_2", "page": 2}],
        "sentiment_confidence": 0.73,
    }
    llm_client = _build_mock_llm_client(responses)

    with pytest.raises(PipelineError, match="No asset class tags generated"):
        await process_pdf(pdf_path, db=temp_database, llm_client=llm_client)


@pytest.mark.asyncio
async def test_pipeline_low_quality_flags_attention(
    pdf_file_factory,
    temp_storage: LocalBlobStorage,
    temp_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = _build_standard_pages()
    pdf_path = pdf_file_factory(pages, filename="low_quality.pdf")

    _patch_storage_and_db(monkeypatch, temp_storage, temp_database)
    _patch_fake_index(monkeypatch)

    responses = {stage: get_mock_llm_response(stage) for stage in MOCK_LLM_RESPONSES}
    llm_client = _build_mock_llm_client(responses)

    original_stage_extract = pipeline_run.stage_extract

    async def _low_quality_extract(*args: Any, **kwargs: Any) -> Any:
        doc_json = await original_stage_extract(*args, **kwargs)
        return doc_json.model_copy(update={"extraction_coverage": 0.33})

    monkeypatch.setattr("src.pipeline.run.stage_extract", _low_quality_extract)

    result = await process_pdf(pdf_path, db=temp_database, llm_client=llm_client)

    assert result.confidence.analyst_attention_required is True
    assert "low_extraction_coverage" in result.confidence.attention_reasons
