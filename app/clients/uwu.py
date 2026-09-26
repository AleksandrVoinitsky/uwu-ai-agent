"""Клиент REST API ядра UWU.

Агент — *клиент* ядра, а не часть учётного процесса. Этот клиент — тонкая
обёртка над эндпоинтами ``/api/agent/*`` (см. §9 спецификации ``docs/ai-agent.md``
в ядре UWU). Он не пишет в БД напрямую и не дублирует бизнес-логику.

Эндпоинты ядра, потребляемые агентом, реализуются в ядре на следующем этапе;
здесь зафиксирован контракт (методы, пути, авторизация), по которому пишутся
контракт-тесты.
"""
from __future__ import annotations

from typing import Any, Self

import httpx


class UwuClient:
    """Асинхронный HTTP-клиент ядра UWU с API-key авторизацией агента."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # --- Конфигурация (кэш агента) ---

    async def get_prompts(self) -> list[dict]:
        """Активные промпты (для кэша агента)."""
        return await self._get_json("/api/agent/prompts")

    async def get_tools(self) -> list[dict]:
        """Включённые инструменты (для регистрации в LLM)."""
        return await self._get_json("/api/agent/tools")

    # --- Сообщения ---

    async def get_inbox(self) -> list[dict]:
        """Непрочитанные входящие (polling-режим)."""
        return await self._get_json("/api/agent/inbox")

    async def post_message(
        self,
        chat_id: int,
        text: str,
        *,
        author: str = "agent",
        agent_run_id: int | None = None,
    ) -> dict:
        """Публикует ответ агента в чат (``author="agent"``)."""
        return await self._post_json(
            "/api/agent/messages",
            {"chat_id": chat_id, "text": text, "author": author, "agent_run_id": agent_run_id},
        )

    async def get_context(self, chat_id: int) -> dict:
        """Сводка контекста: профиль/корзина/история покупателя."""
        return await self._get_json(f"/api/agent/context/{chat_id}")

    # --- Одобрения (human-in-the-loop) ---

    async def create_approval(self, **payload: Any) -> dict:
        """Создаёт запрос одобрения действия."""
        return await self._post_json("/api/agent/approvals", payload)

    async def decide_approval(
        self,
        approval_id: int,
        *,
        approve: bool,
        decided_by: str | None = None,
    ) -> dict:
        """Решение оператора по одобрению (вызывается со стороны ядра/админки)."""
        return await self._post_json(
            f"/api/agent/approvals/{approval_id}/decide",
            {"approved": approve, "decided_by": decided_by},
        )

    # --- Аудит запусков ---

    async def post_run(self, **payload: Any) -> dict:
        """Пишет результат запуска в журнал ядра (``agent_runs``)."""
        return await self._post_json("/api/agent/runs", payload)

    # --- Низкоуровневые помощники ---

    async def _get_json(self, path: str) -> Any:
        resp = await self._client.get(path)
        resp.raise_for_status()
        return resp.json()

    async def _post_json(self, path: str, payload: dict) -> Any:
        resp = await self._client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()
