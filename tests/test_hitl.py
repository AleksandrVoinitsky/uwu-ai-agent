"""Тесты human-in-the-loop: одобрение write-действий (interrupt/resume)."""
from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.graph.builder import build_graph
from app.service import process_message, resume_graph
from tests.conftest import make_runtime
from tests.fakes import FakeToolCallingLLM, MockUwuClient


class _AddArgs(BaseModel):
    customer_id: int = Field(description="ID покупателя")
    nomenklatura_id: int = Field(description="ID товара")
    quantity: float = Field(description="количество")


def _write_tool(client):
    return StructuredTool.from_function(
        coroutine=client.add_to_cart,
        name="add_to_cart",
        description="Добавить товар в корзину",
        args_schema=_AddArgs,
    )


def _runtime(client, approved: bool):
    final = "Товар добавлен в корзину." if approved else "Действие отклонено оператором."
    llm = FakeToolCallingLLM(
        [
            AIMessage(content="add_to_cart"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add_to_cart",
                        "args": {"customer_id": 1, "nomenklatura_id": 7, "quantity": 2},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content=final),
        ]
    )
    return make_runtime(
        llm=llm,
        lc_tools=[_write_tool(client)],
        write_tool_names=frozenset({"add_to_cart"}),
        client=client,
    )


async def test_hitl_approval_pending_then_approved():
    client = MockUwuClient()
    runtime = _runtime(client, approved=True)
    graph = build_graph(runtime)

    result = await process_message(
        runtime, graph, chat_id=1, text="добавь ручку в корзину", client=client
    )
    assert result["status"] == "approval_pending"
    assert result["interrupt"]["tool_key"] == "add_to_cart"
    assert len(client.approvals) == 1
    assert client.approvals[0]["tool_key"] == "add_to_cart"
    assert not client.added  # запись ещё не выполнена

    # Оператор одобряет → возобновление и выполнение записи.
    resumed = await resume_graph(graph, chat_id=1, approved=True)
    assert resumed["final_answer"] == "Товар добавлен в корзину."
    assert client.added == [(1, 7, 2)]


async def test_hitl_rejected():
    client = MockUwuClient()
    runtime = _runtime(client, approved=False)
    graph = build_graph(runtime)

    result = await process_message(
        runtime, graph, chat_id=1, text="добавь ручку в корзину", client=client
    )
    assert result["status"] == "approval_pending"

    resumed = await resume_graph(graph, chat_id=1, approved=False)
    assert "отклонено" in resumed["final_answer"].lower()
    assert not client.added  # запись не выполнялась


async def test_audit_status_approval_pending():
    client = MockUwuClient()
    runtime = _runtime(client, approved=True)
    graph = build_graph(runtime)

    await process_message(runtime, graph, chat_id=1, text="добавь", client=client)
    assert client.runs[-1]["status"] == "approval_pending"
