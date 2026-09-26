"""Тесты оркестратора (process_message): обработка и аудит запусков."""
from __future__ import annotations

from app.graph.builder import build_graph
from app.service import process_message
from tests.conftest import make_runtime


class RecordingClient:
    """Заглушка клиента ядра, фиксирующая записанные запуски (agent_runs)."""

    def __init__(self):
        self.runs: list[dict] = []

    async def post_run(self, **payload):
        self.runs.append(payload)


async def test_process_message_writes_run():
    client = RecordingClient()
    runtime = make_runtime()
    graph = build_graph(runtime)
    result = await process_message(
        runtime, graph, chat_id=1, text="привет", client=client
    )
    assert result["final_answer"]
    assert len(client.runs) == 1
    run = client.runs[0]
    assert run["chat_id"] == 1
    assert run["trace_id"]
    assert run["status"] == "ok"
    assert run["intent"] == "consultation"
    assert run["model"]


async def test_process_message_without_client():
    runtime = make_runtime()
    graph = build_graph(runtime)
    result = await process_message(runtime, graph, chat_id=1, text="привет")
    assert result["final_answer"]
    assert result["intent"] == "consultation"
