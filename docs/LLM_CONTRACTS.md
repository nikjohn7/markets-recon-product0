# LLM Contracts

This document defines how LLMs are used in the pipeline: prompt templates, output contracts, and guardrails.

---

## Core Principles

### 1. Never Read Full Documents

LLMs receive **retrieved chunks only**, never the entire PDF content.

```python
# WRONG
prompt = f"Read this document and extract calls:\n{full_document_text}"

# RIGHT
relevant_chunks = await retrieval_index.query("allocation calls overweight underweight")
prompt = f"Given these excerpts, extract calls:\n{format_chunks(relevant_chunks)}"
```

### 2. JSON Output Always

Every LLM call returns structured JSON matching a Pydantic model.

```python
# WRONG
response = await llm.complete("What calls are in this text?")
# Parses free text... unreliable

# RIGHT
response = await llm.complete(
    prompt=structured_prompt,
    response_format={"type": "json_object"},
    schema=AllocationCall.model_json_schema()
)
validated = AllocationCall.model_validate_json(response)
```

### 3. Evidence-Anchored Citations

Every claim must reference source chunks.

```python
# WRONG
{
    "call": "OVERWEIGHT",
    "rationale": ["Good risk-reward"]  # Where does this come from?
}

# RIGHT
{
    "call": "OVERWEIGHT",
    "rationale": ["Good risk-reward given ECB easing cycle"],
    "citations": [{"chunk_id": "3_14", "page": 3, "text_span": "We see..."}]
}
```

### 4. UNCERTAIN Over Guess

If evidence is weak, return `UNCERTAIN` with reason—never fabricate.

```python
# WRONG: Guessing when unclear
{
    "call": "NEUTRAL",  # Document was ambiguous, model guessed
    "confidence": 0.5
}

# RIGHT: Explicit uncertainty
{
    "call": "UNCERTAIN",
    "needs_analyst_review": true,
    "review_reason": "No explicit positioning language found; only general commentary"
}
```

---

## Prompt Templates

### Stage 4: Document Metadata Extraction

```python
METADATA_EXTRACTION_PROMPT = """
You are extracting metadata from an investment research document.

## Retrieved Excerpts (likely containing metadata)
{chunks}

## Task
Extract the document profile. Use ONLY information from the excerpts above.

## Output Schema
{schema}

## Rules
1. manager_name: The asset manager or publisher (e.g., "BlackRock", "PIMCO")
   - If unclear, set manager_name_uncertain=true
   - Never guess—look for explicit mentions
   
2. publication_date: When the document was published
   - Look for "Date:", "Published:", explicit dates in headers
   - Format: YYYY-MM-DD
   - If not found, set publication_date=null, publication_date_uncertain=true
   
3. as_of_date: The "as of" date if different from publication date
   - Common patterns: "Data as of", "Views as of"
   
4. document_type: One of {document_types}
   - ANNUAL_OUTLOOK: Full year outlook (2025 Outlook, Annual Outlook)
   - MID_YEAR_OUTLOOK: Mid-year update (Mid-Year, H2 Outlook)
   - QUARTERLY_OUTLOOK: Quarterly update (Q3 2025, Quarterly)
   - THEMATIC_NOTE: Single theme deep dive
   - ASSET_CLASS_UPDATE: Single asset class focus
   - OTHER: If none of the above
   
5. asset_classes_covered: List all major asset classes discussed
   - Use taxonomy terms: EQUITIES, FIXED_INCOME, ALTERNATIVES, CURRENCIES
   
6. citations: For each field, cite the chunk_id and page where you found it

## Output (JSON only, no explanation)
"""
```

### Stage 6: Allocation Call Extraction

```python
CALL_EXTRACTION_PROMPT = """
You are extracting allocation calls from fund manager research.

## Manager Context
Manager: {manager_name}
Document Type: {document_type}
Publication Date: {publication_date}

## Retrieved Excerpts (containing positioning language)
{chunks}

## Asset Taxonomy
{taxonomy}

## Task
Extract ALL allocation calls from the excerpts. An allocation call is an explicit positioning statement (overweight, neutral, underweight) on an asset class.

## Output Schema
{schema}

## Extraction Rules

### Call Direction
- OVERWEIGHT: "overweight", "prefer", "favor", "constructive", "bullish", "positive", "increase allocation", "add"
- UNDERWEIGHT: "underweight", "avoid", "cautious on", "bearish", "negative", "reduce allocation", "trim"
- NEUTRAL: "neutral", "benchmark weight", "hold", "no strong view"

### Conviction (only if stated)
- HIGH: "high conviction", "strong preference", "very constructive"
- MEDIUM: implied or moderate language
- LOW: "slight preference", "marginally"
- null: if not inferable

### Taxonomy Mapping
1. Map each asset mention to taxonomy category + sub-asset
2. If exact match not found, use closest category
3. If unmappable, set asset_class_category="UNMAPPED"

### Rationale Bullets
- 2-4 bullets per call
- Must be supported by excerpt text
- Include: drivers, catalysts, risks considered

### Key Indicators
- Extract specific indicators mentioned (inflation, growth, policy)
- Note direction: RISING, FALLING, STABLE, VOLATILE

### Citations
- MANDATORY: Every call needs at least 1 citation
- Include chunk_id, page, and relevant text_span (≤200 chars)

## Critical Guardrails

1. NO HALLUCINATION: If a call direction is unclear, output:
   {{
     "call": "UNCERTAIN",
     "needs_analyst_review": true,
     "review_reason": "Ambiguous positioning language"
   }}

2. NO DUPLICATE CALLS: One call per (category, sub-asset) pair

3. NO UNSUPPORTED RATIONALE: Every bullet must trace to excerpt text

4. RESPECT TAXONOMY: Use exact taxonomy codes, not free text

## Output (JSON only, no explanation)
"""
```

### Stage 6: Sentiment Extraction (Same Call)

```python
SENTIMENT_SECTION = """
## Overall Sentiment
Also extract the document's overall sentiment:

- NET_POSITIVE: Generally optimistic, constructive outlook
- NEUTRAL: Balanced, mixed signals
- NET_NEGATIVE: Cautious, bearish outlook

Provide:
- overall_sentiment: One of the above
- sentiment_rationale: 2-3 bullets explaining why
- sentiment_citations: References supporting sentiment assessment
"""
```

### Stage 7: Summary Generation

```python
SUMMARY_GENERATION_PROMPT = """
You are generating summaries for an investment research document.

## Document Profile
Manager: {manager_name}
Type: {document_type}
Date: {publication_date}

## Extracted Calls (summarized)
{calls_summary}

## Retrieved Key Passages
{chunks}

## Task
Generate three summary types:

### 1. Executive Summary (120-180 words)
For time-constrained allocators. Must include:
- Top 2-3 macro drivers
- Top 3 allocation calls (with direction)
- 2 key risks
- Use attribution: "The manager argues...", "The note states..."

### 2. Search Descriptor (20-35 words)
One sentence: "what this is" + "what it implies" + "main asset focus"
Example: "Mid-year outlook emphasizing easing inflation but sticky growth; prefers quality equities and core duration while cautious on HY spreads; highlights policy risk into year-end."

### 3. Key Takeaways (3-5 bullets)
Each bullet:
- ≤200 characters
- Actionable insight
- Must have citation

## Output Schema
{schema}

## Rules
1. WORD COUNTS ARE MANDATORY
2. Do not include information not in the excerpts
3. Do not invent statistics, dates, or quotes
4. Every key takeaway needs a citation

## Output (JSON only)
"""
```

### Stage 8: Tooltip Generation

```python
TOOLTIP_GENERATION_PROMPT = """
Generate concise hover text for each allocation call.

## Calls
{calls}

## Task
For each call, generate a tooltip that:
- Is ≤25 words
- Summarizes the positioning and key reason
- Is specific (not generic)
- Optionally includes a "watch item"

## Examples
Good: "Overweight Bunds as quality hedge; expects easing inflation and flight-to-safety if risk rises."
Bad: "Positive on European bonds due to macro factors."  # Too generic

Good: "Underweight US HY on tight spreads; watch Fed policy pivot and recession signals."
Bad: "Cautious on high yield."  # No rationale

## Output Format
{{
  "tooltips": [
    {{"sub_asset_class": "GERMAN_BUNDS", "tooltip_text": "..."}},
    ...
  ]
}}
"""
```

### Stage 9: Tag Generation

```python
TAG_GENERATION_PROMPT = """
Generate normalized tags for search and filtering.

## Document Profile
{profile}

## Extracted Calls
{calls}

## Key Passages
{chunks}

## Allowed Tag Vocabularies
Theme tags: {theme_tags}
Risk tags: {risk_tags}
Macro regime tags: {macro_regime_tags}

## Task
Generate tags in these categories:
1. theme_tags: Key themes discussed (from allowed list)
2. risk_tags: Key risks highlighted (from allowed list)
3. macro_regime_tags: Economic regime view (from allowed list)

(asset_class_tags, region_tags, instrument_tags are derived from calls—do not generate)

## Rules
1. Only use tags from the allowed lists
2. If a novel theme appears, flag it: {{"novel_themes": ["energy_policy"]}}
3. Limit to most relevant tags (max 5 per category)

## Output Schema
{schema}
"""
```

### Verification Pass (Stage 6)

```python
VERIFICATION_PROMPT = """
You are verifying allocation call extractions.

## Original Extraction
{original_calls}

## Source Excerpts (same as original extraction)
{chunks}

## Task
For each call, verify:
1. Is the call direction (OW/N/UW) supported by the excerpt?
2. Is the taxonomy mapping correct?
3. Is the rationale accurate to the source?

## Output
{{
  "verified_calls": [
    {{
      "original_index": 0,
      "call_verified": true,  // or false
      "disagreement_reason": null,  // or explanation
      "suggested_call": null  // or corrected call if disagreement
    }},
    ...
  ],
  "agreement_rate": 0.95
}}

Be critical. If evidence is weak, flag it.
"""
```

---

## Output Contracts

### Contract Structure

Every LLM interaction has:
1. **Input schema:** What the prompt provides
2. **Output schema:** Pydantic model (JSON Schema)
3. **Validation rules:** Post-processing checks
4. **Error handling:** What to do on failure

### Contract: Document Metadata

```python
class MetadataContract:
    input_schema = {
        "chunks": list[FormattedChunk],
        "document_types": list[str],
    }
    
    output_schema = DocumentProfile
    
    validation_rules = [
        "manager_name must be non-empty",
        "publication_date must be parseable date or null",
        "document_type must be valid enum",
        "at least 1 citation required",
    ]
    
    on_validation_failure = "flag_for_review"
```

### Contract: Allocation Calls

```python
class CallsContract:
    input_schema = {
        "manager_name": str,
        "document_type": str,
        "publication_date": str,
        "chunks": list[FormattedChunk],
        "taxonomy": AssetTaxonomy,
    }
    
    output_schema = CallExtractionOutput
    
    validation_rules = [
        "every call has valid taxonomy mapping",
        "every call has ≥1 citation",
        "no duplicate (category, sub_asset) pairs",
        "rationale_bullets are non-empty",
        "citations reference valid chunk_ids",
    ]
    
    on_validation_failure = "flag_for_review"
    
    post_processing = [
        "verify_citations_exist",
        "normalize_taxonomy_codes",
        "run_verification_pass_if_high_stakes",
    ]
```

---

## Error Handling

### Retry Strategy

```python
async def call_llm_with_retry(
    prompt: str,
    schema: type[BaseModel],
    max_retries: int = 3,
) -> BaseModel:
    for attempt in range(max_retries):
        try:
            response = await llm.complete(prompt, schema=schema)
            validated = schema.model_validate_json(response)
            return validated
        except ValidationError as e:
            if attempt < max_retries - 1:
                # Retry with error context
                prompt = add_error_context(prompt, e)
            else:
                raise ExtractionError(f"Failed after {max_retries} attempts: {e}")
        except RateLimitError:
            await exponential_backoff(attempt)
```

### Validation Failure Handling

```python
def handle_validation_failure(
    stage: str,
    error: ValidationError,
    partial_output: dict,
) -> StageResult:
    """Handle validation failures gracefully."""
    
    # Log the failure
    logger.warning(f"Validation failed in {stage}: {error}")
    
    # Create partial result with flags
    return StageResult(
        success=False,
        partial_data=partial_output,
        needs_analyst_review=True,
        review_reason=f"Validation failed: {error}",
        confidence=0.3,  # Low confidence
    )
```

---

## Guardrails

### Input Guardrails

```python
def validate_prompt_input(chunks: list[Chunk], max_tokens: int = 8000):
    """Ensure prompt doesn't exceed context limits."""
    total_tokens = sum(count_tokens(c.text) for c in chunks)
    
    if total_tokens > max_tokens:
        # Truncate least relevant chunks
        chunks = prioritize_and_truncate(chunks, max_tokens)
    
    return chunks
```

### Output Guardrails

```python
def validate_llm_output(output: dict, schema: type[BaseModel]) -> BaseModel:
    """Comprehensive output validation."""
    
    # 1. Schema validation
    validated = schema.model_validate(output)
    
    # 2. Citation verification
    for field_name, citations in get_cited_fields(validated):
        for citation in citations:
            if not citation_exists_in_document(citation):
                raise ValidationError(f"Invalid citation: {citation}")
    
    # 3. Taxonomy verification
    for call in get_calls(validated):
        if not taxonomy_exists(call.asset_class_category):
            raise ValidationError(f"Invalid taxonomy: {call.asset_class_category}")
    
    # 4. Content checks
    if has_hallucination_markers(validated):
        raise ValidationError("Potential hallucination detected")
    
    return validated
```

### Hallucination Detection

```python
HALLUCINATION_MARKERS = [
    r"\d{4}-\d{2}-\d{2}",  # Specific dates not in source
    r"\d+(\.\d+)?%",       # Specific percentages not in source
    r'"[^"]{50,}"',        # Long quotes not in source
]

def has_hallucination_markers(output: BaseModel, source_chunks: list[Chunk]) -> bool:
    """Check if output contains content not in source."""
    output_text = json.dumps(output.model_dump())
    source_text = " ".join(c.text for c in source_chunks)
    
    for pattern in HALLUCINATION_MARKERS:
        matches = re.findall(pattern, output_text)
        for match in matches:
            if match not in source_text:
                return True
    
    return False
```

---

## Model Selection

### Recommended Models by Stage

| Stage | Model | Rationale |
|-------|-------|-----------|
| S4 (Metadata) | Claude 3.5 Sonnet | Good balance of speed/accuracy |
| S5 (Candidates) | Claude 3.5 Haiku | Fast, cheap, simple task |
| S6 (Calls) | Claude 3.5 Sonnet | Critical accuracy |
| S6 (Verification) | Claude 3.5 Sonnet | Independent verification |
| S7 (Summaries) | Claude 3.5 Sonnet | Quality writing |
| S8 (Tooltips) | Claude 3.5 Haiku | Simple generation |
| S9 (Tags) | Claude 3.5 Haiku | Classification task |

### Cost Optimization

```python
# Use cheaper models for simpler tasks
STAGE_MODEL_MAP = {
    "metadata": "claude-3-5-sonnet-20241022",
    "candidates": "claude-3-5-haiku-20241022",
    "calls": "claude-3-5-sonnet-20241022",
    "verification": "claude-3-5-sonnet-20241022",  # Only run for HIGH stakes
    "summaries": "claude-3-5-sonnet-20241022",
    "tooltips": "claude-3-5-haiku-20241022",
    "tags": "claude-3-5-haiku-20241022",
}

# Skip verification pass for documents from known templates
SKIP_VERIFICATION_FOR = ["manager_templates_v2", "standardized_outlook"]
```

---

## Debugging LLM Issues

### Logging

```python
@log_llm_call
async def extract_calls(chunks, taxonomy):
    """All LLM calls are logged with:
    - Input (prompt + chunks)
    - Output (raw + validated)
    - Latency
    - Token counts
    - Validation errors
    """
    ...
```

### Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Missing calls | Low call count | Expand retrieval, check keyword list |
| Wrong taxonomy | "UNMAPPED" codes | Update synonym dictionary |
| Weak rationale | Generic bullets | Include more context in prompt |
| Citation errors | Invalid chunk_ids | Verify chunks passed to prompt |
| Hallucinated dates | Dates not in source | Enable hallucination detection |
