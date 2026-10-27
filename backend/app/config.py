from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://trace:trace@127.0.0.1:5432/trace"
    redis_url: str = "redis://127.0.0.1:6379/0"
    ingest_enabled: bool = False
    search_enabled: bool = False
    incoming_dir: Path = Path("data/incoming")
    blob_endpoint: str = "http://127.0.0.1:9000"
    blob_bucket: str = "trace"
    blob_access_key: str = "trace-local"
    blob_secret_key: str = "trace-local-development"
    ffprobe_bin: str = "ffprobe"
    deepinfra_api_key: SecretStr | None = None
    embedding_endpoint: str = "http://127.0.0.1:8001/v1/embeddings"
    embedding_api_key: SecretStr | None = None
    visual_endpoint: str = "http://127.0.0.1:8002"

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Trace requires PostgreSQL with the psycopg driver")
        return value
