"""Тесты control-plane: webhook и отладочный /run."""
from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.conftest import make_runtime
from tests.fakes import FakeLLM


def _client(runtime):
    app = create_app(runtime=runtime)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_webhook_returns_answer():
    runtime = make_runtime(llm=FakeLLM(["consultation", "Здравствуйте! Чем помочь?"]))
    async with _client(runtime) as c:
        resp = await c.post(
            "/webhook", json={"chat_id": 7, "text": "привет", "channel": "site"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["chat_id"] == 7
    assert data["intent"] == "consultation"
    assert data["answer"] == "Здравствуйте! Чем помочь?"


async def test_webhook_requires_text():
    async with _client(make_runtime()) as c:
        resp = await c.post("/webhook", json={"chat_id": 7})
    assert resp.status_code == 400


async def test_run_endpoint():
    async with _client(make_runtime()) as c:
        resp = await c.post("/run", json={"message": "добавь ручку в корзину"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "add_to_cart"
    assert data["context"]["requires_approval"] is True
    assert data["answer"]
