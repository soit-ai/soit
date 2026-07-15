"""Docling parser for rich document formats."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from io import BytesIO
from typing import Any

from app.modules.knowledge.infra.parsers.base import DocumentParser, ParsedDocument

DOCLING_VERSION = "2.113.0"
MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_PAGES = 200
PARSE_TIMEOUT_SECONDS = 120.0

_ocr_semaphore = asyncio.Semaphore(1)


def _build_converter() -> Any:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            RapidOcrOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            ImageFormatOption,
            PdfFormatOption,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Docling parsing requires the knowledge-worker optional dependency"
        ) from exc

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = RapidOcrOptions()
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
        }
    )


def _build_stream(*, name: str, stream: BytesIO) -> Any:
    from docling.datamodel.base_models import DocumentStream

    return DocumentStream(name=name, stream=stream)


class DoclingParser(DocumentParser):
    """Convert PDF, Office, HTML, and image documents through Docling."""

    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/html",
        "image/png",
        "image/jpeg",
        "image/tiff",
    }

    _DEFAULT_FILENAMES = {
        "application/pdf": "document.pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document.docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document.pptx",
        "text/html": "document.html",
        "image/png": "document.png",
        "image/jpeg": "document.jpg",
        "image/tiff": "document.tiff",
    }

    def __init__(
        self,
        *,
        converter: Any | None = None,
        stream_factory: Callable[..., Any] | None = None,
        timeout_seconds: float = PARSE_TIMEOUT_SECONDS,
    ) -> None:
        self._converter = converter
        self._stream_factory = stream_factory or _build_stream
        self._timeout_seconds = timeout_seconds

    async def parse(
        self,
        content: bytes,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> ParsedDocument:
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("Docling input exceeds the 20 MiB worker limit")
        resolved_mime = mime_type or "application/pdf"
        if not self.supports(resolved_mime):
            raise ValueError(f"Unsupported Docling MIME type: {resolved_mime}")
        source = self._stream_factory(
            name=filename or self._DEFAULT_FILENAMES[resolved_mime],
            stream=BytesIO(content),
        )
        converter = self._converter or _build_converter()
        started = time.perf_counter()

        async with _ocr_semaphore:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    converter.convert,
                    source,
                    max_num_pages=MAX_PAGES,
                    max_file_size=MAX_FILE_SIZE,
                ),
                timeout=self._timeout_seconds,
            )

        document = result.document
        markdown = document.export_to_markdown()
        structured = document.export_to_dict()
        pages = getattr(document, "pages", None) or {}
        tables = getattr(document, "tables", None) or []
        pictures = getattr(document, "pictures", None) or []
        metadata = {
            "parser": "docling",
            "parser_version": DOCLING_VERSION,
            "mime_type": resolved_mime,
            "filename": filename or self._DEFAULT_FILENAMES[resolved_mime],
            "char_count": len(markdown),
            "page_count": len(pages),
            "table_count": len(tables),
            "image_count": len(pictures),
            "ocr_enabled": True,
            "ocr_engine": "rapidocr",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
        title = structured.get("name") if isinstance(structured, dict) else None
        if title:
            metadata["title"] = title
        return ParsedDocument(text=markdown, metadata=metadata, structured_data=structured)

    def supports(self, mime_type: str) -> bool:
        return mime_type in self.SUPPORTED_MIME_TYPES
