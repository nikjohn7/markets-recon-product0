"""Pipeline stage I/O models.

Models for inter-stage communication so stages don't pass raw dicts.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.models.document import DocumentBlock


class IngestResult(BaseModel):
    """Output of Stage 0: Ingest."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    blob_id: str
    file_hash: str
    is_duplicate: bool
    source_metadata: dict[str, Any]


class Section(BaseModel):
    """A detected section within a document."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., description="Unique identifier: {doc_id}_sec_{index}")
    title: str | None = Field(None, description="Section heading text, if detected")
    start_block_id: str
    end_block_id: str
    section_type: str | None = Field(
        None, description="Classification: macro, equities, fixed_income, risks, appendix, other"
    )


class CleanedDocument(BaseModel):
    """Output of Stage 2: Cleaned document with sections detected."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    blocks: list[DocumentBlock] = Field(..., description="Cleaned blocks")
    sections: list[Section]
    removed_boilerplate_count: int = Field(..., ge=0)
    disclaimer_block_id: str | None = None


class RetrievedChunk(BaseModel):
    """A chunk retrieved from the vector index."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Unique: {doc_id}_{chunk_index}")
    block_ids: list[str] = Field(..., description="Source block IDs")
    page: int = Field(..., ge=1, description="Page of first block")
    text: str
    score: float
    section: str | None = None


class CandidateSet(BaseModel):
    """Output of Stage 5: Candidate passages for extraction."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    candidates: list[RetrievedChunk]
    keyword_matches: dict[str, list[str]] = Field(
        default_factory=dict, description="keyword → block_ids"
    )
    total_chunks_reviewed: int = Field(..., ge=0)
