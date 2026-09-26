"""Тесты графа LangGraph (фаза 2 — консультация)."""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph
from tests.conftest import make_runtime
from tests.fakes import FakeLLM

_CFG = {"configurable": {"thread_id": "chat-1"}}


async def _invoke(runtime, text: str) -> dict:
    graph = build_graph(runtime)
    return await graph.ainvoke(
        {"messages": [HumanMessage(content=text)], "chat_id": 1, "channel": "site"},
        config=_CFG,
    )


async def test_classify_via_llm():
    runtime = make_runtime(llm=FakeLLM(["stock"]))
    result = await _invoke(runtime, "есть в наличии?")
    assert result["intent"] == "stock"


async def test_classify_heuristic_without_llm():
    result = await _invoke(make_runtime(), "какой статус у заказа?")
    assert result["intent"] == "order_status"


async def test_retrieve_context_calls_search():
    calls: list[str] = []

    async def search(query: str):
        calls.append(query)
        return [{"name": "Ручка", "price": "100.00", "stock": "5"}]

    result = await _invoke(make_runtime(tools={"search_catalog": search}), "ручка")
    assert calls == ["ручка"]
    assert result["context"]["products"][0]["name"] == "Ручка"


async def test_generate_with_llm():
    llm = FakeLLM(["stock", "Да, 5 штук в наличии."])
    result = await _invoke(make_runtime(llm=llm), "есть в наличии ручка?")
    assert result["intent"] == "stock"
    assert result["final_answer"] == "Да, 5 штук в наличии."


async def test_write_intent_requires_approval():
    result = await _invoke(make_runtime(), "добавь ручку в корзину")
    assert result["intent"] == "add_to_cart"
    assert result["context"]["requires_approval"] is True


async def test_preserves_history():
    graph = build_graph(make_runtime())
    await graph.ainvoke(
        {"messages": [HumanMessage(content="первое")], "chat_id": 1}, config=_CFG
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="второе")], "chat_id": 1}, config=_CFG
    )
    # reducer add_messages сохраняет историю в рамках одной нити (thread_id).
    assert len(result["messages"]) == 2
