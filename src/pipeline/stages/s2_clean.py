"""Stage 2: Text cleaning and section detection.

This stage removes boilerplate, normalizes text, detects disclaimers,
and identifies document sections.
"""

import logging
import re
from collections import defaultdict

from src.models.document import DocumentJSON, DocumentBlock
from src.models.pipeline import CleanedDocument, Section
from src.models.enums import BlockType
from src.exceptions import ExtractionError

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
    for pattern in DISCLAIMER_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


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
        if (blocks_by_page[page1] and blocks_by_page[page2] and 
            blocks_by_page[page3]):
            idx1, block1 = blocks_by_page[page1][0]
            idx2, block2 = blocks_by_page[page2][0]
            idx3, block3 = blocks_by_page[page3][0]
            
            if (block1.text == block2.text == block3.text and 
                block1.block_type in (BlockType.HEADING, BlockType.PARAGRAPH)):
                # Mark duplicates for removal, keep first
                removed_indices.add(idx2)
                removed_indices.add(idx3)
        
        # Compare last block of each page (footer)
        if (blocks_by_page[page1] and blocks_by_page[page2] and 
            blocks_by_page[page3]):
            idx1, block1 = blocks_by_page[page1][-1]
            idx2, block2 = blocks_by_page[page2][-1]
            idx3, block3 = blocks_by_page[page3][-1]
            
            if (block1.text == block2.text == block3.text and 
                block1.block_type in (BlockType.HEADING, BlockType.PARAGRAPH)):
                removed_indices.add(idx2)
                removed_indices.add(idx3)
    
    return removed_indices


def _classify_section(text: str) -> str | None:
    """Classify section type based on heading text."""
    for section_type, pattern in SECTION_PATTERNS.items():
        if re.search(pattern, text):
            return section_type
    return None


def _detect_sections(blocks: list[DocumentBlock]) -> list[Section]:
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
                    section_id=f"{blocks[0].block_id.split('_')[0]}_sec_{len(sections)}",
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
            section_id=f"{blocks[0].block_id.split('_')[0]}_sec_{len(sections)}",
            title=current_section_title,
            start_block_id=blocks[current_section_start].block_id,
            end_block_id=blocks[-1].block_id,
            section_type=current_section_type,
        )
        sections.append(section)
    
    # If no sections detected, create one covering all blocks
    if not sections:
        section = Section(
            section_id=f"{blocks[0].block_id.split('_')[0]}_sec_0",
            title=None,
            start_block_id=blocks[0].block_id,
            end_block_id=blocks[-1].block_id,
            section_type=None,
        )
        sections.append(section)
    
    return sections


async def stage_clean(doc_json: DocumentJSON) -> CleanedDocument:
    """Clean extracted document and detect sections.
    
    Args:
        doc_json: DocumentJSON from Stage 1
        
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
            block for idx, block in enumerate(normalized_blocks)
            if idx not in boilerplate_indices
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
        
        # Find disclaimer block
        disclaimer_block_id: str | None = None
        for block in cleaned_blocks:
            if _is_disclaimer(block.text):
                block.block_type = BlockType.DISCLAIMER
                if disclaimer_block_id is None:
                    disclaimer_block_id = block.block_id
        
        # Detect sections
        sections = _detect_sections(cleaned_blocks)
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
