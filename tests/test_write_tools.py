"""Тесты прямого исполнения write-инструментов (одобрение убрано).

Проверяют, что ``add_to_cart``/``create_order`` исполняются узлом ``call_tool``
сразу (без interrupt/resume), а ``customer_id`` подставляется из состояния чата,
а не запрашивается у LLM.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.graph.builder import build_graph
from app.service import process_message
from tests.conftest import make_runtime
from tests.fakes import FakeToolCallingLLM, MockUwuClient


async def _noop(**kwargs):
    return dict(kwargs)


class _AddArgs(BaseModel):
    nomenklatura_id: int = Field(description="ID товара")
    quantity: float = Field(description="количество")


class _OrderArgs(BaseModel):
    customer_phone: str = Field(description="номер телефона")
    items: list[dict] = Field(description="Позиции заказа")


def _tool(name: str, description: str, schema: type[BaseModel]) -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_noop, name=name, description=description, args_schema=schema
    )


async def test_add_to_cart_executes_directly_with_injected_customer():
    client = MockUwuClient()
    llm = FakeToolCallingLLM(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add_to_cart",
                        "args": {"nomenklatura_id": 7, "quantity": 2},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="Добавил 2 шт в корзину."),
        ]
    )
    runtime = make_runtime(
        llm=llm,
        lc_tools=[_tool("add_to_cart", "добавить", _AddArgs)],
        tools={"add_to_cart": client.add_to_cart},
        client=client,
    )
    graph = build_graph(runtime)

    result = await process_message(
        runtime, graph, chat_id=1, text="добавь ручку", customer_id=11, client=client
    )

    assert result["final_answer"] == "Добавил 2 шт в корзину."
    # customer_id подставлен из состояния чата (11), а не придуман моделью.
    assert client.added == [(11, 7, 2)]
    assert client.runs[-1]["status"] == "ok"


async def test_create_order_executes_directly():
    client = MockUwuClient()
    llm = FakeToolCallingLLM(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_order",
                        "args": {
                            "customer_phone": "79991112233",
                            "items": [{"name": "хлеб", "quantity": 3}],
                        },
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="Заказ оформлен."),
        ]
    )
    runtime = make_runtime(
        llm=llm,
        lc_tools=[_tool("create_order", "создать заказ", _OrderArgs)],
        tools={"create_order": client.create_order},
        client=client,
    )
    graph = build_graph(runtime)

    result = await process_message(
        runtime, graph, chat_id=1, text="оформи заказ", customer_id=11, client=client
    )

    assert result["final_answer"] == "Заказ оформлен."
    assert client.orders == [("79991112233", [{"name": "хлеб", "quantity": 3}])]


async def test_write_without_customer_asks_for_profile():
    client = MockUwuClient()
    llm = FakeToolCallingLLM(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add_to_cart",
                        "args": {"nomenklatura_id": 7, "quantity": 2},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="Нужен ваш номер телефона."),
        ]
    )
    runtime = make_runtime(
        llm=llm,
        lc_tools=[_tool("add_to_cart", "добавить", _AddArgs)],
        tools={"add_to_cart": client.add_to_cart},
        client=client,
    )
    graph = build_graph(runtime)

    result = await process_message(
        runtime, graph, chat_id=1, text="добавь ручку", customer_id=None, client=client
    )

    assert result["final_answer"] == "Нужен ваш номер телефона."
    assert client.added == []  # запись не выполнялась без покупателя
