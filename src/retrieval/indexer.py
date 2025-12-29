"""Per-document vector index for retrieval-grounded extraction.

This module provides chunking, embedding generation, and vector storage
for efficient retrieval of relevant document passages.
"""

import asyncio
import logging
from typing import Any, Protocol

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI

from src.config.settings import get_settings
from src.exceptions import ExtractionError
from src.models.pipeline import Chunk, CleanedDocument, RetrievedChunk

logger = logging.getLogger(__name__)

# Token estimation: ~4 characters per token
CHARS_PER_TOKEN = 4
TARGET_CHUNK_TOKENS = 300  # Target middle of 200-400 range
MAX_CHUNK_TOKENS = 400
MIN_CHUNK_TOKENS = 200


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider with retry logic."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int | None = 1536,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI API with retry."""
        max_retries = 3
        retry_delay = 1.0
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                if self.dimensions is None:
                    response = await self.client.embeddings.create(model=self.model, input=texts)
                else:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=texts,
                        dimensions=self.dimensions,
                    )
                return [embedding.embedding for embedding in response.data]

            except Exception as e:
                last_error = e
                if attempt == max_retries - 1:
                    logger.error(f"Embedding generation failed after {max_retries} attempts: {e}")
                    break  # Break to raise after loop

                logger.warning(
                    f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

        # Only raise after all retries exhausted
        raise ExtractionError(f"Failed to generate embeddings: {last_error}") from last_error


class DeepInfraEmbeddingProvider:
    """DeepInfra embedding provider (OpenAI-compatible endpoint) with retry logic."""

    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using DeepInfra OpenAI-compatible API with retry."""
        max_retries = 3
        retry_delay = 1.0
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    encoding_format="float",
                )
                return [embedding.embedding for embedding in response.data]

            except Exception as e:
                last_error = e
                if attempt == max_retries - 1:
                    logger.error(f"Embedding generation failed after {max_retries} attempts: {e}")
                    break

                logger.warning(
                    f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

        raise ExtractionError(f"Failed to generate embeddings: {last_error}") from last_error


def _get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embeddings_provider == "deepinfra":
        return DeepInfraEmbeddingProvider(
            api_key=settings.deepinfra_api_key.get_secret_value(),
            model=settings.deepinfra_embeddings_model,
            base_url=settings.deepinfra_embeddings_base_url,
        )

    openai_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    return OpenAIEmbeddingProvider(
        api_key=openai_key,
        model=settings.openai_embeddings_model,
        dimensions=settings.openai_embeddings_dimensions,
    )


def _split_large_block(
    block_text: str, block_id: str, page: int
) -> list[tuple[str, list[str], int]]:
    """Split a large block into smaller pieces that fit within token limits."""
    pieces: list[tuple[str, list[str], int]] = []
    words = block_text.split()
    current_piece: list[str] = []
    current_length = 0

    for word in words:
        word_length = len(word) + 1  # +1 for space

        # If adding this word would exceed max tokens, start new piece
        if current_length + word_length > MAX_CHUNK_TOKENS * CHARS_PER_TOKEN and current_piece:
            pieces.append((" ".join(current_piece), [block_id], page))
            current_piece = []
            current_length = 0

        current_piece.append(word)
        current_length += word_length

    # Add final piece if it has content
    if current_piece:
        pieces.append((" ".join(current_piece), [block_id], page))

    return pieces


def chunk_document(cleaned_doc: CleanedDocument) -> list[Chunk]:
    """Split document into chunks by section + paragraph boundaries.

    Args:
        cleaned_doc: Cleaned document with blocks and sections

    Returns:
        List of chunks with metadata
    """
    chunks: list[Chunk] = []
    chunk_index = 0

    # Group blocks by section for better chunking
    for section in cleaned_doc.sections:
        section_blocks = []

        # Collect all blocks in this section
        in_section = False
        for block in cleaned_doc.blocks:
            if block.block_id == section.start_block_id:
                in_section = True

            if in_section:
                # Skip disclaimer blocks
                if block.block_type.value == "DISCLAIMER":
                    continue

                section_blocks.append(block)

            if block.block_id == section.end_block_id:
                break

        if not section_blocks:
            continue

        # Build chunks within this section
        current_chunk_text_section = ""
        current_block_ids_section: list[str] = []
        current_page_section: int | None = None

        for block in section_blocks:
            block_text = block.text.strip()
            if not block_text:
                continue

            # Check if this single block is too large
            if len(block_text) > MAX_CHUNK_TOKENS * CHARS_PER_TOKEN:
                # Split large block into smaller pieces
                pieces = _split_large_block(block_text, block.block_id, block.page)

                for piece_text, piece_block_ids, piece_page in pieces:
                    # If we have current chunk content, save it first
                    if (
                        current_chunk_text_section
                        and len(current_chunk_text_section) >= MIN_CHUNK_TOKENS * CHARS_PER_TOKEN
                    ):
                        chunk = Chunk(
                            chunk_id=f"{cleaned_doc.document_id}_{chunk_index}",
                            block_ids=current_block_ids_section.copy(),
                            page=current_page_section or 1,
                            text=current_chunk_text_section.strip(),
                            section=section.title,
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                        current_chunk_text_section = ""
                        current_block_ids_section = []
                        current_page_section = None

                    # Create chunk from this piece
                    chunk = Chunk(
                        chunk_id=f"{cleaned_doc.document_id}_{chunk_index}",
                        block_ids=piece_block_ids,
                        page=piece_page,
                        text=piece_text,
                        section=section.title,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                continue  # Skip to next block

            # Start new chunk if adding this block would exceed max tokens
            if (
                current_chunk_text_section
                and len(current_chunk_text_section) + len(block_text)
                > MAX_CHUNK_TOKENS * CHARS_PER_TOKEN
            ):
                # Save current chunk if it has enough content
                if len(current_chunk_text_section) >= MIN_CHUNK_TOKENS * CHARS_PER_TOKEN:
                    chunk = Chunk(
                        chunk_id=f"{cleaned_doc.document_id}_{chunk_index}",
                        block_ids=current_block_ids_section.copy(),
                        page=current_page_section or 1,
                        text=current_chunk_text_section.strip(),
                        section=section.title,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                # Reset for new chunk
                current_chunk_text_section = ""
                current_block_ids_section = []
                current_page_section = None

            # Add block to current chunk
            if current_page_section is None:
                current_page_section = block.page

            if current_chunk_text_section:
                current_chunk_text_section += "\n\n" + block_text
            else:
                current_chunk_text_section = block_text

            current_block_ids_section.append(block.block_id)

        # Save final chunk for this section
        if (
            current_chunk_text_section
            and len(current_chunk_text_section) >= MIN_CHUNK_TOKENS * CHARS_PER_TOKEN
        ):
            chunk = Chunk(
                chunk_id=f"{cleaned_doc.document_id}_{chunk_index}",
                block_ids=current_block_ids_section,
                page=current_page_section or 1,
                text=current_chunk_text_section.strip(),
                section=section.title,
            )
            chunks.append(chunk)
            chunk_index += 1

    # Handle any remaining blocks not in sections (shouldn't happen with proper section detection)
    if not chunks:
        logger.warning("No chunks created from document sections, falling back to simple chunking")

        current_chunk_text = ""
        current_block_ids: list[str] = []
        current_page: int | None = None

        for block in cleaned_doc.blocks:
            # Skip disclaimer blocks
            if block.block_type.value == "DISCLAIMER":
                continue

            block_text = block.text.strip()
            if not block_text:
                continue

            if (
                current_chunk_text
                and len(current_chunk_text) + len(block_text) > MAX_CHUNK_TOKENS * CHARS_PER_TOKEN
            ):
                if len(current_chunk_text) >= MIN_CHUNK_TOKENS * CHARS_PER_TOKEN:
                    chunk = Chunk(
                        chunk_id=f"{cleaned_doc.document_id}_{chunk_index}",
                        block_ids=current_block_ids,
                        page=current_page or 1,
                        text=current_chunk_text.strip(),
                        section=None,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                current_chunk_text = ""
                current_block_ids = []
                current_page = None

            if current_page is None:
                current_page = block.page

            if current_chunk_text:
                current_chunk_text += "\n\n" + block_text
            else:
                current_chunk_text = block_text

            current_block_ids.append(block.block_id)

        if current_chunk_text and len(current_chunk_text) >= MIN_CHUNK_TOKENS * CHARS_PER_TOKEN:
            chunk = Chunk(
                chunk_id=f"{cleaned_doc.document_id}_{chunk_index}",
                block_ids=current_block_ids,
                page=current_page or 1,
                text=current_chunk_text.strip(),
                section=None,
            )
            chunks.append(chunk)

    # Log warning if too few chunks
    if len(chunks) < 5:
        logger.warning(
            f"Document {cleaned_doc.document_id} produced only {len(chunks)} chunks. "
            "This may indicate insufficient content for reliable retrieval."
        )

    logger.info(f"Created {len(chunks)} chunks from document {cleaned_doc.document_id}")
    return chunks


async def generate_embeddings(chunks: list[Chunk]) -> list[list[float]]:
    """Generate embeddings for chunks using OpenAI API.

    Retry logic is handled by the active embedding provider.

    Args:
        chunks: List of chunks to embed

    Returns:
        List of embedding vectors
    """
    if not chunks:
        return []

    provider = _get_embedding_provider()

    # Extract texts for embedding
    texts = [chunk.text for chunk in chunks]

    # Provider handles retries internally
    embeddings = await provider.generate_embeddings(texts)
    logger.info(f"Generated {len(embeddings)} embeddings for {len(chunks)} chunks")
    return embeddings


class DocumentIndex:
    """Per-document vector index using ChromaDB."""

    def __init__(self, document_id: str):
        self.document_id = document_id
        self.chroma_client = chromadb.Client(
            ChromaSettings(
                anonymized_telemetry=False,
                is_persistent=False,  # In-memory for per-document index
            )
        )
        self.collection = self.chroma_client.create_collection(
            name=f"doc_{document_id}",
            metadata={
                "document_id": document_id,
                "hnsw:space": "cosine",  # Use cosine distance for OpenAI embeddings
            },
        )
        self.chunks: list[Chunk] = []

    async def build(self, cleaned_doc: CleanedDocument) -> None:
        """Build index from cleaned document.

        Args:
            cleaned_doc: Cleaned document to index
        """
        logger.info(f"Building index for document {cleaned_doc.document_id}")

        # Chunk the document
        self.chunks = chunk_document(cleaned_doc)

        if not self.chunks:
            logger.warning(f"No chunks created for document {cleaned_doc.document_id}")
            return

        # Generate embeddings
        embeddings = await generate_embeddings(self.chunks)

        if len(embeddings) != len(self.chunks):
            raise ExtractionError(
                f"Embedding count mismatch: {len(embeddings)} embeddings for {len(self.chunks)} chunks"
            )

        # Add to ChromaDB collection
        # Cast embeddings to proper type for ChromaDB
        embeddings_cast: list[list[float]] = embeddings
        self.collection.add(
            ids=[chunk.chunk_id for chunk in self.chunks],
            embeddings=embeddings_cast,  # type: ignore[arg-type]
            documents=[chunk.text for chunk in self.chunks],
            metadatas=[
                {
                    "block_ids": ",".join(chunk.block_ids),  # Store as comma-separated string
                    "page": chunk.page,
                    "section": chunk.section or "",
                }
                for chunk in self.chunks
            ],
        )

        logger.info(
            f"Index built with {len(self.chunks)} chunks for document {cleaned_doc.document_id}"
        )

    async def query(
        self,
        query: str,
        top_k: int = 10,
        _filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Query index and return relevant chunks.

        Args:
            query: Search query text
            top_k: Number of top results to return
            _filters: Optional metadata filters (not implemented in MVP)

        Returns:
            List of retrieved chunks with similarity scores
        """
        if not self.chunks:
            logger.warning(f"Query on empty index for document {self.document_id}")
            return []

        # Generate embedding for query
        provider = _get_embedding_provider()

        query_embeddings = await provider.generate_embeddings([query])
        query_embedding = query_embeddings[0]

        # Query ChromaDB
        query_embeddings_cast: list[list[float]] = [query_embedding]
        results = self.collection.query(
            query_embeddings=query_embeddings_cast,  # type: ignore[arg-type]
            n_results=min(top_k, len(self.chunks)),
        )

        # Convert to RetrievedChunk objects
        retrieved_chunks: list[RetrievedChunk] = []

        if not results["ids"] or not results["ids"][0]:
            return []

        for i, chunk_id in enumerate(results["ids"][0]):
            # Find the original chunk
            chunk = next((c for c in self.chunks if c.chunk_id == chunk_id), None)
            if not chunk:
                logger.warning(f"Chunk {chunk_id} not found in stored chunks")
                continue

            # Get score (distance converted to similarity)
            distances = results["distances"]
            if distances is None:
                logger.warning(f"No distances returned for chunk {chunk_id}")
                continue
            distance = distances[0][i]
            # Convert cosine distance to similarity score (0-1 range)
            # Cosine distance is in [0, 2]; similarity = 1 - distance/2 but we use 1 - distance
            # since ChromaDB returns normalized values in [0, 1] for cosine space
            score = max(0.0, 1.0 - distance)

            retrieved_chunk = RetrievedChunk(
                chunk_id=chunk_id,
                block_ids=chunk.block_ids,
                page=chunk.page,
                text=chunk.text,
                score=score,
                section=chunk.section,
            )
            retrieved_chunks.append(retrieved_chunk)

        logger.info(
            f"Query returned {len(retrieved_chunks)} chunks for document {self.document_id}"
        )
        return retrieved_chunks
