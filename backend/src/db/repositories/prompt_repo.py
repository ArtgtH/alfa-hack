from db.models import Prompt
from db.repositories.base_repo import BaseRepository


class PromptRepository(BaseRepository[Prompt]):
    __model__ = Prompt
