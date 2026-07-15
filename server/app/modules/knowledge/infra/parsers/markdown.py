""" markdown

Markdown parser.
"""


from app.modules.knowledge.infra.parsers.base import DocumentParser, ParsedDocument


class MarkdownParser(DocumentParser):
    """Parser for Markdown files."""

    async def parse(
        self,
        content: bytes,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> ParsedDocument:
        """Parse Markdown content.

        Args:
            content: Markdown content bytes.
            mime_type: Optional MIME type.
            filename: Optional filename.

        Returns:
            ParsedDocument instance.
        """
        # Decode text
        text = content.decode("utf-8")

        # Extract metadata if present (frontmatter)
        metadata = {
            "char_count": len(text),
            "line_count": text.count("\n") + 1,
        }

        # Try to extract title from first heading
        lines = text.split("\n")
        for line in lines[:10]:  # Check first 10 lines
            if line.startswith("#"):
                metadata["title"] = line.lstrip("#").strip()
                break

        return ParsedDocument(
            text=text,  # Keep original markdown for now
            metadata=metadata,
        )

    def supports(self, mime_type: str) -> bool:
        """Check if supports MIME type."""
        return mime_type in ("text/markdown", "text/x-markdown")
