from db.models import Message
from db.repositories.base_repo import BaseRepository


class MessageRepository(BaseRepository[Message]):
    __model__ = Message
