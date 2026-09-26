"""Маршруты control-plane агента.

``/healthz`` используется HEALTHCHECK'ом контейнера; ``/webhook`` — точка приёма
входящих сообщений из ядра (webhook-режим интеграции, §3 спецификации). В
фазах 2–7 сюда добавляются маршруты отладки/наблюдения (запуск графа, SSE).
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    """Проверка готовности сервиса (для Docker HEALTHCHECK)."""
    return {"status": "ok", "service": "uwu-ai-agent", "version": __version__}


@router.get("/")
async def root() -> dict:
    """Корневой эндпоинт — краткая справка о сервисе."""
    return {"service": "uwu-ai-agent", "version": __version__, "docs": "/docs"}


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    """Приём входящего сообщения из ядра (заглушка фазы 1).

    Фазы 2–7: запуск графа LangGraph по полученному ``chat_id``/тексту и
    публикация ответа обратно в ядро через ``UwuClient.post_message``.
    """
    payload = await request.json()
    return {
        "status": "accepted",
        "mode": "stub",
        "chat_id": payload.get("chat_id"),
    }
