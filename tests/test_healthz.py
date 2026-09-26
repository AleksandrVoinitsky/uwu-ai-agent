"""Тесты control-plane: healthz и корневой эндпоинт."""
from __future__ import annotations

from app import __version__


async def test_healthz_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "uwu-ai-agent"
    assert data["version"] == __version__


async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "uwu-ai-agent"
