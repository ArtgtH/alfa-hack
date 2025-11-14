import structlog
from sqladmin import ModelView, Admin
from sqladmin.authentication import AuthenticationBackend
from sqladmin.fields import SelectField
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request
from wtforms.validators import DataRequired

from config import settings
from db.base import session_factory
from db.models import User, Role
from db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


class GayError(Exception):
    def __str__(self):
        return "🏳️‍🌈 GayError"


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        logger.info(f"{username=}, {password=}")

        if not username or not password:
            return False

        try:
            async with session_factory() as db:
                user_repo = UserRepository(db)
                user = await user_repo.get_by_username(username)

                if user and user.verify_password(password) and user.role == Role.ADMIN:
                    request.session.update(
                        {
                            "user_id": str(user.user_id),
                            "role": "ADMIN",
                        }
                    )
                    return True

                raise GayError

        except Exception as e:
            logger.error("Error while admin login", username=username, error=str(e))

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        role = request.session.get("role")

        if user_id and role == "ADMIN":
            return True

        return False


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.role, User.created_at]
    column_searchable_list = [User.username, User.email]
    column_sortable_list = [User.created_at]
    form_excluded_columns = [User.hashed_password]

    can_create = True
    can_edit = True
    can_view_details = True

    form_overrides = {"role": SelectField}

    form_args = {
        "role": {
            "choices": [
                (Role.ADMIN, "🏳️‍🌈 Администратор"),
                (Role.USER, "👤 Пользователь"),
            ],
            "validators": [DataRequired()],
            "coerce": int,  # Ключевой момент! Преобразуем строку в число
        }
    }


def setup_admin(app, engine: AsyncEngine):
    authentication_backend = AdminAuth(secret_key=settings.ADMIN_SECRET_KEY)

    admin = Admin(
        app=app,
        engine=engine,
        authentication_backend=authentication_backend,
        title="Admin Panel",
    )

    admin.add_view(UserAdmin)
    logger.info("SQLAdmin configured successfully")
    return admin
