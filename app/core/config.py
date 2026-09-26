"""Конфигурация сервиса агента.

Настройки читаются из переменных окружения и опционального файла ``.env``
(см. ``.env.example``). Источник истины для параметров LLM, подключения к ядру
UWU и checkpointer'а LangGraph.

См. также: :mod:`app.main`, :mod:`app.llm.factory`.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки агента (pydantic-settings, значения из env / .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Сервис ---
    environment: str = "production"
    agent_port: int = 8100
    log_level: str = "INFO"

    # --- Ядро UWU ---
    uwu_api_base_url: str = "http://localhost:8000"
    uwu_api_key: str = ""
    uwu_api_timeout_seconds: float = 30.0

    # --- LLM (OpenAI-совместимый API) ---
    llm_base_url: str | None = None
    llm_api_key: str = ""
    llm_model: str = "qwen3_30b"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1024

    # --- Checkpointer LangGraph ---
    # Пусто = in-memory (только разработка). В production — PostgreSQL.
    checkpoint_db_url: str | None = None
    checkpoint_schema: str = "agent"

    # --- Поведение агента (переопределяет настройки админки ядра) ---
    default_responder: str = "agent"
    max_history: int = 20

    @property
    def is_production(self) -> bool:
        """True, если окружение — production (для fail-fast проверок)."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Возвращает синглтон настроек (кэшируется)."""
    return Settings()
