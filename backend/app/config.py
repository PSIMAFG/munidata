from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://munidata:munidata@localhost:5432/munidata"
    DATABASE_URL_SYNC: str = "postgresql://munidata:munidata@localhost:5432/munidata"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    DATA_DIR: str = "/app/data"
    PORTAL_BASE_URL: str = "https://www.portaltransparencia.cl/PortalPdT/directorio-de-organismos-regulados/"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
