"""Маршруты control-plane агента.

- ``/healthz`` — для HEALTHCHECK контейнера.
- ``/webhook`` — приём входящего сообщения, запуск графа, публикация ответа.
- ``/resume`` — возобновление прерванного графа после решения по одобрению (HITL).
- ``/run`` — отладочный запуск графа (без публикации в ядро).

Рантайм и граф живут в ``request.app.state`` (собираются в lifespan, см.
:mod:`app.main`), поэтому их можно подменить в тестах.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app import __version__
from app.core.logging import get_logger
from app.service import process_message, resume_graph

router = APIRouter()
logger = get_logger("app.api")


@router.get("/healthz")
async def healthz() -> dict:
    """Проверка готовности сервиса (для Docker HEALTHCHECK)."""
    return {"status": "ok", "service": "uwu-ai-agent", "version": __version__}


@router.get("/")
async def root() -> dict:
    """Корневой эндпоинт — краткая справка о сервисе."""
    return {"service": "uwu-ai-agent", "version": __version__, "docs": "/docs"}


async def _post_answer(request: Request, chat_id: int, text: str) -> None:
    client = request.app.state.client
    if client is None:
        return
    try:
        await client.post_message(chat_id=chat_id, text=text, author="agent")
    except Exception:
        logger.warning("Не удалось опубликовать ответ в ядро", exc_info=True)


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    """Принимает входящее сообщение, выполняет граф и публикует ответ в ядро."""
    payload = await request.json()
    chat_id = payload.get("chat_id")
    text = (payload.get("text") or "").strip()
    if chat_id is None or not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chat_id and text required",
        )
    channel = payload.get("channel") or "site"
    customer_id = payload.get("customer_id")

    result = await process_message(
        request.app.state.runtime,
        request.app.state.graph,
        chat_id=int(chat_id),
        text=text,
        channel=channel,
        customer_id=customer_id,
        client=request.app.state.client,
    )

    if result.get("status") == "approval_pending":
        intr = result.get("interrupt") or {}
        await _post_answer(
            request,
            int(chat_id),
            "Запрос отправлен оператору на подтверждение — сообщу о результате.",
        )
        return {
            "status": "approval_pending",
            "chat_id": chat_id,
            "approval_id": intr.get("approval_id"),
            "tool_key": intr.get("tool_key"),
        }

    answer = result.get("final_answer") or ""
    await _post_answer(request, int(chat_id), answer)
    return {
        "status": "ok",
        "chat_id": chat_id,
        "intent": result.get("intent"),
        "answer": answer,
    }


class ResumeRequest(BaseModel):
    chat_id: int
    approved: bool


@router.post("/resume")
async def resume(payload: ResumeRequest, request: Request) -> dict:
    """Возобновляет прерванный граф после решения оператора по одобрению."""
    result = await resume_graph(
        request.app.state.graph,
        chat_id=payload.chat_id,
        approved=payload.approved,
    )
    answer = result.get("final_answer") or ""
    await _post_answer(request, payload.chat_id, answer)
    return {"status": "ok", "chat_id": payload.chat_id, "answer": answer}


class RunRequest(BaseModel):
    message: str
    chat_id: int = 0
    channel: str = "internal"


@router.post("/run")
async def run_debug(payload: RunRequest, request: Request) -> dict:
    """Отладочный запуск графа: возвращает намерение, контекст и ответ."""
    result = await process_message(
        request.app.state.runtime,
        request.app.state.graph,
        chat_id=payload.chat_id,
        text=payload.message,
        channel=payload.channel,
    )
    if result.get("status") == "approval_pending":
        return {
            "status": "approval_pending",
            "approval_id": (result.get("interrupt") or {}).get("approval_id"),
            "tool_key": (result.get("interrupt") or {}).get("tool_key"),
        }
    return {
        "intent": result.get("intent"),
        "context": result.get("context"),
        "answer": result.get("final_answer"),
    }
