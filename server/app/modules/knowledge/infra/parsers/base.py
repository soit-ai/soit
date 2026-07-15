""" base

Base document parser interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedDocument:
    """Parsed document result."""

    text: str
    """Extracted text content."""

    metadata: dict[str, Any]
    """Document metadata (pages, title, language, etc.)."""

    structured_data: dict[str, Any] | None = None
    """Structured data (tables, images, etc.)."""


class DocumentParser(ABC):
    """Base class for document parsers."""

    @abstractmethod
    async def parse(
        self,
        content: bytes,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> ParsedDocument:
        """Parse document content.

        Args:
            content: Document content bytes.
            mime_type: Optional MIME type.
            filename: Optional filename.

        Returns:
            ParsedDocument instance.
        """
        pass

    def supports(self, mime_type: str) -> bool:
        """Check if parser supports MIME type.

        Args:
            mime_type: MIME type.

        Returns:
            True if supported.
        """
        return False

