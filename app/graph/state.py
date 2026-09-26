"""Состояние графа LangGraph.

Схема состояния едина для всех запусков и соответствует §4.1 спецификации
агента в ядре UWU (``docs/ai-agent.md``). Поля, которые фазы 2–7 ещё не
заполняют, объявлены заранее, чтобы не менять сигнатуру состояния позже.
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ToolCall(TypedDict, total=False):
    """Один вызванный инструмент и его аргументы."""

    tool: str
    args: dict


class ApprovalRequest(TypedDict, total=False):
    """Запрос на одобрение (human-in-the-loop)."""

    tool_key: str
    payload: dict


class AgentState(TypedDict, total=False):
    """Состояние одного запуска агента (см. §4.1 спецификации)."""

    # Диалог: сообщения LangChain (reducer add_messages склеивает историю).
    messages: Annotated[list[BaseMessage], add_messages]
    # Контекст ядра UWU.
    chat_id: int | None
    channel: str
    customer_id: int | None
    # Результаты работы узлов.
    intent: str | None
    context: dict
    tool_calls: list[ToolCall]
    pending_approval: ApprovalRequest | None
    final_answer: str | None
    # Аудит / трассировка.
    run_id: str | None
    trace_id: str | None
