from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://trace:trace@127.0.0.1:5432/trace"
    redis_url: str = "redis://127.0.0.1:6379/0"
    ingest_enabled: bool = False
    search_enabled: bool = False
    auth_enabled: bool = False  # Set True to enforce API key authentication
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

    # ---------------------------------------------------------------------------
    # LLM Generation settings (Ollama — local, free, $0.00)
    # ---------------------------------------------------------------------------
    # llm_enabled: Set True to use Ollama LLM for grounded answer generation.
    #   Falls back to template generator automatically if Ollama is unreachable.
    # llm_endpoint: Ollama API base URL (default: http://localhost:11434).
    #   Inside Docker Compose use http://host.docker.internal:11434
    # llm_model: Any model pulled via `ollama pull <model>`.
    #   Recommended (smallest/fastest on RTX 4050 6 GB VRAM):
    #     gemma2:2b    (~1.6 GB VRAM) — Google Gemma 2 2B, best quality/speed ratio
    #     llama3.2:3b  (~2.0 GB VRAM) — Meta Llama 3.2 3B
    #     phi3:mini    (~2.3 GB VRAM) — Microsoft Phi-3 Mini
    #     mistral:7b   (~4.1 GB VRAM) — Mistral 7B (larger, higher quality)
    # llm_timeout: Max seconds to wait for Ollama to respond.
    llm_enabled: bool = True
    llm_endpoint: str = "http://localhost:11434"
    llm_model: str = "llama3.2:3b"
    llm_timeout: float = 60.0

    # Optional local-only video understanding and retrieval stages. These remain
    # off until model/runtime setup and corpus indexing receive explicit approval.
    ivp_ai_enabled: bool = False
    ivp_caption_model: str = "llava:7b"
    asr_model: str = "large-v3"
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"
    query_analysis_enabled: bool = False
    rerank_enabled: bool = False
    visual_segment_fusion_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Trace requires PostgreSQL with the psycopg driver")
        return value
