"""Tests for shared LLM fixtures."""

from __future__ import annotations

import pytest

from src.llm.client import PipelineStage
from src.pipeline.stages.s4_metadata import DocumentProfileLLM
from src.pipeline.stages.s5_candidates import ExpansionOutput
from src.pipeline.stages.s6_calls import CallExtractionLLM
from src.pipeline.stages.s7_summaries import SummaryGenerationLLM
from src.pipeline.stages.s8_tooltips import TooltipGenerationLLM
from src.pipeline.stages.s9_tags import TagGenerationLLM
from tests.fixtures.llm_responses import get_mock_llm_response


def test_mock_llm_responses_validate() -> None:
    """Ensure mock responses match the stage-level schemas."""
    DocumentProfileLLM.model_validate(get_mock_llm_response(PipelineStage.METADATA))
    ExpansionOutput.model_validate(get_mock_llm_response(PipelineStage.CANDIDATES))
    CallExtractionLLM.model_validate(get_mock_llm_response(PipelineStage.CALLS))
    SummaryGenerationLLM.model_validate(get_mock_llm_response(PipelineStage.SUMMARIES))
    TooltipGenerationLLM.model_validate(get_mock_llm_response(PipelineStage.TOOLTIPS))
    TagGenerationLLM.model_validate(get_mock_llm_response(PipelineStage.TAGS))


@pytest.mark.asyncio
async def test_mock_llm_client_returns_valid_models(mock_llm_client) -> None:
    """Mock LLM client should return validated Pydantic models."""
    result = await mock_llm_client.complete_json(
        prompt="test",
        response_model=DocumentProfileLLM,
        stage=PipelineStage.METADATA,
    )
    assert isinstance(result, DocumentProfileLLM)
