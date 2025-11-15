from db.models import ParsedDocument
from db.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[ParsedDocument]):
    __model__ = ParsedDocument
