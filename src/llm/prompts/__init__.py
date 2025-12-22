"""Prompt templates for LLM pipeline stages.

This module provides prompt templates and builder functions for each
LLM-powered pipeline stage, following the contracts in docs/LLM_CONTRACTS.md.

Stage 4 (Metadata): Extract document metadata (manager, date, type)
Stage 5 (Candidates): Identify signal-containing passages
Stage 6 (Calls): Extract allocation calls with taxonomy mapping
Stage 6 (Verification): Verify extracted calls against source (v1+)
Stage 7 (Summaries): Generate executive summary and key takeaways
Stage 8 (Tooltips): Generate concise hover text for calls
Stage 9 (Tags): Generate normalized tags for search/filtering
"""

from src.llm.prompts.calls import (
    build_call_extraction_prompt,
    format_taxonomy_summary,
    get_call_extraction_prompt_template,
    get_call_extraction_schema,
)
from src.llm.prompts.candidates import build_candidate_expansion_prompt
from src.llm.prompts.metadata import (
    METADATA_EXTRACTION_PROMPT,
    build_metadata_extraction_prompt,
    format_chunks_for_prompt,
    get_document_types_list,
    get_metadata_extraction_schema,
)
from src.llm.prompts.summaries import (
    build_summary_generation_prompt,
    format_calls_summary,
    get_summary_generation_prompt_template,
    get_summary_generation_schema,
)
from src.llm.prompts.tags import (
    build_tag_generation_prompt,
    get_tag_generation_prompt_template,
    get_tag_generation_schema,
)
from src.llm.prompts.tooltips import (
    build_tooltip_generation_prompt,
    get_tooltip_generation_prompt_template,
    get_tooltip_generation_schema,
)
from src.llm.prompts.verification import (
    build_verification_prompt,
    get_verification_prompt_template,
    get_verification_schema,
)

# Re-export format_chunks_for_prompt from metadata as the canonical implementation
# Other modules may import from here for consistency
__all__ = [
    # Calls (Stage 6)
    "build_call_extraction_prompt",
    # Candidates (Stage 5)
    "build_candidate_expansion_prompt",
    # Metadata (Stage 4)
    "build_metadata_extraction_prompt",
    # Summaries (Stage 7)
    "build_summary_generation_prompt",
    # Tags (Stage 9)
    "build_tag_generation_prompt",
    # Tooltips (Stage 8)
    "build_tooltip_generation_prompt",
    # Verification (Stage 6 - v1+)
    "build_verification_prompt",
    "format_calls_summary",
    "format_chunks_for_prompt",
    "format_taxonomy_summary",
    "get_call_extraction_prompt_template",
    "get_call_extraction_schema",
    "get_document_types_list",
    "get_metadata_extraction_prompt_template",
    "get_metadata_extraction_schema",
    "get_summary_generation_prompt_template",
    "get_summary_generation_schema",
    "get_tag_generation_prompt_template",
    "get_tag_generation_schema",
    "get_tooltip_generation_prompt_template",
    "get_tooltip_generation_schema",
    "get_verification_prompt_template",
    "get_verification_schema",
]


def get_metadata_extraction_prompt_template() -> str:
    """Get the metadata extraction prompt template."""
    return METADATA_EXTRACTION_PROMPT
