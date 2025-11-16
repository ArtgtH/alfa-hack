from __future__ import annotations

import asyncio
import importlib
import io
import os
from typing import Any, Sequence

import structlog
from unstructured.documents.elements import Element, ListItem, NarrativeText, Table, Text, Title
from unstructured.partition.auto import partition

from .models import MarkdownDocument


logger = structlog.get_logger(__name__)
_TRUE_VALUES = {"1", "true", "yes", "on"}


class UnstructuredDocumentParser:
    """Parse binary office documents into Markdown using `unstructured` best practices."""

    def __init__(
        self,
        *,
        strategy: str | None = None,
        fallback_strategy: str | None = None,
        enable_hi_res: bool | None = None,
        ocr_languages: str = "rus+eng",
    ) -> None:
        env_strategy = (os.getenv("UNSTRUCTURED_PARSER_STRATEGY") or "").strip().lower()
        env_fallback = (os.getenv("UNSTRUCTURED_PARSER_FALLBACK") or "").strip().lower()
        env_hi_res = (os.getenv("UNSTRUCTURED_ENABLE_HI_RES") or "").strip().lower()

        resolved_strategy = (strategy or env_strategy or "fast").lower()
        resolved_fallback = (fallback_strategy or env_fallback or "").lower() or None

        if enable_hi_res is None:
            enable_hi_res = env_hi_res in _TRUE_VALUES

        self._ocr_languages = ocr_languages
        self._allow_hi_res = enable_hi_res
        self._strategy = resolved_strategy
        self._fallback_strategy = resolved_fallback
        self._hi_res_available = self._allow_hi_res and self._detect_hi_res_support()

        if self._strategy == "hi_res" and not self._hi_res_available:
            logger.info(
                "unstructured-hi-res-disabled",
                reason="required dependencies not installed",
                fallback="fast",
            )
            self._strategy = "fast"

    async def parse(
        self, *, content_bytes: bytes, filename: str | None = None
    ) -> MarkdownDocument:
        elements = await self._partition_elements(content_bytes=content_bytes, filename=filename)
        markdown = self._elements_to_markdown(elements)
        metadata = self._extract_metadata(elements=elements, filename=filename)
        return MarkdownDocument(content=markdown, metadata=metadata)

    def parse_sync(
        self, *, content_bytes: bytes, filename: str | None = None
    ) -> MarkdownDocument:
        """Synchronous helper for CLI scripts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            raise RuntimeError(
                "parse_sync cannot run inside an active event loop. "
                "Use `await parse(...)` instead."
            )

        return asyncio.run(self.parse(content_bytes=content_bytes, filename=filename))

    async def _partition_elements(
        self, *, content_bytes: bytes, filename: str | None
    ) -> Sequence[Element]:
        primary_strategy = self._resolve_strategy(self._strategy)

        try:
            return await asyncio.to_thread(
                self._partition_sync,
                content_bytes,
                filename,
                primary_strategy,
            )
        except Exception as primary_exc:
            fallback_strategy = self._resolve_strategy(self._fallback_strategy)
            if fallback_strategy and fallback_strategy != primary_strategy:
                logger.warning(
                    "unstructured-parse-retrying",
                    primary_strategy=primary_strategy,
                    fallback_strategy=fallback_strategy,
                    error=str(primary_exc),
                )
                try:
                    return await asyncio.to_thread(
                        self._partition_sync,
                        content_bytes,
                        filename,
                        fallback_strategy,
                    )
                except Exception as fallback_exc:
                    raise RuntimeError(
                        "Failed to parse document via unstructured. "
                        "Make sure poppler, tesseract, libmagic and ghostscript are installed."
                    ) from fallback_exc

            raise RuntimeError(
                "Failed to parse document via unstructured. "
                "Make sure poppler, tesseract, libmagic and ghostscript are installed."
            ) from primary_exc

    def _partition_sync(
        self,
        content_bytes: bytes,
        filename: str | None,
        strategy: str,
    ) -> Sequence[Element]:
        buffer = io.BytesIO(content_bytes)
        buffer.seek(0)

        return partition(
            file=buffer,
            file_filename=filename,
            include_metadata=True,
            strategy=strategy,
            ocr_languages=self._ocr_languages,
            infer_table_structure=True,
            include_page_breaks=False,
        )

    def _elements_to_markdown(self, elements: Sequence[Element]) -> str:
        lines: list[str] = []

        for element in elements:
            text = self._clean_text(element)
            if not text:
                continue

            if isinstance(element, Title):
                heading_level = self._heading_level(element)
                heading_level = max(1, min(heading_level, 6))
                lines.append(f"{'#' * heading_level} {text}")
            elif isinstance(element, ListItem):
                list_type = self._metadata_dict(element).get("list_type", "unordered")
                bullet = "1." if list_type == "ordered" else "-"
                lines.append(f"{bullet} {text}")
            elif isinstance(element, Table):
                lines.append(text)
            else:
                lines.append(text)

        return "\n\n".join(lines).strip()

    def _extract_metadata(
        self, *, elements: Sequence[Element], filename: str | None
    ) -> dict[str, Any]:
        sections: list[dict[str, Any]] = []
        order = 0

        for element in elements:
            if not isinstance(element, Title):
                continue

            text = self._clean_text(element)
            if not text:
                continue

            metadata_dict = self._metadata_dict(element)
            sections.append(
                {
                    "title": text,
                    "level": self._heading_level(element),
                    "order": order,
                    "page_number": metadata_dict.get("page_number"),
                }
            )
            order += 1

        document_metadata: dict[str, Any] = {"sections": sections}
        if filename:
            document_metadata["source_filename"] = filename

        pages = sorted(
            {
                element.metadata.page_number
                for element in elements
                if element.metadata and element.metadata.page_number is not None
            }
        )
        if pages:
            document_metadata["pages"] = pages

        return document_metadata

    def _clean_text(self, element: Element | None) -> str:
        if element is None:
            return ""

        text = ""
        if isinstance(element, (Text, NarrativeText, Title, ListItem, Table)):
            text = element.text or ""
        else:
            text = getattr(element, "text", "") or ""

        return text.strip()

    def _heading_level(self, element: Title) -> int:
        metadata_dict = self._metadata_dict(element)
        level = metadata_dict.get("heading_level")
        if isinstance(level, int):
            return level
        if isinstance(level, str) and level.isdigit():
            return int(level)
        return 2

    def _metadata_dict(self, element: Element) -> dict[str, Any]:
        metadata = getattr(element, "metadata", None)
        if metadata and hasattr(metadata, "to_dict"):
            return metadata.to_dict() or {}
        return {}

    def _resolve_strategy(self, strategy: str | None) -> str:
        if not strategy:
            return "fast"

        normalized = strategy.lower()
        if normalized == "hi_res" and not self._hi_res_available:
            logger.debug(
                "unstructured-hi-res-unavailable",
                requested_strategy=strategy,
                reason="layoutparser/torch not installed",
            )
            return "fast"

        if normalized not in {"fast", "auto", "hi_res"}:
            logger.debug("unstructured-unknown-strategy", strategy=strategy)
            return "fast"

        if normalized == "hi_res" and not self._allow_hi_res:
            return "fast"

        return normalized

    def _detect_hi_res_support(self) -> bool:
        try:
            importlib.import_module("layoutparser")
            importlib.import_module("torch")
            return True
        except ImportError:
            return False
