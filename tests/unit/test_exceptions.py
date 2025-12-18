"""Tests for exception hierarchy in src/exceptions.py."""

import pytest

from src.exceptions import (
    ExtractionError,
    LLMError,
    PipelineError,
    StorageError,
    TaxonomyMappingError,
    ValidationError,
    WeakEvidenceError,
)


class TestExceptionHierarchy:
    """Test that all exceptions inherit correctly."""

    def test_pipeline_error_is_base(self) -> None:
        """PipelineError inherits from Exception."""
        assert issubclass(PipelineError, Exception)

    def test_extraction_error_inherits_from_pipeline_error(self) -> None:
        """ExtractionError inherits from PipelineError."""
        assert issubclass(ExtractionError, PipelineError)

    def test_weak_evidence_error_inherits_from_extraction_error(self) -> None:
        """WeakEvidenceError inherits from ExtractionError."""
        assert issubclass(WeakEvidenceError, ExtractionError)
        assert issubclass(WeakEvidenceError, PipelineError)

    def test_taxonomy_mapping_error_inherits_from_extraction_error(self) -> None:
        """TaxonomyMappingError inherits from ExtractionError."""
        assert issubclass(TaxonomyMappingError, ExtractionError)
        assert issubclass(TaxonomyMappingError, PipelineError)

    def test_validation_error_inherits_from_pipeline_error(self) -> None:
        """ValidationError inherits from PipelineError."""
        assert issubclass(ValidationError, PipelineError)

    def test_llm_error_inherits_from_pipeline_error(self) -> None:
        """LLMError inherits from PipelineError."""
        assert issubclass(LLMError, PipelineError)

    def test_storage_error_inherits_from_pipeline_error(self) -> None:
        """StorageError inherits from PipelineError."""
        assert issubclass(StorageError, PipelineError)


class TestExceptionInstantiation:
    """Test that exceptions can be instantiated with messages."""

    def test_can_instantiate_pipeline_error(self) -> None:
        """PipelineError can be instantiated with a message."""
        exc = PipelineError("test message")
        assert str(exc) == "test message"

    def test_can_instantiate_extraction_error(self) -> None:
        """ExtractionError can be instantiated with a message."""
        exc = ExtractionError("extraction failed")
        assert str(exc) == "extraction failed"

    def test_can_instantiate_weak_evidence_error(self) -> None:
        """WeakEvidenceError can be instantiated with a message."""
        exc = WeakEvidenceError("insufficient evidence for manager name")
        assert str(exc) == "insufficient evidence for manager name"

    def test_can_instantiate_taxonomy_mapping_error(self) -> None:
        """TaxonomyMappingError can be instantiated with a message."""
        exc = TaxonomyMappingError("unknown asset class: crypto")
        assert str(exc) == "unknown asset class: crypto"

    def test_can_instantiate_validation_error(self) -> None:
        """ValidationError can be instantiated with a message."""
        exc = ValidationError("missing required field: citations")
        assert str(exc) == "missing required field: citations"

    def test_can_instantiate_llm_error(self) -> None:
        """LLMError can be instantiated with a message."""
        exc = LLMError("API rate limit exceeded")
        assert str(exc) == "API rate limit exceeded"

    def test_can_instantiate_storage_error(self) -> None:
        """StorageError can be instantiated with a message."""
        exc = StorageError("database connection failed")
        assert str(exc) == "database connection failed"


class TestExceptionCatching:
    """Test that exceptions can be caught by base classes."""

    def test_catch_pipeline_error_catches_all(self) -> None:
        """Catching PipelineError catches all domain exceptions."""
        exceptions = [
            ExtractionError("test"),
            WeakEvidenceError("test"),
            TaxonomyMappingError("test"),
            ValidationError("test"),
            LLMError("test"),
            StorageError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(PipelineError):
                raise exc

    def test_catch_extraction_error_catches_subclasses(self) -> None:
        """Catching ExtractionError catches WeakEvidenceError and TaxonomyMappingError."""
        with pytest.raises(ExtractionError):
            raise WeakEvidenceError("test")

        with pytest.raises(ExtractionError):
            raise TaxonomyMappingError("test")

    def test_catch_specific_exception(self) -> None:
        """Can catch specific exception types."""
        with pytest.raises(WeakEvidenceError):
            raise WeakEvidenceError("test")

        with pytest.raises(TaxonomyMappingError):
            raise TaxonomyMappingError("test")

        with pytest.raises(ValidationError):
            raise ValidationError("test")

    def test_exception_not_caught_by_sibling(self) -> None:
        """Exceptions are not caught by sibling exception types."""
        # ValidationError should not catch LLMError
        with pytest.raises(LLMError):
            try:
                raise LLMError("test")
            except ValidationError:
                pytest.fail("LLMError should not be caught by ValidationError")

    def test_exception_preserves_message_when_caught(self) -> None:
        """Exception message is preserved when caught by base class."""
        test_message = "detailed error context"

        try:
            raise WeakEvidenceError(test_message)
        except ExtractionError as e:
            assert str(e) == test_message

        try:
            raise TaxonomyMappingError(test_message)
        except PipelineError as e:
            assert str(e) == test_message
