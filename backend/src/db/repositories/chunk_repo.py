from typing import Sequence

from sqlalchemy import select

from db.models import DocumentChunk
from db.repositories.base_repo import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    __model__ = DocumentChunk

    async def get_all_by_document_id(self, document_id: int) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.id == document_id)
            .order_by(DocumentChunk.chunk_serial)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()
