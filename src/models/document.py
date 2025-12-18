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

        # Validate cell positions are within table dimensions
        for cell in self.cells:
            if cell.row >= self.row_count:
                raise ValueError(
                    f"Cell at row={cell.row}, col={cell.col} exceeds table row_count={self.row_count}"
                )
            if cell.col >= self.col_count:
                raise ValueError(
                    f"Cell at row={cell.row}, col={cell.col} exceeds table col_count={self.col_count}"
                )

        # Validate unique (row, col) coordinates
        seen_positions = set()
        for cell in self.cells:
            position = (cell.row, cell.col)
            if position in seen_positions:
                raise ValueError(
                    f"Duplicate cell at position (row={cell.row}, col={cell.col})"
                )
            seen_positions.add(position)

        # Validate tight bounds: row_count/col_count should match actual cell coverage
        if self.cells:
            max_row = max(cell.row for cell in self.cells)
            max_col = max(cell.col for cell in self.cells)
            if max_row >= self.row_count:
                raise ValueError(
                    f"max cell row={max_row} but row_count={self.row_count} (should be > max_row)"
                )
            if max_col >= self.col_count:
                raise ValueError(
                    f"max cell col={max_col} but col_count={self.col_count} (should be > max_col)"
                )

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
        for block in self.blocks:
            if block.page > self.page_count:
                raise ValueError(
                    f"Block {block.block_id} references page {block.page} "
                    f"but document only has {self.page_count} pages"
                )
        for table in self.tables:
            if table.page > self.page_count:
                raise ValueError(
                    f"Table {table.table_id} references page {table.page} "
                    f"but document only has {self.page_count} pages"
                )

        # Validate unique block_id values
        block_ids = [block.block_id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            duplicates = [bid for bid in block_ids if block_ids.count(bid) > 1]
            raise ValueError(f"Duplicate block_id found: {duplicates[0]}")

        # Validate unique table_id values
        table_ids = [table.table_id for table in self.tables]
        if len(table_ids) != len(set(table_ids)):
            duplicates = [tid for tid in table_ids if table_ids.count(tid) > 1]
            raise ValueError(f"Duplicate table_id found: {duplicates[0]}")

        return self
