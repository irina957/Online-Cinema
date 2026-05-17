from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BASE_DIR: Path = Path(__file__).parent.parent.parent

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_DB_PORT: int = 5432
    POSTGRES_DB: str = "cinema_db"

    SECRET_KEY_ACCESS: str
    SECRET_KEY_REFRESH: str
    JWT_SIGNING_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"

    MAIL_USERNAME: str = "testuser"
    MAIL_PASSWORD: str = "testpassword"
    MAIL_FROM: str = "admin@online-cinema.com"
    MAIL_PORT: int = 1025
    MAIL_SERVER: str = "mailhog"
    MAIL_FROM_NAME: str = "Online_Cinema_Admin"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin123"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_DB_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
