"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import fitz
import pytest

from tests.fixtures.llm_responses import MOCK_LLM_RESPONSES, MockLLMResponse, get_mock_llm_response

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from pydantic import BaseModel
    from src.llm.client import LLMProvider, PipelineStage

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def sample_document_id() -> str:
    """Return a sample document ID for testing."""
    return "doc_test_12345678"


@pytest.fixture
def pdf_bytes_factory() -> Callable[[Iterable[str]], bytes]:
    """Create deterministic PDF bytes from a list of page strings."""

    def _factory(pages: Iterable[str]) -> bytes:
        doc = fitz.open()
        try:
            for page_text in pages:
                page = doc.new_page()
                page.insert_text((72, 72), page_text)
            return doc.write()
        finally:
            doc.close()

    return _factory


@pytest.fixture
def sample_pdf_bytes(pdf_bytes_factory: Callable[[Iterable[str]], bytes]) -> bytes:
    """Return a small, deterministic PDF payload for tests."""
    return pdf_bytes_factory(["Sample page one", "Sample page two"])


@pytest.fixture
def pdf_file_factory(
    tmp_path: Path, pdf_bytes_factory: Callable[[Iterable[str]], bytes]
) -> Callable[[Iterable[str], str], Path]:
    """Write deterministic PDFs to disk for tests that need file paths."""

    def _factory(pages: Iterable[str], filename: str = "sample.pdf") -> Path:
        pdf_path = tmp_path / filename
        pdf_path.write_bytes(pdf_bytes_factory(pages))
        return pdf_path

    return _factory


@pytest.fixture
def mock_llm_responses() -> dict[PipelineStage, MockLLMResponse]:
    """Provide a fresh copy of all mock LLM responses keyed by stage."""
    return {stage: get_mock_llm_response(stage) for stage in MOCK_LLM_RESPONSES}


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """Return a mock LLM client that validates against response models."""

    async def _complete_json(
        *,
        prompt: str,  # noqa: ARG001
        response_model: type[BaseModel],
        stage: PipelineStage | None = None,
        provider: LLMProvider | None = None,  # noqa: ARG001
        max_tokens: int | None = None,  # noqa: ARG001
        temperature: float | None = None,  # noqa: ARG001
        system_prompt: str | None = None,  # noqa: ARG001
    ) -> BaseModel:
        if stage is None:
            raise ValueError("stage must be provided for mock LLM responses")
        response = get_mock_llm_response(stage)
        return response_model.model_validate(response)

    client = AsyncMock()
    client.complete_json.side_effect = _complete_json
    return client
