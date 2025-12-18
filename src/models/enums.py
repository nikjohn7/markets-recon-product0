"""Core enums for the Markets Recon pipeline.

All enums inherit from (str, Enum) for JSON serialization compatibility.
"""

from enum import Enum


class CallDirection(str, Enum):
    """Asset allocation positioning direction."""
    OVERWEIGHT = "OVERWEIGHT"
    NEUTRAL = "NEUTRAL"
    UNDERWEIGHT = "UNDERWEIGHT"
    UNCERTAIN = "UNCERTAIN"


class Conviction(str, Enum):
    """Conviction level for allocation calls."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Sentiment(str, Enum):
    """Overall document sentiment."""
    NET_POSITIVE = "NET_POSITIVE"
    NEUTRAL = "NEUTRAL"
    NET_NEGATIVE = "NET_NEGATIVE"


class DocumentType(str, Enum):
    """Type of fund manager document."""
    ANNUAL_OUTLOOK = "ANNUAL_OUTLOOK"
    MID_YEAR_OUTLOOK = "MID_YEAR_OUTLOOK"
    QUARTERLY_OUTLOOK = "QUARTERLY_OUTLOOK"
    THEMATIC_NOTE = "THEMATIC_NOTE"
    ASSET_CLASS_UPDATE = "ASSET_CLASS_UPDATE"
    OTHER = "OTHER"


class BlockType(str, Enum):
    """Type of content block extracted from PDF."""
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    BULLET = "BULLET"
    TABLE_CELL = "TABLE_CELL"
    CHART_TEXT = "CHART_TEXT"
    FOOTNOTE = "FOOTNOTE"
    DISCLAIMER = "DISCLAIMER"


class ConfidenceBand(str, Enum):
    """Confidence band for routing decisions.
    
    HIGH: ≥0.80 - Auto-publish
    MEDIUM: 0.60–0.79 - Spot-check queue
    LOW: <0.60 - Must-review
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DocumentStatus(str, Enum):
    """Processing status of a document."""
    PENDING = "pending"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    PUBLISHED = "published"
    FAILED = "failed"


class TagType(str, Enum):
    """Category of document tag."""
    ASSET_CLASS = "ASSET_CLASS"
    REGION = "REGION"
    THEME = "THEME"
    RISK = "RISK"
    INSTRUMENT = "INSTRUMENT"
    STYLE = "STYLE"
    MACRO_REGIME = "MACRO_REGIME"


class IndicatorDirection(str, Enum):
    """Direction of economic/market indicator."""
    RISING = "RISING"
    FALLING = "FALLING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
