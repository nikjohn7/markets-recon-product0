"""Stage 2: Text cleaning and section detection.

This stage removes boilerplate, normalizes text, detects disclaimers,
and identifies document sections.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from math import ceil

from src.exceptions import ExtractionError
from src.models.document import DocumentBlock, DocumentJSON
from src.models.enums import BlockType
from src.models.pipeline import CleanedDocument, Section

logger = logging.getLogger(__name__)

# Disclaimer patterns
DISCLAIMER_PATTERNS = [
    r"(?i)this document is for informational purposes",
    r"(?i)past performance",
    r"(?i)not a recommendation",
    r"(?i)important disclosure",
    r"(?i)confidential",
    r"(?i)forward-looking statements",
    r"(?i)disclaimer",
]

# Section heading patterns
SECTION_PATTERNS = {
    "macro": r"(?i)(macro|economic outlook|market outlook|global outlook)",
    "equities": r"(?i)(equities?|equity outlook|stock market)",
    "fixed_income": r"(?i)(fixed income|bonds?|credit|fixed rate)",
    "risks": r"(?i)(risks?|risk factors|downside)",
    "appendix": r"(?i)(appendix|appendices|glossary|definitions)",
}

# =============================================================================
# Page triage (cheap heuristics for large clean PDFs)
# =============================================================================

TRIAGE_HIGH_VALUE_HEADERS: dict[str, re.Pattern[str]] = {
    "executive_summary": re.compile(r"(?i)\bexecutive summary\b"),
    "asset_allocation": re.compile(r"(?i)\b(asset allocation|allocation)\b"),
    "outlook": re.compile(r"(?i)\b(outlook|our views|house view)\b"),
    "positioning": re.compile(r"(?i)\b(positioning|recommended positioning|portfolio positioning)\b"),
    "recommendations": re.compile(r"(?i)\b(recommendations?|what we like|what we don'?t like)\b"),
}

TRIAGE_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "overweight",
    "underweight",
    "neutral weight",
    "equal weight",
    "market weight",
    "bullish",
    "bearish",
    "upgrade",
    "downgrade",
    "increase",
    "decrease",
    "reduce",
    "trim",
    "adding",
    "reducing",
    "increasing",
    "decreasing",
    "allocation",
    "exposure",
    "tactical",
    "strategic",
)

TRIAGE_WORD_BOUNDARY_KEYWORDS: tuple[str, ...] = ("ow", "uw", "n", "add")

TRIAGE_BOILERPLATE_PAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\btable of contents\b"),
    re.compile(r"(?i)\bcontents\b"),
    re.compile(r"(?i)\bdisclaimer\b"),
    re.compile(r"(?i)\bimportant (information|disclosure)\b"),
)

_TRIAGE_WORD_BOUNDARY_PATTERNS: dict[str, re.Pattern[str]] = {
    keyword: re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    for keyword in TRIAGE_WORD_BOUNDARY_KEYWORDS
}


@dataclass(frozen=True)
class PageScore:
    """Cheap per-page scoring result used for triage selection."""

    page: int
    score: float
    keyword_hits_total: int
    keyword_hits_unique: int
    header_hits: tuple[str, ...]
    bullet_block_count: int
    table_cell_block_count: int
    position_prior: float
    boilerplate_penalty: float


@dataclass(frozen=True)
class PageTriageConfig:
    """Configuration for heuristic page triage in Stage 2."""

    enabled: bool = True
    min_page_count: int = 40
    max_pages: int = 40
    always_keep_first_pages: int = 5
    always_keep_unique_keyword_threshold: int = 3
    keep_header_pages: bool = True
    neighbor_window: int = 1
    segment_count: int = 4


def _count_keyword_hits(text_lower: str) -> tuple[int, int]:
    """Return (total_hits, unique_hits) for triage signal keywords."""
    total_hits = 0
    unique_hits = 0

    for keyword in TRIAGE_SIGNAL_KEYWORDS:
        count = text_lower.count(keyword)
        if count > 0:
            unique_hits += 1
            total_hits += count

    for keyword, pattern in _TRIAGE_WORD_BOUNDARY_PATTERNS.items():
        matches = pattern.findall(text_lower)
        if matches:
            unique_hits += 1
            total_hits += len(matches)

    return total_hits, unique_hits


def _detect_header_hits(page_blocks: list[DocumentBlock]) -> tuple[str, ...]:
    """Detect high-value header terms on a page.

    Uses heading blocks first; falls back to the top few blocks.
    """
    heading_text = " ".join(
        block.text for block in page_blocks if block.block_type == BlockType.HEADING
    ).lower()
    top_text = " ".join(block.text for block in page_blocks[:3]).lower()
    candidate = f"{heading_text}\n{top_text}"

    hits = [name for name, pattern in TRIAGE_HIGH_VALUE_HEADERS.items() if pattern.search(candidate)]
    return tuple(sorted(hits))


def _compute_position_prior(page: int, page_count: int) -> float:
    """Light position prior: boost front and mid-document pages modestly."""
    if page_count <= 1:
        return 0.0

    percentile = (page - 1) / (page_count - 1)
    if percentile <= 0.20:
        return 0.50
    if 0.35 <= percentile <= 0.70:
        return 0.30
    return 0.0


def _compute_boilerplate_penalty(page_text: str) -> float:
    """Downweight pages that look like TOC/disclaimer boilerplate."""
    text = page_text.strip()
    if not text:
        return 0.0

    penalty = 0.0
    for pattern in TRIAGE_BOILERPLATE_PAGE_PATTERNS:
        if pattern.search(text):
            penalty = max(penalty, 1.0)
    return penalty


def _score_pages(page_count: int, blocks: list[DocumentBlock]) -> list[PageScore]:
    """Compute cheap triage scores for all pages in the document."""
    blocks_by_page: dict[int, list[DocumentBlock]] = defaultdict(list)
    for block in blocks:
        blocks_by_page[block.page].append(block)

    results: list[PageScore] = []
    for page in range(1, page_count + 1):
        page_blocks = blocks_by_page.get(page, [])
        page_text = "\n".join(block.text for block in page_blocks).lower()

        keyword_total, keyword_unique = _count_keyword_hits(page_text)
        header_hits = _detect_header_hits(page_blocks)
        bullet_blocks = sum(1 for block in page_blocks if block.block_type == BlockType.BULLET)
        table_cells = sum(1 for block in page_blocks if block.block_type == BlockType.TABLE_CELL)
        position_prior = _compute_position_prior(page, page_count)
        boilerplate_penalty = _compute_boilerplate_penalty(page_text)

        header_score = 2.0 if header_hits else 0.0
        keyword_score = min(3.0, keyword_unique * 0.9 + min(2.0, keyword_total * 0.15))
        structure_score = min(1.5, bullet_blocks * 0.10 + (1.0 if table_cells >= 20 else 0.0))
        position_score = position_prior
        penalty = boilerplate_penalty * 1.5

        score = header_score + keyword_score + structure_score + position_score - penalty

        results.append(
            PageScore(
                page=page,
                score=score,
                keyword_hits_total=keyword_total,
                keyword_hits_unique=keyword_unique,
                header_hits=header_hits,
                bullet_block_count=bullet_blocks,
                table_cell_block_count=table_cells,
                position_prior=position_prior,
                boilerplate_penalty=boilerplate_penalty,
            )
        )

    return results


def _expand_neighbors(pages: set[int], page_count: int, window: int) -> set[int]:
    if window <= 0:
        return set(pages)

    expanded = set(pages)
    for page in list(pages):
        for offset in range(1, window + 1):
            if page - offset >= 1:
                expanded.add(page - offset)
            if page + offset <= page_count:
                expanded.add(page + offset)
    return expanded


def _select_pages_for_triage(page_scores: list[PageScore], config: PageTriageConfig) -> list[int]:
    """Select pages to keep using guardrails + top-N scoring.

    Designed to be high-recall: always keep early pages and strongly signaled pages,
    then fill remaining slots with the highest-scoring pages with light coverage constraints.
    """
    if not page_scores:
        return []

    page_count = len(page_scores)
    max_pages = max(1, min(config.max_pages, page_count))
    first_pages = max(0, min(config.always_keep_first_pages, page_count))

    must_keep = set(range(1, first_pages + 1))

    guardrail_pages: set[int] = set(must_keep)
    for page_score in page_scores:
        if config.keep_header_pages and page_score.header_hits:
            guardrail_pages.add(page_score.page)
        if page_score.keyword_hits_unique >= config.always_keep_unique_keyword_threshold:
            guardrail_pages.add(page_score.page)

    guardrail_pages = _expand_neighbors(guardrail_pages, page_count, config.neighbor_window)

    scores_by_page = {s.page: s for s in page_scores}

    # If guardrails exceed the cap, keep must-keep pages and then highest-scoring guardrail pages.
    if len(guardrail_pages) >= max_pages:
        remaining_guardrails = sorted(
            (p for p in guardrail_pages if p not in must_keep),
            key=lambda p: scores_by_page[p].score,
            reverse=True,
        )
        kept = set(must_keep)
        for page in remaining_guardrails:
            if len(kept) >= max_pages:
                break
            kept.add(page)
        return sorted(kept)

    kept_pages = set(guardrail_pages)
    remaining_slots = max_pages - len(kept_pages)

    candidate_pages = [s.page for s in page_scores if s.page not in kept_pages]
    candidate_pages.sort(key=lambda p: scores_by_page[p].score, reverse=True)

    if remaining_slots <= 0:
        return sorted(kept_pages)

    # Light coverage: take top pages from each segment, then fill remaining globally.
    segment_count = max(1, config.segment_count)
    if segment_count > 1 and candidate_pages:
        slots_per_segment = max(1, ceil(remaining_slots / segment_count))
        segment_size = ceil(page_count / segment_count)

        for segment_idx in range(segment_count):
            if remaining_slots <= 0:
                break
            start_page = segment_idx * segment_size + 1
            end_page = min(page_count, (segment_idx + 1) * segment_size)
            segment_candidates = [
                p for p in candidate_pages if start_page <= p <= end_page and p not in kept_pages
            ]
            segment_candidates.sort(key=lambda p: scores_by_page[p].score, reverse=True)
            for page in segment_candidates[:slots_per_segment]:
                if remaining_slots <= 0:
                    break
                kept_pages.add(page)
                remaining_slots -= 1

    if remaining_slots > 0:
        for page in candidate_pages:
            if remaining_slots <= 0:
                break
            if page in kept_pages:
                continue
            kept_pages.add(page)
            remaining_slots -= 1

    return sorted(kept_pages)


def _filter_blocks_to_pages(blocks: list[DocumentBlock], pages_to_keep: set[int]) -> list[DocumentBlock]:
    return [block for block in blocks if block.page in pages_to_keep]


def _normalize_text(text: str) -> str:
    """Normalize text: fix hyphenation, whitespace."""
    # Fix hyphenation across line breaks
    text = re.sub(r"-\n", "", text)
    # Normalize whitespace
    text = re.sub(r" +", " ", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def _is_disclaimer(text: str) -> bool:
    """Check if text matches disclaimer patterns."""
    return any(re.search(pattern, text) for pattern in DISCLAIMER_PATTERNS)


def _detect_boilerplate(blocks: list[DocumentBlock]) -> set[int]:
    """Detect repeated headers/footers across consecutive pages.

    Returns set of block indices to remove.
    """
    removed_indices: set[int] = set()

    # Group blocks by page
    blocks_by_page: dict[int, list[tuple[int, DocumentBlock]]] = defaultdict(list)
    for idx, block in enumerate(blocks):
        blocks_by_page[block.page].append((idx, block))

    # Find repeated text at similar positions across 3+ consecutive pages
    pages = sorted(blocks_by_page.keys())

    for i in range(len(pages) - 2):
        page1, page2, page3 = pages[i], pages[i + 1], pages[i + 2]

        # Compare first block of each page (header)
        if blocks_by_page[page1] and blocks_by_page[page2] and blocks_by_page[page3]:
            _idx1, block1 = blocks_by_page[page1][0]
            idx2, block2 = blocks_by_page[page2][0]
            idx3, block3 = blocks_by_page[page3][0]

            if block1.text == block2.text == block3.text and block1.block_type in (
                BlockType.HEADING,
                BlockType.PARAGRAPH,
            ):
                # Mark duplicates for removal, keep first
                removed_indices.add(idx2)
                removed_indices.add(idx3)

        # Compare last block of each page (footer)
        if blocks_by_page[page1] and blocks_by_page[page2] and blocks_by_page[page3]:
            _idx1, block1 = blocks_by_page[page1][-1]
            idx2, block2 = blocks_by_page[page2][-1]
            idx3, block3 = blocks_by_page[page3][-1]

            if block1.text == block2.text == block3.text and block1.block_type in (
                BlockType.HEADING,
                BlockType.PARAGRAPH,
            ):
                removed_indices.add(idx2)
                removed_indices.add(idx3)

    return removed_indices


def _classify_section(text: str) -> str | None:
    """Classify section type based on heading text."""
    for section_type, pattern in SECTION_PATTERNS.items():
        if re.search(pattern, text):
            return section_type
    return None


def _detect_sections(document_id: str, blocks: list[DocumentBlock]) -> list[Section]:
    """Detect section boundaries based on headings."""
    if not blocks:
        return []

    sections: list[Section] = []
    current_section_start = 0
    current_section_title: str | None = None
    current_section_type: str | None = None

    for idx, block in enumerate(blocks):
        # Check if this is a heading
        if block.block_type == BlockType.HEADING:
            # Save previous section if exists
            if idx > current_section_start:
                section = Section(
                    section_id=f"{document_id}_sec_{len(sections)}",
                    title=current_section_title,
                    start_block_id=blocks[current_section_start].block_id,
                    end_block_id=blocks[idx - 1].block_id,
                    section_type=current_section_type,
                )
                sections.append(section)

            # Start new section
            current_section_start = idx
            current_section_title = block.text
            current_section_type = _classify_section(block.text)

    # Add final section
    if current_section_start < len(blocks):
        section = Section(
            section_id=f"{document_id}_sec_{len(sections)}",
            title=current_section_title,
            start_block_id=blocks[current_section_start].block_id,
            end_block_id=blocks[-1].block_id,
            section_type=current_section_type,
        )
        sections.append(section)

    # If no sections detected, create one covering all blocks
    if not sections:
        section = Section(
            section_id=f"{document_id}_sec_0",
            title=None,
            start_block_id=blocks[0].block_id,
            end_block_id=blocks[-1].block_id,
            section_type=None,
        )
        sections.append(section)

    return sections


async def stage_clean(
    doc_json: DocumentJSON,
    triage_config: PageTriageConfig | None = None,
) -> CleanedDocument:
    """Clean extracted document and detect sections.

    Args:
        doc_json: DocumentJSON from Stage 1
        triage_config: Optional page triage configuration override

    Returns:
        CleanedDocument with cleaned blocks and detected sections

    Raises:
        ExtractionError: If cleaning fails
    """
    logger.info(f"Starting Stage 2 cleaning for document {doc_json.document_id}")

    try:
        # Normalize all block text
        normalized_blocks = []
        for block in doc_json.blocks:
            normalized_text = _normalize_text(block.text)
            normalized_block = block.model_copy(update={"text": normalized_text})
            normalized_blocks.append(normalized_block)

        # Detect and remove boilerplate
        boilerplate_indices = _detect_boilerplate(normalized_blocks)
        cleaned_blocks = [
            block for idx, block in enumerate(normalized_blocks) if idx not in boilerplate_indices
        ]

        removed_count = len(boilerplate_indices)
        logger.info(f"Removed {removed_count} boilerplate blocks")

        # Check boilerplate ratio
        if len(doc_json.blocks) > 0:
            boilerplate_ratio = removed_count / len(doc_json.blocks)
            if boilerplate_ratio > 0.3:
                logger.warning(
                    f"High boilerplate ratio: {boilerplate_ratio:.2%}. "
                    f"Document may have unusual structure."
                )

        # Optional page triage: filter pages before downstream chunking/embedding.
        # Only applies to large clean PDFs (no OCR/vision pages).
        active_triage_config = triage_config or PageTriageConfig()
        is_clean_pdf = not doc_json.ocr_pages and not doc_json.vision_pages
        if not is_clean_pdf and active_triage_config.enabled:
            logger.debug(
                "Stage 2 page triage skipped: document has OCR/vision pages "
                "(ocr=%d, vision=%d)",
                len(doc_json.ocr_pages),
                len(doc_json.vision_pages),
            )
        if (
            active_triage_config.enabled
            and is_clean_pdf
            and doc_json.page_count >= active_triage_config.min_page_count
        ):
            page_scores = _score_pages(doc_json.page_count, cleaned_blocks)
            selected_pages = _select_pages_for_triage(page_scores, active_triage_config)
            selected_set = set(selected_pages)

            if len(selected_set) < doc_json.page_count:
                scores_by_page = {s.page: s for s in page_scores}
                header_pages_selected = sum(1 for p in selected_set if scores_by_page[p].header_hits)
                strong_keyword_pages_selected = sum(
                    1
                    for p in selected_set
                    if scores_by_page[p].keyword_hits_unique
                    >= active_triage_config.always_keep_unique_keyword_threshold
                )
                top_pages = sorted(selected_set, key=lambda p: scores_by_page[p].score, reverse=True)[
                    :5
                ]
                top_summary = ", ".join(
                    (
                        f"p{p}:s={scores_by_page[p].score:.2f}"
                        f" kw={scores_by_page[p].keyword_hits_unique}"
                        f" hdr={'+'.join(scores_by_page[p].header_hits) or '-'}"
                    )
                    for p in top_pages
                )
                before_blocks = len(cleaned_blocks)
                cleaned_blocks = _filter_blocks_to_pages(cleaned_blocks, selected_set)
                after_blocks = len(cleaned_blocks)
                logger.info(
                    "Stage 2 page triage kept %d/%d pages (max=%d, min_pages=%d), blocks %d→%d",
                    len(selected_set),
                    doc_json.page_count,
                    active_triage_config.max_pages,
                    active_triage_config.min_page_count,
                    before_blocks,
                    after_blocks,
                )
                logger.info(
                    "Stage 2 page triage summary: header_pages=%d strong_keyword_pages=%d top=%s",
                    header_pages_selected,
                    strong_keyword_pages_selected,
                    top_summary,
                )

        # Find disclaimer block
        disclaimer_block_id: str | None = None
        for block in cleaned_blocks:
            if _is_disclaimer(block.text):
                block.block_type = BlockType.DISCLAIMER
                if disclaimer_block_id is None:
                    disclaimer_block_id = block.block_id

        # Detect sections
        sections = _detect_sections(doc_json.document_id, cleaned_blocks)
        logger.info(f"Detected {len(sections)} sections")

        # Create cleaned document
        cleaned_doc = CleanedDocument(
            document_id=doc_json.document_id,
            blocks=cleaned_blocks,
            sections=sections,
            removed_boilerplate_count=removed_count,
            disclaimer_block_id=disclaimer_block_id,
        )

        logger.info(
            f"Stage 2 complete: {len(cleaned_blocks)} blocks, "
            f"{len(sections)} sections, {removed_count} boilerplate removed"
        )

        return cleaned_doc

    except Exception as e:
        logger.error(f"Stage 2 cleaning failed: {e}")
        raise ExtractionError(f"Failed to clean document: {e}") from e
