"""Тесты графа LangGraph (фаза 1 — каркас)."""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph

# checkpointer привязан к «нити» диалога (thread_id = беседа в ядре UWU).
_CFG = {"configurable": {"thread_id": "chat-1"}}


def test_graph_runs_stub():
    graph = build_graph()
    result = graph.invoke({"messages": [HumanMessage(content="Привет")]}, config=_CFG)
    assert result["intent"] == "fallback"
    assert result["final_answer"]


def test_graph_preserves_messages():
    graph = build_graph()
    result = graph.invoke({"messages": [HumanMessage(content="первое")]}, config=_CFG)
    # reducer add_messages сохраняет историю диалога в состоянии.
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == "первое"


def test_graph_node_functions_are_pure():
    from app.graph.nodes import classify_intent, generate

    assert classify_intent({}) == {"intent": "fallback"}
    assert generate({})["final_answer"]
