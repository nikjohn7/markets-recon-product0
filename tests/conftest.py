"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_document_id() -> str:
    """Return a sample document ID for testing."""
    return "doc_test_12345678"
