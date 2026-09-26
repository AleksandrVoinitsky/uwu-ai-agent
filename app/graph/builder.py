"""Сборка графа LangGraph.

Возвращает скомпилированный граф с узлами, замыкающими
:class:`~app.graph.runtime.AgentRuntime`. Фаза 2 — линейный маршрут
``classify_intent → retrieve_context → generate``. В фазах 5+ добавляются узлы
инструментов записи и прерывания для одобрения (interrupt).
"""
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import make_classify_intent, make_generate, make_retrieve_context
from app.graph.runtime import AgentRuntime
from app.graph.state import AgentState


def build_graph(
    runtime: AgentRuntime,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Собирает и компилирует граф агента для заданного рантайма."""
    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", make_classify_intent(runtime))
    builder.add_node("retrieve_context", make_retrieve_context(runtime))
    builder.add_node("generate", make_generate(runtime))

    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "retrieve_context")
    builder.add_edge("retrieve_context", "generate")
    builder.add_edge("generate", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
