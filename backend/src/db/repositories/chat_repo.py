from db.models import Chat
from db.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[Chat]):
    __model__ = Chat
