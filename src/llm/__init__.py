"""LLM interaction layer for the pipeline."""

from src.llm.client import (
    PROVIDER_CONFIGS,
    STAGE_PROVIDER_MAP,
    LLMClient,
    LLMProvider,
    PipelineStage,
    ProviderConfig,
    get_stage_model_info,
)
from src.llm.contracts import (
    HALLUCINATION_MARKERS,
    extract_allocation_calls,
    extract_citations,
    find_hallucination_markers,
    validate_citations,
    validate_llm_output,
    validate_taxonomy,
)

__all__ = [
    "HALLUCINATION_MARKERS",
    "PROVIDER_CONFIGS",
    "STAGE_PROVIDER_MAP",
    "LLMClient",
    "LLMProvider",
    "PipelineStage",
    "ProviderConfig",
    "extract_allocation_calls",
    "extract_citations",
    "find_hallucination_markers",
    "get_stage_model_info",
    "validate_citations",
    "validate_llm_output",
    "validate_taxonomy",
]
