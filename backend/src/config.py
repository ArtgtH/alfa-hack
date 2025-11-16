from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "finance"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    ADMIN_SECRET_KEY: str = "dev-admin-secret-change-in-production"

    DB_NAME: str = "finance"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False
    ADD_BASE_ADMIN: bool = False

    OPENROUTER_API_KEY: str | None = (
        "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"
    )
    OPENROUTER_EMBED_MODEL: str = "openai/text-embedding-3-large"
    OPENROUTER_EMBED_URL: str | None = None
    OPENROUTER_HTTP_REFERER: str | None = None
    OPENROUTER_APP_TITLE: str | None = None
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_CHAT_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_CHAT_URL: str | None = None
    OPENROUTER_CHAT_TIMEOUT_SECONDS: float = 60.0

    QDRANT_URL: str | None = "http://178.72.149.75:6333"
    QDRANT_COLLECTION_NAME: str = "document_chunks"
    QDRANT_BATCH_SIZE: int = 64

    MINIO_ENDPOINT: str | None = "http://178.72.149.75:9000"
    MINIO_ACCESS_KEY: str | None = "minioadmin"
    MINIO_SECRET_KEY: str | None = "minioadmin"
    MINIO_BUCKET_NAME: str = "documents"
    MINIO_REGION: str | None = None
    MINIO_PUBLIC_ENDPOINT: str | None = "http://178.72.149.75:9001"
    MINIO_USE_SSL: bool = False

    @property
    def db_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
