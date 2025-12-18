"""Document extraction models.

Models for representing extracted PDF content: blocks, tables, and full documents.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.core import BoundingBox
from models.enums import BlockType


class DocumentBlock(BaseModel):
    """Single block of content from PDF."""

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(..., description="Stable ID: {page}_{index}")
    page: int = Field(..., ge=1)
    text: str
    block_type: BlockType
    bbox: BoundingBox | None = None
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")


class TableCell(BaseModel):
    """Single cell in an extracted table."""

    model_config = ConfigDict(extra="forbid")

    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)
    text: str
    is_header: bool = False


class ExtractedTable(BaseModel):
    """Structured table from PDF."""

    model_config = ConfigDict(extra="forbid")

    table_id: str
    page: int = Field(..., ge=1)
    cells: list[TableCell]
    row_count: int = Field(..., ge=0)
    col_count: int = Field(..., ge=0)
    caption: str | None = None

    @model_validator(mode="after")
    def check_counts_with_cells(self) -> "ExtractedTable":
        if self.cells and (self.row_count == 0 or self.col_count == 0):
            raise ValueError("row_count and col_count must be > 0 when cells exist")
        return self


class DocumentJSON(BaseModel):
    """Full extracted document structure."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    blob_id: str
    file_hash: str
    blocks: list[DocumentBlock]
    tables: list[ExtractedTable]
    page_count: int = Field(..., ge=1)
    extraction_coverage: float = Field(
        ..., ge=0, le=1, description="% pages with text"
    )
    ocr_pages: list[int] = Field(
        default_factory=list, description="Pages that required OCR"
    )
    vision_pages: list[int] = Field(
        default_factory=list, description="Pages processed with vision"
    )

    @model_validator(mode="after")
    def check_page_bounds(self) -> "DocumentJSON":
        for p in self.ocr_pages:
            if p < 1 or p > self.page_count:
                raise ValueError(f"ocr_pages contains invalid page {p}")
        for p in self.vision_pages:
            if p < 1 or p > self.page_count:
                raise ValueError(f"vision_pages contains invalid page {p}")
        return self
