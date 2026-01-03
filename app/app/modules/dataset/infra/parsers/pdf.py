""" pdf

PDF parser.
"""

from typing import Optional
from pypdf import PdfReader
from io import BytesIO

from app.modules.dataset.infra.parsers.base import DocumentParser, ParsedDocument


class PDFParser(DocumentParser):
    """Parser for PDF files."""
    
    async def parse(
        self,
        content: bytes,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> ParsedDocument:
        """Parse PDF content.
        
        Args:
            content: PDF content bytes.
            mime_type: Optional MIME type.
            filename: Optional filename.
            
        Returns:
            ParsedDocument instance.
        """
        pdf_file = BytesIO(content)
        reader = PdfReader(pdf_file)
        
        # Extract text from all pages
        pages_text = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            pages_text.append(text)
        
        full_text = "\n\n".join(pages_text)
        
        # Extract metadata
        metadata = {
            "page_count": len(reader.pages),
            "char_count": len(full_text),
        }
        
        # Try to extract title from metadata
        if reader.metadata and reader.metadata.title:
            metadata["title"] = reader.metadata.title
        
        return ParsedDocument(
            text=full_text,
            metadata=metadata,
        )
    
    def supports(self, mime_type: str) -> bool:
        """Check if supports MIME type."""
        return mime_type == "application/pdf"

