"""Unit tests for DocumentProfile model."""

import pytest
from pydantic import ValidationError

from src.models.core import Citation
from src.models.enums import DocumentType
from src.models.profile import DocumentProfile


class TestDocumentProfile:
    def test_valid_profile(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        p = DocumentProfile(
            document_id="d1",
            manager_name="BlackRock",
            title="2024 Outlook",
            document_type=DocumentType.ANNUAL_OUTLOOK,
            asset_classes_covered=["Equities"],
            citations=[c],
        )
        assert p.manager_name == "BlackRock"
        assert p.manager_name_uncertain is False

    def test_manager_name_min_length(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            DocumentProfile(
                document_id="d1",
                manager_name="",
                title="Title",
                document_type=DocumentType.OTHER,
                asset_classes_covered=["Equities"],
                citations=[c],
            )

    def test_citations_required(self) -> None:
        with pytest.raises(ValidationError):
            DocumentProfile(
                document_id="d1",
                manager_name="Manager",
                title="Title",
                document_type=DocumentType.OTHER,
                asset_classes_covered=["Equities"],
                citations=[],
            )

    def test_asset_classes_required(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            DocumentProfile(
                document_id="d1",
                manager_name="Manager",
                title="Title",
                document_type=DocumentType.OTHER,
                asset_classes_covered=[],
                citations=[c],
            )

    def test_uncertainty_flags(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        p = DocumentProfile(
            document_id="d1",
            manager_name="Unknown Manager",
            title="Title",
            document_type=DocumentType.OTHER,
            asset_classes_covered=["Equities"],
            citations=[c],
            manager_name_uncertain=True,
            publication_date_uncertain=True,
        )
        assert p.manager_name_uncertain is True
        assert p.publication_date_uncertain is True
