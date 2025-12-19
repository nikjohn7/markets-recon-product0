"""LLM interaction layer for the pipeline."""
from src.llm.client import (
    LLMClient,
    LLMProvider,
    PipelineStage,
    ProviderConfig,
    PROVIDER_CONFIGS,
    STAGE_PROVIDER_MAP,
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
    "LLMClient",
    "LLMProvider",
    "PipelineStage",
    "ProviderConfig",
    "PROVIDER_CONFIGS",
    "STAGE_PROVIDER_MAP",
    "get_stage_model_info",
    "HALLUCINATION_MARKERS",
    "extract_allocation_calls",
    "extract_citations",
    "find_hallucination_markers",
    "validate_citations",
    "validate_llm_output",
    "validate_taxonomy",
]
