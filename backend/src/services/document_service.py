from typing import Sequence

import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, ParsedDocument, DocumentChunk
from db.repositories.chunk_repo import DocumentChunkRepository
from services.document_processing import DocumentUploadPipeline, DocumentVectorManager
from services.document_processing.vector_manager import VectorSearchResult


logger = structlog.get_logger(__name__)

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

document_pipeline = DocumentUploadPipeline(max_file_size_bytes=MAX_FILE_SIZE_BYTES)
vector_manager = DocumentVectorManager()


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
    return await document_pipeline.handle(file=file, db=db, user=user)


async def search_document_chunks(
    *,
    db: AsyncSession,
    user: User,
    query: str,
    limit: int = 5,
    score_threshold: float | None = None,
    document_ids: Sequence[int] | None = None,
) -> Sequence[VectorSearchResult]:
    chunk_repo = DocumentChunkRepository(db)
    return await vector_manager.search_chunks(
        chunk_repo=chunk_repo,
        user_id=user.user_id,
        query=query,
        limit=limit,
        score_threshold=score_threshold,
        document_ids=document_ids,
    )
