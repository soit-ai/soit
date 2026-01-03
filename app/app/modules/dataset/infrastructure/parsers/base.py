""" base

Base document parser interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ParsedDocument:
    """Parsed document result."""
    
    text: str
    """Extracted text content."""
    
    metadata: Dict[str, Any]
    """Document metadata (pages, title, language, etc.)."""
    
    structured_data: Optional[Dict[str, Any]] = None
    """Structured data (tables, images, etc.)."""


class DocumentParser(ABC):
    """Base class for document parsers."""
    
    @abstractmethod
    async def parse(
        self,
        content: bytes,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
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

