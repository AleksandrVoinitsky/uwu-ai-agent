"""Тесты клиента ядра UWU (контракт: пути, метод, авторизация)."""
from __future__ import annotations

import httpx

from app.clients.uwu import UwuClient


def test_client_builds_auth_header():
    c = UwuClient("http://core", api_key="secret")
    assert c._client.headers["Authorization"] == "Bearer secret"


async def test_get_prompts_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/agent/prompts"
        return httpx.Response(200, json=[{"key": "system"}])

    c = UwuClient(
        "http://core",
        api_key="k",
        transport=httpx.MockTransport(handler),
    )
    try:
        data = await c.get_prompts()
    finally:
        await c.aclose()
    assert data == [{"key": "system"}]


async def test_post_message_contract():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    c = UwuClient("http://core", transport=httpx.MockTransport(handler))
    try:
        await c.post_message(chat_id=7, text="привет", author="agent")
    finally:
        await c.aclose()
    assert captured["path"] == "/api/agent/messages"
