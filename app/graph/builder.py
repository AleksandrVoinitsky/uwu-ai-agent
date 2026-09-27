"""Сборка графа LangGraph.

Граф консультанта-сборщика заказов (без human-in-the-loop):

```
START → classify_intent → decide_action ⇄ call_tool → finalize → END
```

Все инструменты (чтение и запись) исполняются напрямую узлом ``call_tool``;
одобрение оператора убрано — агент собирает заказы/корзину сам, но документ
создаётся в статусе ``DRAFT`` (проведение остаётся за оператором).
"""
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    make_call_tool,
    make_classify_intent,
    make_decide_action,
    make_finalize,
)
from app.graph.runtime import AgentRuntime
from app.graph.state import AgentState


def build_graph(
    runtime: AgentRuntime,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Собирает и компилирует граф агента для заданного рантайма."""

    def _route(state: AgentState) -> str:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        tool_calls = getattr(last, "tool_calls", None)
        return "call_tool" if tool_calls else "finalize"

    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", make_classify_intent(runtime))
    builder.add_node("decide_action", make_decide_action(runtime))
    builder.add_node("call_tool", make_call_tool(runtime))
    builder.add_node("finalize", make_finalize(runtime))

    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "decide_action")
    builder.add_conditional_edges(
        "decide_action",
        _route,
        {"call_tool": "call_tool", "finalize": "finalize"},
    )
    builder.add_edge("call_tool", "decide_action")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
