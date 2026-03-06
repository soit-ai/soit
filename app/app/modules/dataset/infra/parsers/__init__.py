""" parsers

Document parsers for various formats.
"""

from typing import Dict, Type, Optional

from app.modules.dataset.infra.parsers.base import DocumentParser
from app.modules.dataset.infra.parsers.text import TextParser
from app.modules.dataset.infra.parsers.markdown import MarkdownParser
from app.modules.dataset.infra.parsers.pdf import PDFParser
from app.modules.dataset.infra.parsers.docx import DocxParser


# Registry for parsers
_parser_registry: Dict[str, Type[DocumentParser]] = {}


def register_parser(mime_type: str, parser_class: Type[DocumentParser]) -> None:
    """Register a document parser.
    
    Args:
        mime_type: MIME type (e.g., "application/pdf").
        parser_class: Parser class.
    """
    _parser_registry[mime_type] = parser_class


def get_parser(mime_type: str) -> Optional[Type[DocumentParser]]:
    """Get parser class for MIME type.
    
    Args:
        mime_type: MIME type.
        
    Returns:
        Parser class or None if not found.
    """
    return _parser_registry.get(mime_type)


# Register built-in parsers
register_parser("text/plain", TextParser)
register_parser("text/markdown", MarkdownParser)
register_parser("text/x-markdown", MarkdownParser)
register_parser("application/pdf", PDFParser)
register_parser(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocxParser,
)
register_parser("application/msword", DocxParser)
