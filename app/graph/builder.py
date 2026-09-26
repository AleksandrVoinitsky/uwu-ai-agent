"""Сборка графа LangGraph.

Возвращает скомпилированный граф с опциональным checkpointer'ом. В фазах 2–7
сюда добавляются ветвления по намерению, узлы инструментов и прерывания для
одобрения (interrupt), см. ``ROADMAP.md`` и ``docs/graph.md``.
"""
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import classify_intent, finalize, generate
from app.graph.state import AgentState


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Собирает и компилирует граф агента.

    Фаза 1 — линейный маршрут ``classify_intent -> generate -> finalize``.
    Если checkpointer не передан, используется in-memory (для тестов/разработки).
    """
    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("generate", generate)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "generate")
    builder.add_edge("generate", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
