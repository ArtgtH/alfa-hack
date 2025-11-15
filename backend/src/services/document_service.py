from typing import Sequence

import structlog
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_413_REQUEST_ENTITY_TOO_LARGE

from db.models import User, ParsedDocument, DocumentChunk
from db.repositories.chunk_repo import DocumentChunkRepository
from db.repositories.document_repo import ParsedDocumentRepository
from services.qdrant.qdrant_test import vectorize
from services.s3.s3_test import upload_to_s3


logger = structlog.get_logger(__name__)

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


async def get_chunks_for_document(
    db: AsyncSession, document_id: int
) -> Sequence[DocumentChunk]:
    if not (
        chunks := await DocumentChunkRepository(db).get_all_by_document_id(document_id)
    ):
        logger.error(f"ParsedDocument with id {document_id} not found")
        return []

    return chunks


async def process_document(
    file: UploadFile, db: AsyncSession, user: User
) -> ParsedDocument:
    filename = file.filename
    content_bytes = await file.read()

    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Even your mom is smaller",
        )

    minio_url = await upload_to_s3(content_bytes, filename, user)

    # я не ебу как и что парсить
    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="File content is not valid UTF-8 text",
        )

    chunks = await vectorize(content_str)
    doc_repo = ParsedDocumentRepository(db)
    chunk_repo = DocumentChunkRepository(db)

    try:
        document = ParsedDocument(
            content=content_str, user=user, filename=filename, minio_url=minio_url
        )
        await doc_repo.create(document)
        await db.refresh(document)

        for chunk in chunks:
            doc_chunk = DocumentChunk(
                chunk_content=chunk.chunk_content,
                chunk_serial=chunk.chunk_serial,
                document=document,
            )
            await chunk_repo.create(doc_chunk)

    except Exception as exc:
        logger.error(
            "Failed to process document",
            length=len(content_str),
            filename=filename,
            minio_url=minio_url,
            exception=str(exc),
        )
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, detail="Failed to process document"
        )

    return document
