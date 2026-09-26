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
