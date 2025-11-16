from __future__ import annotations

from typing import Any

from .models import MarkdownDocument


class MegaParseClient:
    def __init__(self) -> None:
        try:
            from megaparse import MarkdownParser
        except ImportError as exc:
            raise RuntimeError(
                "megaparse package is required to parse uploaded documents. "
                "Please ensure megaparse and its dependencies are properly installed."
            ) from exc
        except Exception as exc:
            # Handle other import errors (e.g., dependency conflicts)
            raise RuntimeError(
                f"Failed to initialize megaparse parser: {exc}. "
                "This may be due to dependency version conflicts. "
                "Please check pdfminer and unstructured library versions."
            ) from exc

        try:
            self._parser = MarkdownParser()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create MarkdownParser instance: {exc}"
            ) from exc

    def parse(
        self, *, content_bytes: bytes, filename: str | None = None
    ) -> MarkdownDocument:
        parsed_document = self._parse_bytes(content_bytes, filename)
        markdown = self._extract_markdown(parsed_document)
        metadata = self._extract_metadata(parsed_document)
        return MarkdownDocument(content=markdown, metadata=metadata)

    def _parse_bytes(
        self, content_bytes: bytes, filename: str | None
    ) -> Any:
        parse_kwargs: dict[str, Any] = {}
        if filename:
            parse_kwargs["filename"] = filename

        if hasattr(self._parser, "parse_bytes"):
            return self._parser.parse_bytes(content_bytes, **parse_kwargs)

        if hasattr(self._parser, "parse"):
            return self._parser.parse(content_bytes, **parse_kwargs)

        raise RuntimeError("MegaParse parser does not expose a supported parse method")

    def _extract_markdown(self, parsed_document: Any) -> str:
        candidate_attrs = (
            "to_markdown",
            "markdown",
            "content",
            "text",
        )

        for attr_name in candidate_attrs:
            attribute = getattr(parsed_document, attr_name, None)
            if callable(attribute):
                result = attribute()
                if isinstance(result, str):
                    return result
            elif isinstance(attribute, str):
                return attribute

        if isinstance(parsed_document, str):
            return parsed_document

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
