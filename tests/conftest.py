"""Фикстуры тестов.

Не требуют PostgreSQL и сети: рантайм строится на дефолтной конфигурации
(``default_config``), LLM и инструменты подменяются в тестах.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config_loader.loader import default_config
from app.core.config import Settings
from app.graph.runtime import AgentRuntime
from app.main import create_app


def make_runtime(llm=None, tools=None, lc_tools=None) -> AgentRuntime:
    """Собирает рантайм на дефолтной конфигурации с подменяемыми LLM/инструментами."""
    settings = Settings(_env_file=None)
    config = default_config(settings)
    return AgentRuntime(
        llm=llm,
        prompts=config.prompts,
        tools=tools or {},
        lc_tools=lc_tools or [],
        settings=settings,
    )


@pytest.fixture
async def client():
    """ASGI-клиент (httpx) с рантаймом без LLM и пустым набором инструментов."""
    app = create_app(runtime=make_runtime())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
