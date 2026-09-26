"""Общие фейки для тестов (мок LLM, без сети и реальных вызовов)."""
from __future__ import annotations

from types import SimpleNamespace


class FakeLLM:
    """Заглушка LLM: отдаёт заданные ответы по очереди, фиксирует вызовы."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls: list = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        content = self.responses.pop(0) if self.responses else "consultation"
        return SimpleNamespace(content=content)
