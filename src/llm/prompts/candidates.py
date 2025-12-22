"""Prompt template for Stage 5: Candidate retrieval expansion.

This prompt asks the LLM to identify additional sections with positioning language
that may not have been caught by keyword search.
"""

from src.models.pipeline import RetrievedChunk


def build_candidate_expansion_prompt(
    keyword_chunks: list[RetrievedChunk],
    all_chunks: list[RetrievedChunk],
) -> str:
    """Build prompt for LLM-assisted retrieval expansion.

    Args:
        keyword_chunks: Chunks found via keyword search
        all_chunks: All available chunks from the document

    Returns:
        Formatted prompt string
    """
    # Format keyword-matched chunks
    keyword_section = "\n\n".join(
        f"[{chunk.chunk_id}] (page {chunk.page}):\n{chunk.text}"
        for chunk in keyword_chunks[:8]  # Limit to avoid prompt bloat
    )

    # Format preview of other chunks (limited to avoid prompt size issues)
    other_chunks = [
        c for c in all_chunks if c.chunk_id not in {kc.chunk_id for kc in keyword_chunks}
    ]
    other_section = "\n\n".join(
        f"[{chunk.chunk_id}] (page {chunk.page}):\n{chunk.text[:300]}{'...' if len(chunk.text) > 300 else ''}"
        for chunk in other_chunks[:15]  # Preview only
    )

    prompt = f"""# Task: Identify Additional Allocation Signal Passages

You are analyzing a fund manager outlook document. We've already identified passages containing explicit positioning keywords (overweight, underweight, neutral, etc.).

**Your task:** Review the keyword-matched passages and other document sections, then identify:
1. Additional passages with allocation signals that use INDIRECT or IMPLIED positioning language
2. Passages with comparative statements (e.g., "prefer X over Y", "favor", "avoiding")
3. Passages with tactical shifts or rebalancing actions

## Keyword-Matched Passages (Already Found)
{keyword_section}

## Other Document Sections (Preview)
{other_section}

## Output Format

Return a JSON object with this structure:

```json
{{
    "additional_chunk_ids": [
        "doc_123_chunk_5",
        "doc_123_chunk_8"
    ],
    "reasoning": "Brief explanation of why each additional chunk was selected"
}}
```

**IMPORTANT RULES:**
1. ONLY return chunk IDs (the bracketed identifiers like [doc_123_chunk_5]) from the "Other Document Sections" above
2. Do NOT return chunk IDs already in the keyword-matched section
3. Return EMPTY LIST if no additional passages contain positioning signals
4. Maximum 10 additional chunks
5. Focus on QUALITY over quantity - only select chunks with clear allocation implications

**Examples of INDIRECT positioning language to look for:**
- "We continue to find value in..."
- "Looks attractive at current levels"
- "Reducing exposure to..."
- "Increasing allocation to..."
- "Constructive view on..."
- "Cautious stance toward..."
- "Trim positions in..."

**Do NOT select chunks that are:**
- Pure macroeconomic commentary without asset class implications
- Historical performance data
- Disclaimers or methodology descriptions
- General market observations without positioning
"""

    return prompt
