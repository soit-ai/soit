""" text

Plain text parser.
"""

from typing import Optional
from app.modules.dataset.infrastructure.parsers.base import DocumentParser, ParsedDocument


class TextParser(DocumentParser):
    """Parser for plain text files."""
    
    async def parse(
        self,
        content: bytes,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> ParsedDocument:
        """Parse plain text content.
        
        Args:
            content: Text content bytes.
            mime_type: Optional MIME type.
            filename: Optional filename.
            
        Returns:
            ParsedDocument instance.
        """
        # Decode text
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            # Try other encodings
            try:
                text = content.decode("gbk")
            except UnicodeDecodeError:
                text = content.decode("utf-8", errors="ignore")
        
        metadata = {
            "encoding": "utf-8",
            "char_count": len(text),
            "line_count": text.count("\n") + 1,
        }
        
        return ParsedDocument(
            text=text,
            metadata=metadata,
        )
    
    def supports(self, mime_type: str) -> bool:
        """Check if supports MIME type."""
        return mime_type in ("text/plain", "text/txt")

