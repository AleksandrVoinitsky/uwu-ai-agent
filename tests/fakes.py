"""Общие фейки для тестов (мок LLM, без сети и реальных вызовов)."""
from __future__ import annotations

from langchain_core.messages import AIMessage


class FakeLLM:
    """Заглушка LLM: отдаёт заданные ответы по очереди (как ``AIMessage``)."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls: list = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        content = self.responses.pop(0) if self.responses else "consultation"
        return AIMessage(content=content)


class FakeToolCallingLLM:
    """Заглушка LLM с поддержкой tool-calling.

    Отдаёт готовые ``AIMessage`` по очереди (в т.ч. с ``tool_calls``); ``bind_tools``
    фиксирует переданные инструменты и возвращает ``self``.
    """

    def __init__(self, responses: list[AIMessage] | None = None):
        self.responses = list(responses or [])
        self.calls: list = []
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0) if self.responses else AIMessage(content="нет ответа")


class MockUwuClient:
    """Заглушка клиента ядра: фиксирует одобрения, write-вызовы и запуски."""

    def __init__(self):
        self.approvals: list[dict] = []
        self.added: list[tuple] = []
        self.orders: list[tuple] = []
        self.runs: list[dict] = []

    async def create_approval(self, **payload):
        self.approvals.append(payload)
        return {"id": 1, "status": "pending"}

    async def add_to_cart(self, customer_id, nomenklatura_id, quantity):
        self.added.append((customer_id, nomenklatura_id, quantity))
        return {"ok": True}

    async def create_order(self, customer_id, items):
        self.orders.append((customer_id, items))
        return {"ok": True}

    async def post_run(self, **payload):
        self.runs.append(payload)
