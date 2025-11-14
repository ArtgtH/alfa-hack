import enum
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import String, TypeDecorator, Integer
from sqlalchemy.orm import Mapped, mapped_column, synonym

from db.base import Base, int_pk


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class IntEnum(TypeDecorator):
    impl = Integer

    def __init__(self, enumtype, *args, **kwargs):
        super(IntEnum, self).__init__(*args, **kwargs)
        self._enumtype = enumtype

    def process_bind_param(self, value, dialect):
        if isinstance(value, int):
            return value

        return value.value

    def process_result_value(self, value, dialect):
        return self._enumtype(value)


class Role(enum.IntEnum):
    ADMIN = 1
    USER = 0


class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int_pk] = mapped_column()
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(IntEnum(Role), default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now())

    id: Mapped[int] = synonym("user_id")

    def verify_password(self, plain_password: str) -> bool:
        return pwd_context.verify(plain_password, self.hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)
