"""Сборка графа LangGraph.

Граф фазы 3 (tool-calling):

```
START → classify_intent → decide_action ⇄ call_tool → finalize → END
```

``decide_action`` — LLM с привязанными инструментами; если LLM вернул tool_calls —
маршрутизация в ``call_tool`` (``ToolNode``) и обратно, иначе — в ``finalize``.
"""
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.graph.nodes import make_classify_intent, make_decide_action, make_finalize
from app.graph.runtime import AgentRuntime
from app.graph.state import AgentState


def _route(state: AgentState) -> str:
    """Маршрутизация после decide_action: есть tool_calls → call_tool, иначе finalize."""
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if getattr(last, "tool_calls", None):
        return "call_tool"
    return "finalize"


def build_graph(
    runtime: AgentRuntime,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Собирает и компилирует граф агента для заданного рантайма."""
    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", make_classify_intent(runtime))
    builder.add_node("decide_action", make_decide_action(runtime))
    builder.add_node("finalize", make_finalize(runtime))

    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "decide_action")

    if runtime.lc_tools:
        builder.add_node("call_tool", ToolNode(runtime.lc_tools))
        builder.add_conditional_edges(
            "decide_action",
            _route,
            {"call_tool": "call_tool", "finalize": "finalize"},
        )
        builder.add_edge("call_tool", "decide_action")
    else:
        builder.add_edge("decide_action", "finalize")

    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
