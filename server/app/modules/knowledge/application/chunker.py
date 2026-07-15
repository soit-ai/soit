""" chunker

Text chunker with various strategies.
"""

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass
class Chunk:
    """Text chunk with metadata."""

    text: str
    """Chunk text."""

    chunk_no: int
    """Chunk number (0-indexed)."""

    start_offset: int | None = None
    """Start character offset."""

    end_offset: int | None = None
    """End character offset."""

    page_no: int | None = None
    """Page number."""

    section_path: list[str] | None = None
    """Section path (e.g., ["H1", "H2"])."""

    metadata: dict[str, Any] | None = None
    """Additional metadata."""


class TextChunker:
    """Text chunker with configurable strategies."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ):
        """Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters.
            chunk_overlap: Overlap size between chunks.
            separators: List of separators for splitting (priority order).
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def chunk(
        self,
        text: str,
        page_no: int | None = None,
        section_path: list[str] | None = None,
    ) -> list[Chunk]:
        """Chunk text into chunks.

        Args:
            text: Text to chunk.
            page_no: Optional page number.
            section_path: Optional section path.

        Returns:
            List of Chunk instances.
        """
        chunks = []
        current_offset = 0

        while current_offset < len(text):
            # Determine chunk end
            chunk_end = min(current_offset + self.chunk_size, len(text))

            # Try to split at separator
            chunk_text = text[current_offset:chunk_end]

            # If not at end of text, try to find separator
            if chunk_end < len(text):
                # Look for separator in overlap region
                overlap_start = max(0, chunk_end - self.chunk_overlap)
                overlap_text = text[overlap_start:chunk_end + 100]  # Look ahead

                best_split = -1
                for separator in self.separators:
                    if separator:
                        # Find last occurrence of separator in overlap region
                        idx = overlap_text.rfind(separator)
                        if idx != -1:
                            idx += overlap_start
                            if idx > current_offset:
                                best_split = idx + len(separator)
                                break

                if best_split > current_offset:
                    chunk_end = best_split
                    chunk_text = text[current_offset:chunk_end]

            # Create chunk
            chunk = Chunk(
                text=chunk_text.strip(),
                chunk_no=len(chunks),
                start_offset=current_offset,
                end_offset=chunk_end,
                page_no=page_no,
                section_path=section_path.copy() if section_path else None,
            )

            chunks.append(chunk)

            # Move to next chunk (with overlap)
            if chunk_end >= len(text):
                break
            current_offset = max(current_offset + 1, chunk_end - self.chunk_overlap)

        return chunks

    @staticmethod
    def generate_chunk_key(doc_key: str, version: int, chunk_no: int) -> str:
        """Generate stable chunk key.

        Args:
            doc_key: Document key.
            version: Document version.
            chunk_no: Chunk number.

        Returns:
            Chunk key string.
        """
        return f"{doc_key}:v{version}:chunk{chunk_no}"

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Compute content hash for chunk.

        Args:
            text: Chunk text.

        Returns:
            SHA256 hash hex string.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
