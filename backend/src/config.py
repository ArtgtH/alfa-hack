from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    ADMIN_SECRET_KEY: str

    DB_NAME: str
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str

    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False
    ADD_BASE_ADMIN: bool = False

    @property
    def db_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
