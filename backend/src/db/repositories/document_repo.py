from typing import Sequence

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from db.models import ParsedDocument, User
from db.repositories.base_repo import BaseRepository


class ParsedDocumentRepository(BaseRepository[ParsedDocument]):
    __model__ = ParsedDocument

    async def get_all_for_user(self, user: User) -> Sequence[ParsedDocument]:
        stmt = select(ParsedDocument).where(
            or_(ParsedDocument.user_id == user.id, ParsedDocument.is_general)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_one_with_chunks_by_id(self, document_id: int) -> ParsedDocument:
        stmt = (
            select(ParsedDocument)
            .where(ParsedDocument.document_id == document_id)
            .options(selectinload(ParsedDocument.chunks))
        )
        result = await self._db.execute(stmt)
        return result.scalars().one_or_none()
