from db.models import Message
from db.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[Message]):
    __model__ = Message
