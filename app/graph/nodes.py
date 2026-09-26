"""Узлы графа LangGraph.

Фаза 1 — каркас: узлы присутствуют и проходятся, но LLM-вызовы и вызовы
инструментов подключаются в фазах 2–7 (см. ``ROADMAP.md``). Каждый узел —
чистая функция от состояния: принимает ``AgentState`` и возвращает
``dict``-частичное обновление состояния.
"""
from __future__ import annotations

from app.graph.state import AgentState

# Итоговый ответ-заглушка, пока не реализован узел генерации (фаза 2).
_STUB_ANSWER = (
    "Я — AI-ассистент UWU. Настройка ответов ещё выполняется, "
    "оператор скоро свяжется с вами."
)


def classify_intent(state: AgentState) -> dict:
    """Классифицирует намерение сообщения.

    Фаза 2: LLM-классификация по промпту ``classify_intent`` из админки ядра.
    Фаза 1: всегда ``fallback``.
    """
    return {"intent": "fallback"}


def generate(state: AgentState) -> dict:
    """Формирует итоговый ответ покупателю.

    Фаза 2: генерация по промпту ``generate`` с собранным контекстом.
    Фаза 1: статичная заглушка.
    """
    return {"final_answer": _STUB_ANSWER}


def finalize(state: AgentState) -> dict:
    """Завершает запуск: здесь будет запись ``AgentRun`` в ядро (фаза 6)."""
    return {}
