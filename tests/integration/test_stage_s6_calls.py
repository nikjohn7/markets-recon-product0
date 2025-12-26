"""Integration tests for Stage 6 - Call extraction."""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock

import pytest

from src.exceptions import ExtractionError
from src.llm.client import LLMProvider, ProviderConfig
from src.models.core import Citation
from src.models.enums import DocumentType
from src.models.pipeline import CandidateSet, RetrievedChunk
from src.models.profile import DocumentProfile
from src.pipeline.stages.s6_calls import stage_calls


@pytest.mark.asyncio
async def test_stage_calls_with_mock_llm(mock_llm_client):
    """Stage 6 should return structured calls with model metadata."""
    mock_llm_client.get_provider_for_stage = Mock(return_value=LLMProvider.OHMYGPT)
    mock_llm_client.get_config = Mock(
        return_value=ProviderConfig(
            base_url="http://example.com",
            model_name="test-model",
        )
    )

    profile = DocumentProfile(
        document_id="doc_calls",
        manager_name="BlackRock",
        title="Mid-Year Investment Outlook 2025",
        publication_date=date(2025, 7, 15),
        as_of_date=date(2025, 6, 30),
        document_type=DocumentType.MID_YEAR_OUTLOOK,
        asset_classes_covered=["EQUITIES", "FIXED_INCOME"],
        regions=["US", "EUROPE"],
        time_horizon="6-12 months",
        intended_audience="Institutional investors",
        citations=[Citation(chunk_id="chunk_4", page=1)],
        manager_name_uncertain=False,
        publication_date_uncertain=False,
    )

    source_text = (
        "ECB easing cycle supports duration demand. "
        "Bunds provide defensive carry in a soft landing. "
        "Lower rates improve Bund total returns. "
        "Valuations look full relative to earnings momentum. "
        "Policy easing may cushion downside risks. "
        "Stable revisions limit upside surprises. "
        "Balanced outlook with selective opportunities."
    )

    candidates = [
        RetrievedChunk(
            chunk_id="chunk_4",
            block_ids=["block_1"],
            page=4,
            text=source_text,
            score=0.9,
            section="Fixed Income",
        ),
        RetrievedChunk(
            chunk_id="chunk_6",
            block_ids=["block_2"],
            page=6,
            text=source_text,
            score=0.85,
            section="Equities",
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["block_3"],
            page=2,
            text=source_text,
            score=0.8,
            section="Overview",
        ),
    ]

    candidate_set = CandidateSet(
        document_id="doc_calls",
        candidates=candidates,
        keyword_matches={"overweight": ["block_1"]},
        total_chunks_reviewed=len(candidates),
    )

    output = await stage_calls(profile, candidate_set, llm_client=mock_llm_client)

    assert output.document_id == profile.document_id
    assert output.model_version == "test-model"
    assert len(output.allocation_calls) == 2
    assert output.sentiment_confidence == pytest.approx(0.73)


@pytest.mark.asyncio
async def test_stage_calls_requires_candidates(mock_llm_client):
    """Stage 6 should fail when no candidates are provided."""
    profile = DocumentProfile(
        document_id="doc_empty",
        manager_name="BlackRock",
        title="Outlook",
        publication_date=None,
        as_of_date=None,
        document_type=DocumentType.OTHER,
        asset_classes_covered=["EQUITIES"],
        regions=[],
        time_horizon=None,
        intended_audience=None,
        citations=[Citation(chunk_id="chunk_1", page=1)],
        manager_name_uncertain=True,
        publication_date_uncertain=True,
    )

    candidate_set = CandidateSet(
        document_id="doc_empty",
        candidates=[],
        keyword_matches={},
        total_chunks_reviewed=0,
    )

    with pytest.raises(ExtractionError, match="No candidate chunks available"):
        await stage_calls(profile, candidate_set, llm_client=mock_llm_client)
