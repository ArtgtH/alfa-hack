from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any

from .models import MarkdownDocument


class MegaParseClient:
    def __init__(self) -> None:
        try:
            from megaparse.core.megaparse import MegaParse
        except ImportError as exc:
            raise RuntimeError(
                "megaparse package is required to parse uploaded documents. "
                "Please ensure megaparse and its dependencies are properly installed."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize megaparse parser: {exc}. "
                "This may be due to dependency version conflicts. "
                "Please check pdfminer and unstructured library versions."
            ) from exc

        try:
            self._parser = MegaParse()
        except Exception as exc:
            raise RuntimeError(f"Failed to create MegaParse instance: {exc}") from exc

    async def parse(
        self, *, content_bytes: bytes, filename: str | None = None
    ) -> MarkdownDocument:
        parsed_document = await self._parse_bytes(content_bytes, filename)
        markdown = self._extract_markdown(parsed_document)
        metadata = self._extract_metadata(parsed_document)
        return MarkdownDocument(content=markdown, metadata=metadata)

    def parse_sync(self, *, content_bytes: bytes, filename: str | None = None) -> MarkdownDocument:
        """Synchronous helper for tests or scripts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            raise RuntimeError(
                "parse_sync cannot be used inside a running event loop; call `await parse(...)` instead."
            )

        return asyncio.run(self.parse(content_bytes=content_bytes, filename=filename))

    async def _parse_bytes(self, content_bytes: bytes, filename: str | None) -> Any:
        file_extension = Path(filename).suffix if filename else ""
        buffer = io.BytesIO(content_bytes)
        buffer.seek(0)

        try:
            return await self._parser.aload(file=buffer, file_extension=file_extension)
        except Exception as exc:
            raise RuntimeError(f"Failed to parse document via MegaParse: {exc}") from exc

    def _extract_markdown(self, parsed_document: Any) -> str:
        if isinstance(parsed_document, str):
            return parsed_document

        candidate_attrs = ("to_markdown", "markdown", "content", "text")
        for attr_name in candidate_attrs:
            attribute = getattr(parsed_document, attr_name, None)
            if callable(attribute):
                result = attribute()
                if isinstance(result, str):
                    return result
            elif isinstance(attribute, str):
                return attribute

        raise RuntimeError("Unable to obtain markdown content from MegaParse output")

    def _extract_metadata(self, parsed_document: Any) -> dict[str, Any] | None:
        sections = getattr(parsed_document, "sections", None)
        if not sections:
            return None

        serialized_sections: list[dict[str, Any]] = []
        for index, section in enumerate(sections):
            serialized_sections.append(
                {
                    "title": getattr(section, "title", None)
                    or getattr(section, "heading", None),
                    "level": getattr(section, "level", None)
                    or getattr(section, "depth", None),
                    "order": index,
                }
            )

        return {"sections": serialized_sections}
