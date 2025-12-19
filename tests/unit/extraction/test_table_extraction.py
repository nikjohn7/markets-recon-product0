"""Unit tests for table extraction functionality."""

from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
from src.extraction.parser import PDFParser, parse_pdf
from src.models.document import DocumentJSON, ExtractedTable
from src.models.enums import BlockType


class TestTableExtraction:
    """Unit tests for table extraction from PDFs."""

    def create_test_pdf_with_table(self) -> bytes:
        """Create a test PDF with a simple table programmatically."""
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)  # Standard US Letter

        # Create table data
        table_data = [
            ["Product", "Price", "Quantity"],  # Header row
            ["Apple", "1.20", "50"],
            ["Banana", "0.80", "30"],
            ["Orange", "1.50", "25"],
        ]

        # Table positioning
        start_x = 100
        start_y = 200
        col_widths = [150, 100, 100]  # Different widths for each column
        row_height = 30

        # Draw table cells
        for row_idx, row in enumerate(table_data):
            y = start_y + (row_idx * row_height)
            x = start_x

            for col_idx, cell_text in enumerate(row):
                # Draw cell text
                page.insert_text(
                    (x + 5, y + 20),  # Small padding within cell
                    cell_text,
                    fontsize=12,
                )

                # Draw cell border
                rect = fitz.Rect(x, y, x + col_widths[col_idx], y + row_height)
                page.draw_rect(rect, color=(0, 0, 0), width=1)

                x += col_widths[col_idx]

        # Add some regular text above and below the table
        page.insert_text((50, 100), "Investment Portfolio Summary", fontsize=16)
        page.insert_text((50, 350), "This table shows our current holdings.", fontsize=11)

        pdf_bytes = doc.write()
        doc.close()
        return pdf_bytes

    @patch("pdfplumber.open")
    def test_table_extraction_detects_table(self, mock_pdfplumber_open):
        """Test that table extraction detects tables in PDF."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["Product", "Price", "Quantity"], ["Apple", "1.20", "50"], ["Banana", "0.80", "30"]]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        # Should have extracted at least one table
        assert len(result.tables) > 0

        # Find the table (should be the first/only one)
        table = result.tables[0]
        assert isinstance(table, ExtractedTable)

        # Verify table has correct structure
        assert table.row_count == 3  # 3 rows of data
        assert table.col_count == 3  # 3 columns

        # Verify table ID format
        assert table.table_id.startswith("1_tbl_")  # Page 1, table index

    @patch("pdfplumber.open")
    def test_table_extraction_cell_positions(self, mock_pdfplumber_open):
        """Test that cells are extracted with correct row/col positions (0-indexed)."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Check that we have cells
        assert len(table.cells) > 0

        # Verify cell positions are 0-indexed and within bounds
        for cell in table.cells:
            assert cell.row >= 0
            assert cell.col >= 0
            assert cell.row < table.row_count
            assert cell.col < table.col_count

        # Check for expected header cells (first row)
        header_cells = [c for c in table.cells if c.row == 0]
        assert len(header_cells) == 3  # 3 header cells

        # Check for expected data cells
        data_cells = [c for c in table.cells if c.row > 0]
        assert len(data_cells) == 9  # 3 rows × 3 columns = 9 data cells

    @patch("pdfplumber.open")
    def test_table_extraction_header_detection(self, mock_pdfplumber_open):
        """Test that header rows are correctly identified."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Check that first row cells are marked as headers
        header_cells = [c for c in table.cells if c.row == 0]
        for cell in header_cells:
            assert cell.is_header is True

        # Check that non-first row cells are not marked as headers
        data_cells = [c for c in table.cells if c.row > 0]
        for cell in data_cells:
            assert cell.is_header is False

    @patch("pdfplumber.open")
    def test_table_extraction_cell_text_content(self, mock_pdfplumber_open):
        """Test that cell text content is correctly extracted."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Create a mapping of cell positions to text for easy lookup
        cell_map = {(cell.row, cell.col): cell.text for cell in table.cells}

        # Check header row
        assert cell_map[(0, 0)] == "Product"
        assert cell_map[(0, 1)] == "Price"
        assert cell_map[(0, 2)] == "Quantity"

        # Check some data cells
        assert "Apple" in cell_map[(1, 0)]
        assert "Banana" in cell_map[(2, 0)]
        assert "Orange" in cell_map[(3, 0)]

    @patch("pdfplumber.open")
    def test_table_extraction_creates_table_cell_blocks(self, mock_pdfplumber_open):
        """Test that TABLE_CELL blocks are created for searchable text."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        # Should have TABLE_CELL blocks
        table_cell_blocks = [b for b in result.blocks if b.block_type == BlockType.TABLE_CELL]
        assert len(table_cell_blocks) > 0

        # Verify TABLE_CELL block structure
        for block in table_cell_blocks:
            assert block.block_type == BlockType.TABLE_CELL
            assert block.page == 1  # All on first page
            assert block.text  # Should have text content
            assert block.bbox is not None  # Should have bounding box
            assert 0 <= block.confidence <= 1  # Valid confidence

    @patch("pdfplumber.open")
    def test_table_extraction_no_duplicate_positions(self, mock_pdfplumber_open):
        """Test that no duplicate (row, col) positions exist."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Check for duplicate positions
        positions = [(cell.row, cell.col) for cell in table.cells]
        unique_positions = set(positions)

        assert len(positions) == len(unique_positions), "Found duplicate cell positions"

    @patch("pdfplumber.open")
    def test_table_extraction_row_col_count_validation(self, mock_pdfplumber_open):
        """Test that row_count and col_count match actual table dimensions."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Calculate actual dimensions from cells
        actual_max_row = max(cell.row for cell in table.cells)
        actual_max_col = max(cell.col for cell in table.cells)

        # row_count should be max_row + 1 (since 0-indexed)
        assert table.row_count == actual_max_row + 1
        assert table.col_count == actual_max_col + 1

    @patch("pdfplumber.open")
    def test_table_extraction_with_parse_pdf_function(self, mock_pdfplumber_open):
        """Test table extraction using the convenience parse_pdf function."""
        # Mock pdfplumber to return table data
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [
                ["Product", "Price", "Quantity"],
                ["Apple", "1.20", "50"],
                ["Banana", "0.80", "30"],
                ["Orange", "1.50", "25"],
            ]
        ]
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

        pdf_bytes = self.create_test_pdf_with_table()

        result = parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert isinstance(result, DocumentJSON)
        assert len(result.tables) > 0

        table = result.tables[0]
        assert table.row_count == 4
        assert table.col_count == 3

        # Should have TABLE_CELL blocks
        table_cell_blocks = [b for b in result.blocks if b.block_type == BlockType.TABLE_CELL]
        assert len(table_cell_blocks) > 0

    def test_table_extraction_empty_pdf(self):
        """Test that table extraction handles PDFs with no tables gracefully."""
        # Mock pdfplumber to return no tables
        with patch("pdfplumber.open") as mock_pdfplumber_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_tables.return_value = []
            mock_pdf.pages = [mock_page]
            mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

            # Create PDF without tables
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), "This is a document without tables.", fontsize=12)

            pdf_bytes = doc.write()
            doc.close()

            parser = PDFParser()
            result = parser.parse_pdf(
                pdf_bytes=pdf_bytes,
                document_id="no-table-doc",
                blob_id="no-table-blob",
                file_hash="no-table-hash",
            )

            # Should have no tables
            assert len(result.tables) == 0

            # Should have no TABLE_CELL blocks
            table_cell_blocks = [b for b in result.blocks if b.block_type == BlockType.TABLE_CELL]
            assert len(table_cell_blocks) == 0

            # Should still have regular text blocks
            regular_blocks = [b for b in result.blocks if b.block_type != BlockType.TABLE_CELL]
            assert len(regular_blocks) > 0

    def test_table_extraction_detects_table_integration(self):
        """Test that table extraction detects tables in PDF (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        # Should have extracted at least one table
        assert len(result.tables) > 0

        # Find the table (should be the first/only one)
        table = result.tables[0]
        assert isinstance(table, ExtractedTable)

        # Verify table has correct structure
        assert table.row_count == 4  # 4 rows of data
        assert table.col_count == 3  # 3 columns

        # Verify table ID format
        assert table.table_id.startswith("1_tbl_")  # Page 1, table index

    def test_table_extraction_cell_positions_integration(self):
        """Test that cells are extracted with correct row/col positions (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Check that we have cells
        assert len(table.cells) > 0

        # Verify cell positions are 0-indexed and within bounds
        for cell in table.cells:
            assert cell.row >= 0
            assert cell.col >= 0
            assert cell.row < table.row_count
            assert cell.col < table.col_count

        # Check for expected header cells (first row)
        header_cells = [c for c in table.cells if c.row == 0]
        assert len(header_cells) == 3  # 3 header cells

        # Check for expected data cells
        data_cells = [c for c in table.cells if c.row > 0]
        assert len(data_cells) == 9  # 3 rows × 3 columns = 9 data cells

    def test_table_extraction_header_detection_integration(self):
        """Test that header rows are correctly identified (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Check that first row cells are marked as headers
        header_cells = [c for c in table.cells if c.row == 0]
        for cell in header_cells:
            assert cell.is_header is True

        # Check that non-first row cells are not marked as headers
        data_cells = [c for c in table.cells if c.row > 0]
        for cell in data_cells:
            assert cell.is_header is False

    def test_table_extraction_cell_text_content_integration(self):
        """Test that cell text content is correctly extracted (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Create a mapping of cell positions to text for easy lookup
        cell_map = {(cell.row, cell.col): cell.text for cell in table.cells}

        # Check header row
        assert cell_map[(0, 0)] == "Product"
        assert cell_map[(0, 1)] == "Price"
        assert cell_map[(0, 2)] == "Quantity"

        # Check some data cells
        assert "Apple" in cell_map[(1, 0)]
        assert "Banana" in cell_map[(2, 0)]
        assert "Orange" in cell_map[(3, 0)]

    def test_table_extraction_creates_table_cell_blocks_integration(self):
        """Test that TABLE_CELL blocks are created for searchable text (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        # Should have TABLE_CELL blocks
        table_cell_blocks = [b for b in result.blocks if b.block_type == BlockType.TABLE_CELL]
        assert len(table_cell_blocks) > 0

        # Verify TABLE_CELL block structure
        for block in table_cell_blocks:
            assert block.block_type == BlockType.TABLE_CELL
            assert block.page == 1  # All on first page
            assert block.text  # Should have text content
            assert block.bbox is not None  # Should have bounding box
            assert 0 <= block.confidence <= 1  # Valid confidence

    def test_table_extraction_no_duplicate_positions_integration(self):
        """Test that no duplicate (row, col) positions exist (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Check for duplicate positions
        positions = [(cell.row, cell.col) for cell in table.cells]
        unique_positions = set(positions)

        assert len(positions) == len(unique_positions), "Found duplicate cell positions"

    def test_table_extraction_row_col_count_validation_integration(self):
        """Test that row_count and col_count match actual table dimensions (integration test)."""
        parser = PDFParser()
        pdf_bytes = self.create_test_pdf_with_table()

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert len(result.tables) > 0
        table = result.tables[0]

        # Calculate actual dimensions from cells
        actual_max_row = max(cell.row for cell in table.cells)
        actual_max_col = max(cell.col for cell in table.cells)

        # row_count should be max_row + 1 (since 0-indexed)
        assert table.row_count == actual_max_row + 1
        assert table.col_count == actual_max_col + 1

    def test_table_extraction_with_parse_pdf_function_integration(self):
        """Test table extraction using the convenience parse_pdf function (integration test)."""
        pdf_bytes = self.create_test_pdf_with_table()

        result = parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-test-doc",
            blob_id="table-test-blob",
            file_hash="table-test-hash",
        )

        assert isinstance(result, DocumentJSON)
        assert len(result.tables) > 0

        table = result.tables[0]
        assert table.row_count == 4
        assert table.col_count == 3

        # Should have TABLE_CELL blocks
        table_cell_blocks = [b for b in result.blocks if b.block_type == BlockType.TABLE_CELL]
        assert len(table_cell_blocks) > 0

    def test_table_extraction_empty_pdf_integration(self):
        """Test that table extraction handles PDFs with no tables gracefully (integration test)."""
        # Create PDF without tables
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "This is a document without tables.", fontsize=12)

        pdf_bytes = doc.write()
        doc.close()

        parser = PDFParser()
        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="no-table-doc",
            blob_id="no-table-blob",
            file_hash="no-table-hash",
        )

        # Should have no tables
        assert len(result.tables) == 0

        # Should have no TABLE_CELL blocks
        table_cell_blocks = [b for b in result.blocks if b.block_type == BlockType.TABLE_CELL]
        assert len(table_cell_blocks) == 0

        # Should still have regular text blocks
        regular_blocks = [b for b in result.blocks if b.block_type != BlockType.TABLE_CELL]
        assert len(regular_blocks) > 0
