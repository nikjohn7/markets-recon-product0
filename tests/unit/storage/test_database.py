"""Tests for SQLite database layer in src/storage/database.py."""

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.exceptions import StorageError
from src.storage.database import Database, get_database


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(temp_db_path: Path) -> Database:
    """Create a test database instance."""
    database = Database(db_path=temp_db_path)
    yield database
    database.close()


class TestDatabaseInitialization:
    """Test database initialization and table creation."""

    def test_database_created_on_init(self, temp_db_path: Path) -> None:
        """Database file is created on initialization."""
        assert not temp_db_path.exists()
        db = Database(db_path=temp_db_path)
        assert temp_db_path.exists()
        db.close()

    def test_data_directory_created(self, tmp_path: Path) -> None:
        """Data directory is created if it doesn't exist."""
        db_path = tmp_path / "nested" / "dir" / "test.db"
        assert not db_path.parent.exists()

        db = Database(db_path=db_path)
        assert db_path.parent.exists()
        db.close()

    def test_all_tables_created(self, db: Database) -> None:
        """All required tables are created."""
        table_names = {
            "managers",
            "documents",
            "allocation_calls",
            "summaries",
            "document_tags",
            "evidence_blocks",
            "pipeline_runs",
        }

        with db.get_connection() as conn:
            # Query sqlite_master to get all table names
            from sqlalchemy import text

            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            )
            created_tables = {row[0] for row in result}

        assert created_tables == table_names

    def test_get_database_factory(self, temp_db_path: Path) -> None:
        """get_database() factory function works."""
        db = get_database(db_path=temp_db_path)
        assert isinstance(db, Database)
        assert temp_db_path.exists()
        db.close()


class TestManagersTable:
    """Test managers table operations."""

    def test_insert_manager(self, db: Database) -> None:
        """Can insert a manager record."""
        manager_id = str(uuid.uuid4())
        aliases = json.dumps(["BlackRock Inc", "BLK"])

        with db.get_connection() as conn:
            conn.execute(
                db.managers.insert().values(
                    id=manager_id,
                    name="BlackRock",
                    aliases=aliases,
                )
            )
            conn.commit()

            # Query back
            result = conn.execute(select(db.managers).where(db.managers.c.id == manager_id))
            row = result.fetchone()

        assert row is not None
        assert row.name == "BlackRock"
        assert row.aliases == aliases

    def test_manager_name_unique(self, db: Database) -> None:
        """Manager name must be unique."""
        with db.get_connection() as conn:
            conn.execute(db.managers.insert().values(name="BlackRock"))
            conn.commit()

            # Try to insert duplicate
            with pytest.raises(IntegrityError):
                conn.execute(db.managers.insert().values(name="BlackRock"))
                conn.commit()


class TestDocumentsTable:
    """Test documents table operations."""

    def test_insert_document(self, db: Database) -> None:
        """Can insert a document record."""
        doc_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="abc123",
                    file_hash="sha256hash",
                    title="Test Document",
                    publication_date=date(2025, 1, 15),
                    document_type="outlook",
                    status="pending",
                )
            )
            conn.commit()

            result = conn.execute(select(db.documents).where(db.documents.c.id == doc_id))
            row = result.fetchone()

        assert row is not None
        assert row.title == "Test Document"
        assert row.document_type == "outlook"
        assert row.status == "pending"

    def test_document_file_hash_unique(self, db: Database) -> None:
        """Document file_hash must be unique."""
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    blob_id="blob1",
                    file_hash="samehash",
                )
            )
            conn.commit()

            with pytest.raises(IntegrityError):
                conn.execute(
                    db.documents.insert().values(
                        blob_id="blob2",
                        file_hash="samehash",
                    )
                )
                conn.commit()

    def test_document_status_check_constraint(self, db: Database) -> None:
        """Document status must be valid enum value."""
        with db.get_connection() as conn:
            # Valid status should work
            conn.execute(
                db.documents.insert().values(
                    blob_id="blob1",
                    file_hash="hash1",
                    status="completed",
                )
            )
            conn.commit()

            # Invalid status should fail
            with pytest.raises(IntegrityError):
                conn.execute(
                    db.documents.insert().values(
                        blob_id="blob2",
                        file_hash="hash2",
                        status="invalid_status",
                    )
                )
                conn.commit()

    def test_document_manager_foreign_key_enforced(self, db: Database) -> None:
        """Foreign key to managers is enforced for documents."""

        with db.get_connection() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    db.documents.insert().values(
                        manager_id=str(uuid.uuid4()),
                        blob_id="blob_with_missing_manager",
                        file_hash="fk_hash_1",
                        status="pending",
                    )
                )
                conn.commit()


class TestAllocationCallsTable:
    """Test allocation_calls table operations."""

    def test_insert_allocation_call(self, db: Database) -> None:
        """Can insert an allocation call."""
        # First create a document
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

        # Insert allocation call
        call_id = str(uuid.uuid4())
        citations = json.dumps([{"chunk_id": "chunk1", "page": 1, "text_span": "evidence"}])

        with db.get_connection() as conn:
            conn.execute(
                db.allocation_calls.insert().values(
                    id=call_id,
                    document_id=doc_id,
                    asset_class_category="EQ_DM",
                    sub_asset_class="US_EQUITY",
                    call="OVERWEIGHT",
                    conviction="HIGH",
                    citations=citations,
                    confidence=0.85,
                )
            )
            conn.commit()

            result = conn.execute(select(db.allocation_calls).where(db.allocation_calls.c.id == call_id))
            row = result.fetchone()

        assert row is not None
        assert row.call == "OVERWEIGHT"
        assert row.conviction == "HIGH"
        assert row.confidence == 0.85

    def test_allocation_call_enum_constraints(self, db: Database) -> None:
        """Allocation call enums must be valid."""
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

            # Invalid call direction
            with pytest.raises(IntegrityError):
                conn.execute(
                    db.allocation_calls.insert().values(
                        document_id=doc_id,
                        asset_class_category="EQ_DM",
                        sub_asset_class="US_EQUITY",
                        call="INVALID_CALL",
                        citations="[]",
                        confidence=0.5,
                    )
                )
                conn.commit()


class TestSummariesTable:
    """Test summaries table operations."""

    def test_insert_summary(self, db: Database) -> None:
        """Can insert a document summary."""
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

        summary_id = str(uuid.uuid4())
        takeaways = json.dumps(["takeaway1", "takeaway2"])

        with db.get_connection() as conn:
            conn.execute(
                db.summaries.insert().values(
                    id=summary_id,
                    document_id=doc_id,
                    executive_summary="Test summary",
                    key_takeaways=takeaways,
                    overall_sentiment="BULLISH",
                )
            )
            conn.commit()

            result = conn.execute(select(db.summaries).where(db.summaries.c.id == summary_id))
            row = result.fetchone()

        assert row is not None
        assert row.executive_summary == "Test summary"
        assert row.overall_sentiment == "BULLISH"

    def test_summary_document_unique(self, db: Database) -> None:
        """Each document can have only one summary."""
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

            conn.execute(
                db.summaries.insert().values(
                    document_id=doc_id,
                    executive_summary="First summary",
                )
            )
            conn.commit()

            # Duplicate should fail
            with pytest.raises(IntegrityError):
                conn.execute(
                    db.summaries.insert().values(
                        document_id=doc_id,
                        executive_summary="Second summary",
                    )
                )
                conn.commit()


class TestDocumentTagsTable:
    """Test document_tags table operations."""

    def test_insert_tag(self, db: Database) -> None:
        """Can insert a document tag."""
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

        tag_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.document_tags.insert().values(
                    id=tag_id,
                    document_id=doc_id,
                    tag_type="ASSET_CLASS",
                    tag_value="US Equities",
                    confidence=0.9,
                )
            )
            conn.commit()

            result = conn.execute(select(db.document_tags).where(db.document_tags.c.id == tag_id))
            row = result.fetchone()

        assert row is not None
        assert row.tag_type == "ASSET_CLASS"
        assert row.tag_value == "US Equities"

    def test_tag_unique_constraint(self, db: Database) -> None:
        """Same tag (document + type + value) cannot be inserted twice."""
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

            conn.execute(
                db.document_tags.insert().values(
                    document_id=doc_id,
                    tag_type="THEME",
                    tag_value="AI Revolution",
                )
            )
            conn.commit()

            # Duplicate should fail
            with pytest.raises(IntegrityError):
                conn.execute(
                    db.document_tags.insert().values(
                        document_id=doc_id,
                        tag_type="THEME",
                        tag_value="AI Revolution",
                    )
                )
                conn.commit()


class TestPipelineRunsTable:
    """Test pipeline_runs table operations."""

    def test_insert_pipeline_run(self, db: Database) -> None:
        """Can insert a pipeline run record."""
        doc_id = str(uuid.uuid4())
        with db.get_connection() as conn:
            conn.execute(
                db.documents.insert().values(
                    id=doc_id,
                    blob_id="blob1",
                    file_hash="hash1",
                )
            )
            conn.commit()

        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC).isoformat()

        with db.get_connection() as conn:
            conn.execute(
                db.pipeline_runs.insert().values(
                    id=run_id,
                    document_id=doc_id,
                    pipeline_version="0.1.0",
                    llm_model="claude-3-5-sonnet-20241022",
                    llm_provider="anthropic",
                    started_at=started_at,
                    status="running",
                )
            )
            conn.commit()

            result = conn.execute(select(db.pipeline_runs).where(db.pipeline_runs.c.id == run_id))
            row = result.fetchone()

        assert row is not None
        assert row.pipeline_version == "0.1.0"
        assert row.llm_model == "claude-3-5-sonnet-20241022"
        assert row.status == "running"


class TestDatabaseUtilities:
    """Test database utility methods."""

    def test_reset_database(self, db: Database) -> None:
        """reset_database() drops and recreates all tables."""
        # Insert some data
        with db.get_connection() as conn:
            conn.execute(db.managers.insert().values(name="Test Manager"))
            conn.commit()

            result = conn.execute(select(db.managers))
            assert len(result.fetchall()) == 1

        # Reset database
        db.reset_database()

        # Data should be gone
        with db.get_connection() as conn:
            result = conn.execute(select(db.managers))
            assert len(result.fetchall()) == 0

    def test_execute_helper(self, db: Database) -> None:
        """execute() helper method works."""
        result = db.execute(db.managers.insert().values(name="Test Manager"))
        assert result is not None

        # Verify insertion
        with db.get_connection() as conn:
            result = conn.execute(select(db.managers))
            assert len(result.fetchall()) == 1
