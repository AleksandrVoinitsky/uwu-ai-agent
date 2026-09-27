"""Тесты потокового ответа (SSE)."""
from __future__ import annotations

from app.graph.builder import build_graph
from app.service import stream_message
from tests.conftest import make_runtime


async def _collect(text: str) -> str:
    graph = build_graph(make_runtime())
    chunks = [c async for c in stream_message(graph, chat_id=1, text=text)]
    return "".join(chunks)


async def test_stream_yields_final_answer():
    answer = await _collect("добавь ручку в корзину")
    assert "Уточните" in answer


async def test_stream_lists_products():
    async def search(query: str):
        return [{"name": "Ручка", "price": "100.00", "stock": "5"}]

    graph = build_graph(make_runtime(tools={"search_catalog": search}))
    chunks = [c async for c in stream_message(graph, chat_id=1, text="ручка")]
    answer = "".join(chunks)
    assert "Ручка" in answer
