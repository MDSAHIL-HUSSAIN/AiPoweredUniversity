"""Environment-backed configuration for the LangGraph workflow."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkflowSettings(BaseSettings):
    """Runtime settings shared by the LLM adapter and graph nodes."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mock_llm: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_keep_alive: str = "10m"
    ollama_num_ctx: int = Field(default=8_192, ge=2_048)
    ollama_num_predict: int = Field(default=512, ge=64)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    router_max_attempts: int = Field(default=2, ge=1, le=3)
    top_k: int = Field(default=5, ge=1, le=20)
    sqlite_path: str = "./data/runtime/university.db"
    chroma_path: str = "./data/runtime/chroma"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> WorkflowSettings:
    return WorkflowSettings()

