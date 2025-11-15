from db.models import DocumentChunk
from db.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[DocumentChunk]):
    __model__ = DocumentChunk
