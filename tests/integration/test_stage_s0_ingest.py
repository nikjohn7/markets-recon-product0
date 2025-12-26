"""Integration tests for Stage 0 - Ingest."""

from __future__ import annotations

import pytest

from src.exceptions import ValidationError
from src.pipeline.stages.s0_ingest import stage_ingest
from src.storage.blob import LocalBlobStorage
from src.storage.database import Database


@pytest.mark.asyncio
async def test_stage_ingest_new_and_duplicate(tmp_path, sample_pdf_bytes, monkeypatch):
    """Ingest a PDF and detect duplicates on re-ingest."""
    storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "marketsrecon.db"

    class TempStorage(LocalBlobStorage):
        def __init__(self, _storage_dir=storage_dir):
            super().__init__(_storage_dir)

    class TempDatabase(Database):
        def __init__(self, _db_path=db_path):
            super().__init__(_db_path)

    monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", TempStorage)
    monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", TempDatabase)

    metadata = {"source": "tests", "filename": "sample.pdf"}
    result = await stage_ingest(sample_pdf_bytes, metadata)

    assert result.is_duplicate is False
    assert result.file_hash
    assert len(result.file_hash) == 64
    assert (storage_dir / f"{result.blob_id}.pdf").exists()

    duplicate = await stage_ingest(sample_pdf_bytes, metadata)

    assert duplicate.is_duplicate is True
    assert duplicate.document_id == result.document_id
    assert duplicate.blob_id == result.blob_id
    assert duplicate.file_hash == result.file_hash


@pytest.mark.asyncio
async def test_stage_ingest_rejects_empty_bytes():
    """Ensure empty payloads fail validation."""
    with pytest.raises(ValidationError, match="pdf_bytes cannot be empty"):
        await stage_ingest(b"", {"source": "tests"})
