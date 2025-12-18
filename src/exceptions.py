"""Domain-specific exception hierarchy for Markets Recon pipeline.

All pipeline exceptions inherit from PipelineError to enable broad error handling
while still allowing specific exception types to be caught.

Exception Hierarchy:
    PipelineError (base)
    ├── ExtractionError
    │   ├── WeakEvidenceError
    │   └── TaxonomyMappingError
    ├── ValidationError
    ├── LLMError
    └── StorageError
"""


class PipelineError(Exception):
    """Base exception for all Markets Recon pipeline errors.

    All domain-specific exceptions inherit from this class, allowing
    broad exception handling with `except PipelineError`.
    """


class ExtractionError(PipelineError):
    """Base for extraction failures.

    Raised when document extraction (text, tables, metadata) fails.
    """


class WeakEvidenceError(ExtractionError):
    """LLM could not find sufficient evidence.

    Raised when the LLM cannot extract required information with
    sufficient confidence from the document text. This typically
    indicates the document lacks the expected information.
    """


class TaxonomyMappingError(ExtractionError):
    """Asset class could not be mapped to taxonomy.

    Raised when an asset class mention in the document cannot be
    resolved to a valid category/sub-asset in our taxonomy system.
    """


class ValidationError(PipelineError):
    """Validation of data against schema failed.

    Raised when Pydantic validation fails or when business logic
    validation detects invalid data (e.g., inconsistent citations,
    missing required fields).
    """


class LLMError(PipelineError):
    """LLM API call or response parsing failed.

    Raised when:
    - API call fails (network, auth, rate limit)
    - Response format is invalid
    - JSON parsing fails
    - Model output doesn't match expected schema
    """


class StorageError(PipelineError):
    """Storage operation (database, blob) failed.

    Raised when:
    - Database connection/query fails
    - Blob storage read/write fails
    - Transaction commit fails
    """
