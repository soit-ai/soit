"""Tests for the Docling rich-document parser."""

from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.knowledge.infra.parsers import get_parser
from app.modules.knowledge.infra.parsers.docling import DoclingParser


class _FakeDoclingDocument:
    pages = {1: object(), 2: object()}
    tables = [object()]
    pictures = [object(), object()]

    def export_to_markdown(self) -> str:
        return "# Parsed\n\nDocling output"

    def export_to_dict(self) -> dict[str, Any]:
        return {"name": "sample.pdf", "body": {"children": []}}


class _FakeConverter:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def convert(self, source: Any, **kwargs: Any) -> SimpleNamespace:
        self.calls.append((source, kwargs))
        return SimpleNamespace(document=_FakeDoclingDocument())


def _stream_factory(*, name: str, stream: BytesIO) -> SimpleNamespace:
    return SimpleNamespace(name=name, stream=stream)


@pytest.mark.asyncio
async def test_docling_parser_uses_in_memory_stream_and_exports_full_document() -> None:
    converter = _FakeConverter()
    parser = DoclingParser(converter=converter, stream_factory=_stream_factory)

    parsed = await parser.parse(b"pdf-bytes", mime_type="application/pdf", filename="sample.pdf")

    source, options = converter.calls[0]
    assert source.name == "sample.pdf"
    assert source.stream.read() == b"pdf-bytes"
    assert options == {"max_num_pages": 200, "max_file_size": 20 * 1024 * 1024}
    assert parsed.text == "# Parsed\n\nDocling output"
    assert parsed.structured_data == {"name": "sample.pdf", "body": {"children": []}}
    assert parsed.metadata["parser"] == "docling"
    assert parsed.metadata["parser_version"] == "2.113.0"
    assert parsed.metadata["page_count"] == 2
    assert parsed.metadata["table_count"] == 1
    assert parsed.metadata["image_count"] == 2
    assert parsed.metadata["ocr_enabled"] is True


@pytest.mark.parametrize(
    "mime_type",
    [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/html",
        "image/png",
        "image/jpeg",
        "image/tiff",
    ],
)
def test_rich_document_registry_uses_docling(mime_type: str) -> None:
    assert get_parser(mime_type) is DoclingParser


@pytest.mark.asyncio
async def test_docling_parser_rejects_files_over_worker_limit() -> None:
    parser = DoclingParser(converter=_FakeConverter(), stream_factory=_stream_factory)

    with pytest.raises(ValueError, match="20 MiB"):
        await parser.parse(b"x" * (20 * 1024 * 1024 + 1), filename="too-large.pdf")
