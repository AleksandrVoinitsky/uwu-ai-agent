"""Рантайм-зависимости графа: LLM, промпты, инструменты, настройки.

Узлы графа — чистые функции, которые получают эти зависимости через замыкание
(см. :mod:`app.graph.builder`). Это позволяет тестировать узлы изолированно,
подставляя мок LLM и мок-инструменты.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.config_loader.loader import PromptSpec
from app.core.config import Settings
from app.tools.uwu_tools import ToolFn


@dataclass
class AgentRuntime:
    """Набор зависимостей, доступных узлам графа."""

    llm: BaseChatModel | None
    prompts: dict[str, PromptSpec]
    tools: dict[str, ToolFn]
    settings: Settings
    # LangChain-инструменты для tool-calling (регистрируются в LLM).
    lc_tools: list[BaseTool] = field(default_factory=list)


def render_prompt(template: str, **values: object) -> str:
    """Подставляет значения в плейсхолдеры ``{key}`` промпта.

    Подставляет только переданные ключи и оставляет остальные плейсхолдеры
    нетронутыми (безопасно при неполном наборе переменных).
    """
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value))
    return result
