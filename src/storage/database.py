"""SQLite database layer for Markets Recon pipeline.

This module provides SQLAlchemy Core-based database access for MVP.
Schema is designed to be PostgreSQL-portable for production migration.

SQLite adaptations:
- UUID stored as TEXT (36 chars)
- TIMESTAMPTZ → TEXT (ISO 8601 format)
- ARRAY → JSON array as TEXT
- JSONB → JSON as TEXT
- Enum types → TEXT with CHECK constraints
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Connection,
    Date,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine

from src.exceptions import StorageError


class Database:
    """SQLite database for Markets Recon pipeline.

    Provides table creation and connection management using SQLAlchemy Core.
    All tables use TEXT-based UUIDs for compatibility with PostgreSQL migration.

    Attributes:
        engine: SQLAlchemy engine instance
        metadata: SQLAlchemy metadata containing table definitions
    """

    def __init__(self, db_path: str | Path = "./data/marketsrecon.db") -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_data_dir()

        # Create engine with SQLite-specific settings
        db_url = f"sqlite:///{self.db_path}"
        self.engine: Engine = create_engine(
            db_url,
            echo=False,  # Set to True for SQL debugging
            future=True,  # Use SQLAlchemy 2.0 style
        )
        event.listen(self.engine, "connect", self._enable_foreign_keys)
        self._initialize_foreign_keys()

        self.metadata = MetaData()
        self._define_tables()
        self._create_tables()

    def _initialize_foreign_keys(self) -> None:
        """Ensure foreign key enforcement is active on initial engine connection."""

        try:
            with self.engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys=ON"))
        except Exception as e:
            raise StorageError(f"Failed to enable foreign key enforcement: {e}") from e

    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Failed to create database directory: {e}") from e

    def _define_tables(self) -> None:
        """Define all database tables using SQLAlchemy Core.

        Tables are designed for PostgreSQL portability:
        - UUID as TEXT (will map to UUID type in Postgres)
        - JSON as TEXT (will map to JSONB in Postgres)
        - TEXT with CHECK for enums (will map to enum types in Postgres)
        """
        # Managers table
        self.managers = Table(
            "managers",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("name", Text, nullable=False, unique=True),
            Column("aliases", Text),  # JSON array as TEXT
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
        )

        # Documents table
        self.documents = Table(
            "documents",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("manager_id", Text, ForeignKey("managers.id")),
            Column("blob_id", Text, nullable=False),
            Column("file_hash", Text, nullable=False, unique=True),
            Column("title", Text),
            Column("publication_date", Date),
            Column("as_of_date", Date),
            Column("document_type", Text),
            CheckConstraint(
                "document_type IN ('outlook', 'quarterly_review', 'special_report', 'whitepaper')"
            ),
            Column("time_snapshot", Text),
            Column("extraction_coverage", Float),
            Column("overall_confidence", Float),
            Column("analyst_attention_required", Boolean, default=False),
            Column("status", Text, nullable=False, default="pending", server_default="pending"),
            CheckConstraint(
                "status IN ('pending', 'processing', 'completed', 'failed', 'review_required')"
            ),
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
            Column("reviewed_at", Text),
            Column("reviewed_by", Text),
        )

        # Allocation calls table
        self.allocation_calls = Table(
            "allocation_calls",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("document_id", Text, ForeignKey("documents.id"), nullable=False),
            Column("asset_class_category", Text, nullable=False),
            Column("sub_asset_class", Text, nullable=False),
            Column("call", Text, nullable=False),
            CheckConstraint("call IN ('OVERWEIGHT', 'NEUTRAL', 'UNDERWEIGHT', 'UNCERTAIN')"),
            Column("conviction", Text),
            CheckConstraint("conviction IN ('HIGH', 'MEDIUM', 'LOW')"),
            Column("time_horizon", Text),
            Column("rationale_bullets", Text),  # JSON array
            Column("key_indicators", Text),  # JSON array
            Column("key_risks", Text),  # JSON array
            Column("tooltip_text", Text),
            Column("citations", Text, nullable=False),  # JSON array
            Column("confidence", Float, nullable=False),
            Column("needs_analyst_review", Boolean, default=False),
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
        )

        # Summaries table
        self.summaries = Table(
            "summaries",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("document_id", Text, ForeignKey("documents.id"), nullable=False, unique=True),
            Column("executive_summary", Text),
            Column("search_descriptor", Text),
            Column("key_takeaways", Text),  # JSON array
            Column("overall_sentiment", Text),
            CheckConstraint("overall_sentiment IN ('BULLISH', 'NEUTRAL', 'BEARISH', 'MIXED')"),
            Column("sentiment_rationale", Text),  # JSON array
            Column("sentiment_citations", Text),  # JSON array
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
        )

        # Document tags table
        self.document_tags = Table(
            "document_tags",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("document_id", Text, ForeignKey("documents.id"), nullable=False),
            Column("tag_type", Text, nullable=False),
            CheckConstraint(
                "tag_type IN ('ASSET_CLASS', 'REGION', 'THEME', 'RISK', 'MACRO_REGIME', 'INDICATOR', 'MANAGER_VIEW')"
            ),
            Column("tag_value", Text, nullable=False),
            Column("confidence", Float),
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
            UniqueConstraint("document_id", "tag_type", "tag_value", name="uq_document_tag"),
        )

        # Evidence blocks table
        self.evidence_blocks = Table(
            "evidence_blocks",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("document_id", Text, ForeignKey("documents.id"), nullable=False),
            Column("chunk_id", Text, nullable=False),
            Column("page", Integer, nullable=False),
            Column("text", Text, nullable=False),
            Column("block_type", Text),
            CheckConstraint(
                "block_type IN ('HEADING', 'PARAGRAPH', 'BULLET', 'TABLE_CELL', 'CHART_TEXT', 'CAPTION', 'FOOTER')"
            ),
            Column("bbox", Text),  # JSON
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
            UniqueConstraint("document_id", "chunk_id", name="uq_document_chunk"),
        )

        # Pipeline runs table (for tracking execution metadata)
        self.pipeline_runs = Table(
            "pipeline_runs",
            self.metadata,
            Column("id", Text, primary_key=True, default=lambda: str(uuid.uuid4())),
            Column("document_id", Text, ForeignKey("documents.id"), nullable=False),
            Column("pipeline_version", Text, nullable=False),
            Column("llm_model", Text, nullable=False),
            Column("llm_provider", Text, nullable=False),
            Column("started_at", Text, nullable=False),
            Column("completed_at", Text),
            Column("total_runtime_seconds", Float),
            Column("status", Text, nullable=False),
            CheckConstraint("status IN ('running', 'completed', 'failed')"),
            Column("error_message", Text),
            Column("stages_completed", Text),  # JSON array of stage names
            Column(
                "created_at", Text, nullable=False, default=lambda: datetime.now(UTC).isoformat()
            ),
        )

    def _create_tables(self) -> None:
        """Create all tables in the database."""
        try:
            self.metadata.create_all(self.engine)
        except Exception as e:
            raise StorageError(f"Failed to create database tables: {e}") from e

    @staticmethod
    def _enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
        """Ensure SQLite foreign key constraints are enforced for each connection."""

        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    def get_connection(self) -> Connection:
        """Get a database connection.

        Returns:
            SQLAlchemy Connection object

        Example:
            with db.get_connection() as conn:
                result = conn.execute(db.documents.select())
        """
        return self.engine.connect()

    def execute(self, statement: Any) -> Any:
        """Execute a SQL statement.

        Args:
            statement: SQLAlchemy statement to execute

        Returns:
            Result of the execution

        Raises:
            StorageError: If execution fails
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute(statement)
                conn.commit()
                if result.returns_rows:
                    return result.fetchall()
                return result.rowcount
        except Exception as e:
            raise StorageError(f"Database query failed: {e}") from e

    def close(self) -> None:
        """Close database connection and dispose engine."""
        self.engine.dispose()

    def reset_database(self) -> None:
        """Drop all tables and recreate them.

        WARNING: This deletes all data. Use only for testing.
        """
        try:
            self.metadata.drop_all(self.engine)
            self.metadata.create_all(self.engine)
        except Exception as e:
            raise StorageError(f"Failed to reset database: {e}") from e


def get_database(db_path: str | Path = "./data/marketsrecon.db") -> Database:
    """Factory function to get database instance.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database instance
    """
    return Database(db_path)
