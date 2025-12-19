"""Stage 4: Document metadata extraction prompt.

This prompt extracts manager name, publication date, document type,
and asset classes covered from retrieved document excerpts.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.models.enums import DocumentType

if TYPE_CHECKING:
    from src.models.pipeline import RetrievedChunk

# Document type descriptions for the prompt
DOCUMENT_TYPE_DESCRIPTIONS: dict[str, str] = {
    DocumentType.ANNUAL_OUTLOOK.value: "Full year outlook (2025 Outlook, Annual Outlook)",
    DocumentType.MID_YEAR_OUTLOOK.value: "Mid-year update (Mid-Year, H2 Outlook)",
    DocumentType.QUARTERLY_OUTLOOK.value: "Quarterly update (Q3 2025, Quarterly)",
    DocumentType.THEMATIC_NOTE.value: "Single theme deep dive",
    DocumentType.ASSET_CLASS_UPDATE.value: "Single asset class focus",
    DocumentType.OTHER.value: "If none of the above",
}


def format_chunks_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for inclusion in prompt.

    Args:
        chunks: List of retrieved chunks with metadata.

    Returns:
        Formatted string with chunk text and metadata.
    """
    formatted_parts: list[str] = []
    for chunk in chunks:
        header = f"[Chunk {chunk.chunk_id} | Page {chunk.page}]"
        formatted_parts.append(f"{header}\n{chunk.text}")
    return "\n\n---\n\n".join(formatted_parts)


def get_document_types_list() -> str:
    """Get formatted list of document types for prompt.

    Returns:
        Formatted string listing all document types with descriptions.
    """
    lines = []
    for doc_type, description in DOCUMENT_TYPE_DESCRIPTIONS.items():
        lines.append(f"- {doc_type}: {description}")
    return "\n".join(lines)


def get_metadata_extraction_schema() -> dict[str, object]:
    """Get JSON schema for metadata extraction output.

    Returns a simplified schema that maps to DocumentProfile,
    with fields that the LLM should extract.
    """
    return {
        "type": "object",
        "required": [
            "manager_name",
            "title",
            "document_type",
            "asset_classes_covered",
            "citations",
        ],
        "properties": {
            "manager_name": {
                "type": "string",
                "description": "Asset manager or publisher name (e.g., 'BlackRock', 'PIMCO')",
            },
            "manager_name_uncertain": {
                "type": "boolean",
                "default": False,
                "description": "True if manager name was inferred or unclear",
            },
            "title": {
                "type": "string",
                "description": "Document title",
            },
            "publication_date": {
                "type": ["string", "null"],
                "description": "Publication date in YYYY-MM-DD format, or null if not found",
            },
            "publication_date_uncertain": {
                "type": "boolean",
                "default": False,
                "description": "True if publication date was inferred or unclear",
            },
            "as_of_date": {
                "type": ["string", "null"],
                "description": "'As of' date in YYYY-MM-DD format if different from publication date",
            },
            "document_type": {
                "type": "string",
                "enum": [dt.value for dt in DocumentType],
                "description": "Type of document",
            },
            "asset_classes_covered": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Major asset classes discussed: EQUITIES, FIXED_INCOME, ALTERNATIVES, CURRENCIES, COMMODITIES",
            },
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Regions covered: US, EUROPE, UK, JAPAN, CHINA, EM, GLOBAL",
            },
            "time_horizon": {
                "type": ["string", "null"],
                "description": "Investment time horizon if stated (e.g., '6-12M', '3-6M')",
            },
            "intended_audience": {
                "type": ["string", "null"],
                "description": "Target audience if mentioned (e.g., 'Institutional Investors')",
            },
            "citations": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["chunk_id", "page"],
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "page": {"type": "integer", "minimum": 1},
                        "text_span": {
                            "type": "string",
                            "maxLength": 200,
                            "description": "Relevant text snippet supporting the extraction",
                        },
                    },
                },
                "description": "Citations for extracted information",
            },
        },
    }


METADATA_EXTRACTION_PROMPT = """You are extracting metadata from an investment research document.

## Retrieved Excerpts (likely containing metadata)
{chunks}

## Task
Extract the document profile. Use ONLY information from the excerpts above.

## Output Schema
{schema}

## Rules
1. manager_name: The asset manager or publisher (e.g., "BlackRock", "PIMCO")
   - If unclear, set manager_name_uncertain=true
   - Never guess—look for explicit mentions in headers, footers, or logos

2. publication_date: When the document was published
   - Look for "Date:", "Published:", explicit dates in headers
   - Format: YYYY-MM-DD
   - If not found, set publication_date=null, publication_date_uncertain=true

3. as_of_date: The "as of" date if different from publication date
   - Common patterns: "Data as of", "Views as of"

4. document_type: One of the following:
{document_types}

5. asset_classes_covered: List all major asset classes discussed
   - Use these terms: EQUITIES, FIXED_INCOME, ALTERNATIVES, CURRENCIES, COMMODITIES
   - Only include if substantively discussed, not just mentioned

6. regions: List geographic regions covered
   - Use: US, EUROPE, UK, JAPAN, CHINA, EM (Emerging Markets), GLOBAL

7. citations: For each key field, cite the chunk_id and page where you found it
   - Include a text_span (≤200 chars) with the relevant quote

## Critical Guardrails
- Do NOT invent or guess information not present in the excerpts
- If a field cannot be determined, use null and set the corresponding _uncertain flag to true
- Every extracted field must be traceable to a citation

## Output (JSON only, no explanation)
"""


def build_metadata_extraction_prompt(chunks: list[RetrievedChunk]) -> str:
    """Build the complete metadata extraction prompt.

    Args:
        chunks: Retrieved chunks likely containing metadata.

    Returns:
        Complete prompt string ready for LLM.
    """
    return METADATA_EXTRACTION_PROMPT.format(
        chunks=format_chunks_for_prompt(chunks),
        schema=json.dumps(get_metadata_extraction_schema(), indent=2),
        document_types=get_document_types_list(),
    )
