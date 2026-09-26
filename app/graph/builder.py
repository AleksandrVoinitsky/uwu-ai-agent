"""Сборка графа LangGraph.

Граф фазы 5 (tool-calling + HITL):

```
START → classify_intent → decide_action
                             ├─ read-tool → call_tool → decide_action (цикл)
                             ├─ write-tool → request_approval (interrupt) → decide_action
                             └─ ответ → finalize → END
```

Write-инструменты (`add_to_cart`/`create_order`) маршрутизируются в
``request_approval``: создаётся ``AgentApproval`` и граф прерывается до решения
оператора; при возобновлении выполняется write или формируется отказ.
"""
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.graph.nodes import (
    make_classify_intent,
    make_decide_action,
    make_finalize,
    make_request_approval,
)
from app.graph.runtime import AgentRuntime
from app.graph.state import AgentState


def build_graph(
    runtime: AgentRuntime,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Собирает и компилирует граф агента для заданного рантайма."""
    write_names = runtime.write_tool_names
    read_tools = [t for t in runtime.lc_tools if t.name not in write_names]

    def _route(state: AgentState) -> str:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        tool_calls = getattr(last, "tool_calls", None)
        if tool_calls:
            if tool_calls[0]["name"] in write_names:
                return "request_approval"
            return "call_tool"
        return "finalize"

    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", make_classify_intent(runtime))
    builder.add_node("decide_action", make_decide_action(runtime))
    builder.add_node("request_approval", make_request_approval(runtime))
    builder.add_node("finalize", make_finalize(runtime))

    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "decide_action")

    if read_tools:
        builder.add_node("call_tool", ToolNode(read_tools))
        builder.add_conditional_edges(
            "decide_action",
            _route,
            {
                "call_tool": "call_tool",
                "request_approval": "request_approval",
                "finalize": "finalize",
            },
        )
        builder.add_edge("call_tool", "decide_action")
    else:
        builder.add_conditional_edges(
            "decide_action",
            _route,
            {"request_approval": "request_approval", "finalize": "finalize"},
        )

    # После одобрения/отказа возвращаемся к decide_action для итогового ответа.
    builder.add_edge("request_approval", "decide_action")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
