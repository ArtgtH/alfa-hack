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

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_EMBED_MODEL: str = "openai/text-embedding-3-large"
    OPENROUTER_EMBED_URL: str | None = None
    OPENROUTER_HTTP_REFERER: str | None = None
    OPENROUTER_APP_TITLE: str | None = None
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_CHAT_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_CHAT_URL: str | None = None
    OPENROUTER_CHAT_TIMEOUT_SECONDS: float = 60.0

    QDRANT_URL: str | None = None
    QDRANT_COLLECTION_NAME: str = "document_chunks"
    QDRANT_BATCH_SIZE: int = 64

    MINIO_ENDPOINT: str | None = None
    MINIO_ACCESS_KEY: str | None = None
    MINIO_SECRET_KEY: str | None = None
    MINIO_BUCKET_NAME: str = "documents"
    MINIO_REGION: str | None = None
    MINIO_PUBLIC_ENDPOINT: str | None = None
    MINIO_USE_SSL: bool = False

    @property
    def db_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
