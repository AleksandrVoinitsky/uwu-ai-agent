"""Тесты графа LangGraph (фаза 3 — tool-calling)."""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.graph.builder import build_graph
from tests.conftest import make_runtime
from tests.fakes import FakeLLM, FakeToolCallingLLM

_CFG = {"configurable": {"thread_id": "chat-1"}}


async def _invoke(runtime, text: str) -> dict:
    graph = build_graph(runtime)
    return await graph.ainvoke(
        {"messages": [HumanMessage(content=text)], "chat_id": 1, "channel": "site"},
        config=_CFG,
    )


async def test_classify_via_llm():
    result = await _invoke(make_runtime(llm=FakeLLM(["stock"])), "есть в наличии?")
    assert result["intent"] == "stock"


async def test_classify_heuristic_without_llm():
    result = await _invoke(make_runtime(), "какой статус у заказа?")
    assert result["intent"] == "order_status"


async def test_deterministic_fallback_lists_products():
    async def search(query: str):
        return [{"name": "Ручка", "price": "100.00", "stock": "5"}]

    result = await _invoke(make_runtime(tools={"search_catalog": search}), "ручка")
    assert "Ручка" in result["final_answer"]
    assert result["context"]["products"][0]["name"] == "Ручка"


async def test_write_intent_requires_approval():
    result = await _invoke(make_runtime(), "добавь ручку в корзину")
    assert result["intent"] == "add_to_cart"
    assert result["context"]["requires_approval"] is True


async def test_tool_calling_executes_tool():
    calls: list[str] = []

    async def fake_search(query: str):
        calls.append(query)
        return [{"name": "Ручка", "price": "100.00", "stock": "5"}]

    class _Args(BaseModel):
        query: str = Field(description="поисковый запрос")

    lc_tool = StructuredTool.from_function(
        coroutine=fake_search,
        name="search_catalog",
        description="поиск товаров",
        args_schema=_Args,
    )
    llm = FakeToolCallingLLM(
        [
            # 1) classify_intent → намерение
            AIMessage(content="consultation"),
            # 2) decide_action → вызов инструмента
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_catalog", "args": {"query": "ручка"}, "id": "call-1"}
                ],
            ),
            # 3) decide_action → итоговый ответ
            AIMessage(content="Ручка стоит 100 ₽."),
        ]
    )
    result = await _invoke(make_runtime(llm=llm, lc_tools=[lc_tool]), "найди ручку")
    assert calls == ["ручка"]
    assert result["final_answer"] == "Ручка стоит 100 ₽."
    assert llm.bound_tools == [lc_tool]


async def test_tool_error_does_not_crash_graph():
    async def failing_search(query: str):
        raise RuntimeError("ядро недоступно")

    class _Args(BaseModel):
        query: str = Field(description="поисковый запрос")

    lc_tool = StructuredTool.from_function(
        coroutine=failing_search,
        name="search_catalog",
        description="поиск",
        args_schema=_Args,
    )
    llm = FakeToolCallingLLM(
        [
            AIMessage(content="consultation"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_catalog", "args": {"query": "ручка"}, "id": "call-1"}
                ],
            ),
            AIMessage(content="Не удалось получить данные, попробуйте позже."),
        ]
    )
    result = await _invoke(make_runtime(llm=llm, lc_tools=[lc_tool]), "найди ручку")
    # Ошибка инструмента не роняет граф — агент отвечает корректно.
    assert result["final_answer"] == "Не удалось получить данные, попробуйте позже."


async def test_preserves_history():
    graph = build_graph(make_runtime())
    await graph.ainvoke(
        {"messages": [HumanMessage(content="первое")], "chat_id": 1}, config=_CFG
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="второе")], "chat_id": 1}, config=_CFG
    )
    assert len(result["messages"]) >= 2
