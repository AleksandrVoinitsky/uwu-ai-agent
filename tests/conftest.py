"""Фикстуры тестов.

Не требуют PostgreSQL: граф работает на in-memory checkpointer'е, а REST
проверяется через ASGI-транспорт httpx (как в ядре UWU, см. его
``tests/conftest.py``).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    """ASGI-клиент (httpx) для тестов control-plane агента."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
