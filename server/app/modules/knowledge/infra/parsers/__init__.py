""" parsers

Document parsers for various formats.
"""

from app.modules.knowledge.infra.parsers.base import DocumentParser
from app.modules.knowledge.infra.parsers.docling import DoclingParser
from app.modules.knowledge.infra.parsers.markdown import MarkdownParser
from app.modules.knowledge.infra.parsers.text import TextParser

# Registry for parsers
_parser_registry: dict[str, type[DocumentParser]] = {}


def register_parser(mime_type: str, parser_class: type[DocumentParser]) -> None:
    """Register a document parser.

    Args:
        mime_type: MIME type (e.g., "application/pdf").
        parser_class: Parser class.
    """
    _parser_registry[mime_type] = parser_class


def get_parser(mime_type: str) -> type[DocumentParser] | None:
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
for rich_mime_type in DoclingParser.SUPPORTED_MIME_TYPES:
    register_parser(rich_mime_type, DoclingParser)
