"""Pipeline stage I/O models.

Models for inter-stage communication so stages don't pass raw dicts.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    cleaned_blocks: list[str] = Field(..., description="Block IDs after cleaning")
    sections: list[Section]
    removed_block_ids: list[str] = Field(
        default_factory=list, description="Blocks removed as boilerplate"
    )


class RetrievedChunk(BaseModel):
    """A chunk retrieved from the vector index."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    text: str
    block_ids: list[str] = Field(..., description="Source block IDs")
    page: int = Field(..., ge=1)
    score: float = Field(..., ge=0, le=1, description="Retrieval similarity score")


class CandidateSet(BaseModel):
    """Output of Stage 5: Candidate passages for extraction."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    chunks: list[RetrievedChunk] = Field(..., description="Candidate chunks for LLM")
    query_terms: list[str] = Field(
        default_factory=list, description="Terms used for retrieval"
    )
