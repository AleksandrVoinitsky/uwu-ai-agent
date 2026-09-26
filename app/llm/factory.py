"""Фабрика LLM-моделей.

Провайдер не «зашит» в коде: используется OpenAI-совместимый API
(``ChatOpenAI``), параметры берутся из настроек (``Settings``). Это позволяет
подключить любой совместимый бэкенд, задав ``LLM_BASE_URL`` и ``LLM_API_KEY``.

См. также: :mod:`app.core.config`.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import Settings


def build_chat_model(settings: Settings) -> BaseChatModel | None:
    """Создаёт модель чата из настроек.

    Возвращает ``None``, если LLM не сконфигурирован (нет API-ключа) — в этом
    случае граф работает в режиме заглушки (фаза 1).
    """
    if not settings.llm_api_key:
        return None

    kwargs: dict = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url

    return ChatOpenAI(**kwargs)
