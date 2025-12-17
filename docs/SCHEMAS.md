# Schemas

All data structures in this system are defined as Pydantic models. **No raw dicts cross function boundaries.**

---

## Enums

```python
from enum import Enum

class CallDirection(str, Enum):
    OVERWEIGHT = "OVERWEIGHT"
    NEUTRAL = "NEUTRAL"
    UNDERWEIGHT = "UNDERWEIGHT"
    UNCERTAIN = "UNCERTAIN"  # Evidence insufficient; requires analyst review

class Conviction(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Sentiment(str, Enum):
    NET_POSITIVE = "NET_POSITIVE"
    NEUTRAL = "NEUTRAL"
    NET_NEGATIVE = "NET_NEGATIVE"

class DocumentType(str, Enum):
    ANNUAL_OUTLOOK = "ANNUAL_OUTLOOK"
    MID_YEAR_OUTLOOK = "MID_YEAR_OUTLOOK"
    QUARTERLY_OUTLOOK = "QUARTERLY_OUTLOOK"
    THEMATIC_NOTE = "THEMATIC_NOTE"
    ASSET_CLASS_UPDATE = "ASSET_CLASS_UPDATE"
    OTHER = "OTHER"

class BlockType(str, Enum):
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    BULLET = "BULLET"
    TABLE_CELL = "TABLE_CELL"
    CHART_TEXT = "CHART_TEXT"
    FOOTNOTE = "FOOTNOTE"
    DISCLAIMER = "DISCLAIMER"

class ConfidenceBand(str, Enum):
    HIGH = "HIGH"      # ≥0.80
    MEDIUM = "MEDIUM"  # 0.60–0.79
    LOW = "LOW"        # <0.60

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    PUBLISHED = "published"
    FAILED = "failed"

class TagType(str, Enum):
    ASSET_CLASS = "ASSET_CLASS"
    REGION = "REGION"
    THEME = "THEME"
    RISK = "RISK"
    INSTRUMENT = "INSTRUMENT"
    STYLE = "STYLE"
    MACRO_REGIME = "MACRO_REGIME"

class IndicatorDirection(str, Enum):
    RISING = "RISING"
    FALLING = "FALLING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
```

---

## Core Models

### Citation (Universal)

```python
from pydantic import BaseModel, Field

class Citation(BaseModel):
    """Evidence reference back to source document."""
    chunk_id: str = Field(..., description="Retrieval chunk ID from Stage 3 index")
    block_ids: list[str] = Field(default_factory=list, description="Source block IDs for UI highlighting")
    page: int = Field(..., ge=1, description="1-indexed page number")
    text_span: str | None = Field(None, description="Relevant text excerpt (≤200 chars)")
    
    class Config:
        frozen = True
```

### BoundingBox

```python
class BoundingBox(BaseModel):
    """Coordinates on page (normalized 0-1)."""
    x0: float = Field(..., ge=0, le=1)
    y0: float = Field(..., ge=0, le=1)
    x1: float = Field(..., ge=0, le=1)
    y1: float = Field(..., ge=0, le=1)
```

---

## Document Extraction Models

### DocumentBlock

```python
class DocumentBlock(BaseModel):
    """Single block of content from PDF."""
    block_id: str = Field(..., description="Stable ID: {page}_{index}")
    page: int = Field(..., ge=1)
    text: str
    block_type: BlockType
    bbox: BoundingBox | None = None
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")
```

### ExtractedTable

```python
class TableCell(BaseModel):
    row: int
    col: int
    text: str
    is_header: bool = False

class ExtractedTable(BaseModel):
    """Structured table from PDF."""
    table_id: str
    page: int
    cells: list[TableCell]
    row_count: int
    col_count: int
    caption: str | None = None
```

### DocumentJSON

```python
class DocumentJSON(BaseModel):
    """Full extracted document structure."""
    document_id: str
    blob_id: str
    file_hash: str
    blocks: list[DocumentBlock]
    tables: list[ExtractedTable]
    page_count: int
    extraction_coverage: float = Field(..., ge=0, le=1, description="% pages with text")
    ocr_pages: list[int] = Field(default_factory=list, description="Pages that required OCR")
    vision_pages: list[int] = Field(default_factory=list, description="Pages processed with vision")
```

---

## Metadata Models (Stage 4)

### DocumentProfile

```python
class DocumentProfile(BaseModel):
    """Extracted document metadata."""
    document_id: str
    manager_name: str = Field(..., min_length=1)
    title: str
    publication_date: date | None = Field(None, description="Publication date if found")
    as_of_date: date | None = Field(None, description="'As of' date if different")
    document_type: DocumentType
    asset_classes_covered: list[str] = Field(..., min_length=1)
    regions: list[str] = Field(default_factory=list)
    time_horizon: str | None = Field(None, description="e.g., '6-12M', '3-6M'")
    intended_audience: str | None = None
    citations: list[Citation] = Field(..., min_length=1)
    
    # Null handling
    manager_name_uncertain: bool = False
    publication_date_uncertain: bool = False
```

---

## Allocation Call Models (Stage 6)

### KeyIndicator

```python
class KeyIndicator(BaseModel):
    """Economic/market indicator referenced in rationale."""
    name: str = Field(..., description="e.g., 'Inflation trend', 'Fed policy'")
    direction: IndicatorDirection
    why_it_matters: str = Field(..., max_length=200)
```

### AllocationCall

```python
class AllocationCall(BaseModel):
    """Single asset class positioning call."""
    asset_class_category: str = Field(..., description="From taxonomy, e.g., 'FIXED_INCOME_SOVEREIGNS_EUROPE'")
    sub_asset_class: str = Field(..., description="From taxonomy, e.g., 'GERMAN_BUNDS'")
    
    call: CallDirection
    conviction: Conviction | None = Field(None, description="Only if inferable from language")
    time_horizon: str | None = Field(None, description="Explicit if stated; else inherit from doc")
    
    rationale_bullets: list[str] = Field(..., min_length=1, max_length=4)
    key_indicators: list[KeyIndicator] = Field(default_factory=list, max_length=5)
    key_risks: list[str] = Field(default_factory=list, max_length=3)
    actionable_takeaways: list[str] = Field(default_factory=list, max_length=3)
    
    tooltip_text: str | None = Field(None, max_length=150, description="Generated in Stage 8")
    
    citations: list[Citation] = Field(..., min_length=1, max_length=3)
    confidence: float = Field(..., ge=0, le=1)
    needs_analyst_review: bool = False
    review_reason: str | None = None
    
    @validator('rationale_bullets')
    def bullets_not_empty(cls, v):
        if any(len(b.strip()) == 0 for b in v):
            raise ValueError("Rationale bullets cannot be empty strings")
        return v
```

### CallExtractionOutput

```python
class CallExtractionOutput(BaseModel):
    """Output of Stage 6: all calls from one document."""
    document_id: str
    allocation_calls: list[AllocationCall]
    overall_sentiment: Sentiment
    sentiment_rationale: list[str] = Field(..., min_length=1, max_length=3)
    sentiment_citations: list[Citation]
    sentiment_confidence: float = Field(..., ge=0, le=1)
    
    # Metadata
    extraction_timestamp: datetime
    model_version: str
    total_candidates_reviewed: int
```

---

## Summary Models (Stage 7)

### KeyTakeaway

```python
class KeyTakeaway(BaseModel):
    """Single takeaway bullet with evidence."""
    text: str = Field(..., max_length=200)
    citations: list[Citation] = Field(..., min_length=1)
```

### DocumentSummaries

```python
class DocumentSummaries(BaseModel):
    """All summaries for one document."""
    document_id: str
    
    executive_summary: str = Field(
        ..., 
        min_length=100, 
        max_length=1000,
        description="120-180 words, max 6 bullets"
    )
    
    search_descriptor: str = Field(
        ..., 
        min_length=50, 
        max_length=200,
        description="20-35 words: what + implication + focus"
    )
    
    key_takeaways: list[KeyTakeaway] = Field(
        ..., 
        min_length=3, 
        max_length=5
    )
    
    citations: list[Citation]
    confidence: float = Field(..., ge=0, le=1)
```

---

## Tag Models (Stage 9)

### TagSet

```python
class Tag(BaseModel):
    """Single normalized tag."""
    tag_type: TagType
    value: str
    confidence: float = Field(..., ge=0, le=1)
    source: str = Field(..., description="'rule' or 'llm'")

class TagSet(BaseModel):
    """All tags for one document."""
    document_id: str
    
    asset_class_tags: list[str]
    region_tags: list[str]
    theme_tags: list[str]
    risk_tags: list[str]
    instrument_tags: list[str]
    style_tags: list[str]
    macro_regime_tags: list[str]
    
    all_tags: list[Tag] = Field(default_factory=list, description="Denormalized for indexing")
    
    confidence: float = Field(..., ge=0, le=1)
```

---

## Confidence Models (Stage 10)

### FieldConfidence

```python
class FieldConfidence(BaseModel):
    """Confidence for a single extracted field."""
    field_name: str
    confidence: float = Field(..., ge=0, le=1)
    reasons: list[str]
    has_explicit_evidence: bool
    evidence_strength: float = Field(..., ge=0, le=1)
```

### ConfidenceResult

```python
class ConfidenceResult(BaseModel):
    """Overall confidence assessment for a document."""
    document_id: str
    
    extraction_coverage: float = Field(..., ge=0, le=1)
    overall_confidence: float = Field(..., ge=0, le=1)
    confidence_band: ConfidenceBand
    
    field_confidences: list[FieldConfidence]
    
    analyst_attention_required: bool
    attention_reasons: list[str]
    
    # Cross-pass agreement (if verification pass was run)
    verification_agreement: float | None = None
    disagreed_fields: list[str] = Field(default_factory=list)
```

---

## Final Pipeline Output

### ProcessedDocument

```python
class ProcessedDocument(BaseModel):
    """Complete output for one PDF."""
    document_id: str
    
    # From Stage 4
    profile: DocumentProfile
    
    # From Stage 6
    allocation_calls: list[AllocationCall]
    overall_sentiment: Sentiment
    sentiment_rationale: list[str]
    sentiment_citations: list[Citation]
    
    # From Stage 7
    summaries: DocumentSummaries
    
    # From Stage 9
    tags: TagSet
    
    # From Stage 10
    confidence: ConfidenceResult
    
    # Metadata
    processing_timestamp: datetime
    pipeline_version: str
    total_processing_time_seconds: float
    
    def to_allocator_pro_calls(self) -> list[dict]:
        """Format calls for Allocator Pro Module 1/2."""
        return [
            {
                "manager_name": self.profile.manager_name,
                "document_id": self.document_id,
                "as_of_date": (self.profile.as_of_date or self.profile.publication_date).isoformat(),
                "asset_class_category": call.asset_class_category,
                "sub_asset_class": call.sub_asset_class,
                "call": call.call.value,
                "rationale": call.rationale_bullets,
                "tooltip": call.tooltip_text,
            }
            for call in self.allocation_calls
        ]
    
    def to_search_document(self) -> dict:
        """Format for search index."""
        return {
            "document_id": self.document_id,
            "manager_name": self.profile.manager_name,
            "title": self.profile.title,
            "publication_date": self.profile.publication_date.isoformat() if self.profile.publication_date else None,
            "document_type": self.profile.document_type.value,
            "executive_summary": self.summaries.executive_summary,
            "search_descriptor": self.summaries.search_descriptor,
            "key_takeaways": [t.text for t in self.summaries.key_takeaways],
            "overall_sentiment": self.overall_sentiment.value,
            "asset_class_tags": self.tags.asset_class_tags,
            "region_tags": self.tags.region_tags,
            "theme_tags": self.tags.theme_tags,
            "risk_tags": self.tags.risk_tags,
            "calls": [
                {
                    "asset_class_category": c.asset_class_category,
                    "sub_asset_class": c.sub_asset_class,
                    "call": c.call.value,
                    "tooltip_text": c.tooltip_text,
                }
                for c in self.allocation_calls
            ],
        }
```

---

## Validation Rules

### Required Citations

The following fields **must** have non-empty `citations`:

| Model | Field |
|-------|-------|
| `DocumentProfile` | `citations` |
| `AllocationCall` | `citations` |
| `KeyTakeaway` | `citations` |
| `DocumentSummaries` | `citations` |

### Field Constraints

| Field | Constraint |
|-------|------------|
| `AllocationCall.rationale_bullets` | 1-4 items, each non-empty |
| `AllocationCall.tooltip_text` | ≤150 characters |
| `DocumentSummaries.executive_summary` | 100-1000 chars |
| `DocumentSummaries.search_descriptor` | 50-200 chars |
| `KeyTakeaway.text` | ≤200 chars |
| `Citation.text_span` | ≤200 chars |

### Confidence Thresholds

| Band | Range | Action |
|------|-------|--------|
| HIGH | ≥0.80 | Auto-publish |
| MEDIUM | 0.60-0.79 | Spot-check queue |
| LOW | <0.60 | Must-review |

---

## JSON Schema Export

All models support JSON Schema export for LLM prompts:

```python
# In LLM prompts, include the schema
schema = AllocationCall.model_json_schema()
prompt = f"""
Extract allocation calls matching this schema:
{json.dumps(schema, indent=2)}
"""
```
