"""Загрузка конфигурации агента (промпты и инструменты).

В норме промпты и инструменты загружаются из ядра UWU через REST API
(``UwuClient.get_prompts`` / ``get_tools``) — так бизнес-пользователь меняет
поведение без пересборки агента. Если ядро недоступно (локальная разработка/
тесты) — используется fallback из :mod:`app.config_loader.defaults`.

См. также: :mod:`app.clients.uwu`, docs/CORE_CONTRACT.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.clients.uwu import UwuClient
from app.config_loader.defaults import DEFAULT_PROMPTS, DEFAULT_TOOLS
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("app.config_loader")


@dataclass
class PromptSpec:
    """Промпт (активная версия) с параметрами сэмплирования."""

    key: str
    name: str
    template: str
    variables: list[str] = field(default_factory=list)
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class ToolSpec:
    """Инструмент (тонкая обёртка над эндпоинтом ядра)."""

    key: str
    name: str
    description: str
    endpoint: str
    method: str
    params_schema: dict = field(default_factory=dict)
    permission: str | None = None
    approval_policy: str = "auto"
    approval_threshold_amount: str | None = None
    rate_limit: int = 60


@dataclass
class AgentConfig:
    """Итоговая конфигурация агента: промпты, инструменты, параметры LLM."""

    prompts: dict[str, PromptSpec]
    tools: dict[str, ToolSpec]
    model: str
    temperature: float
    max_tokens: int


def _prompts_from_raw(raw: list[dict]) -> dict[str, PromptSpec]:
    out: dict[str, PromptSpec] = {}
    for p in raw:
        spec = PromptSpec(
            key=p["key"],
            name=p.get("name", p["key"]),
            template=p.get("template", ""),
            variables=p.get("variables") or [],
            model=p.get("model"),
            temperature=p.get("temperature"),
            max_tokens=p.get("max_tokens"),
        )
        out[spec.key] = spec
    return out


def _tools_from_raw(raw: list[dict]) -> dict[str, ToolSpec]:
    out: dict[str, ToolSpec] = {}
    for t in raw:
        spec = ToolSpec(
            key=t["key"],
            name=t.get("name", t["key"]),
            description=t.get("description", ""),
            endpoint=t.get("endpoint", ""),
            method=t.get("method", "GET"),
            params_schema=t.get("params_schema") or {},
            permission=t.get("permission"),
            approval_policy=t.get("approval_policy", "auto"),
            approval_threshold_amount=t.get("approval_threshold_amount"),
            rate_limit=t.get("rate_limit", 60),
        )
        out[spec.key] = spec
    return out


def default_config(settings: Settings) -> AgentConfig:
    """Конфигурация из локальных дефолтов (без обращения к ядру)."""
    prompts = _prompts_from_raw([{"key": k, **v} for k, v in DEFAULT_PROMPTS.items()])
    tools = _tools_from_raw([{"key": k, **v} for k, v in DEFAULT_TOOLS.items()])
    return AgentConfig(
        prompts=prompts,
        tools=tools,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


async def load_agent_config(client: UwuClient, settings: Settings) -> AgentConfig:
    """Загружает конфигурацию из ядра; при недоступности — fallback на дефолты."""
    config = default_config(settings)
    try:
        raw = await client.get_prompts()
        if raw:
            config.prompts = _prompts_from_raw(raw)
    except Exception as exc:  # noqa: BLE001 — fallback
        logger.warning("Не удалось загрузить промпты из ядра: %s", exc)
    try:
        raw = await client.get_tools()
        if raw:
            config.tools = _tools_from_raw(raw)
    except Exception as exc:  # noqa: BLE001 — fallback
        logger.warning("Не удалось загрузить инструменты из ядра: %s", exc)
    return config
