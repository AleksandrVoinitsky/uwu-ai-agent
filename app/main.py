"""Точка входа FastAPI-приложения агента.

Собирает рантайм (LLM + промпты + инструменты) и граф в lifespan и кладёт их в
``app.state``, откуда их читают маршруты control-plane. ``create_app(runtime=…)``
позволяет подменить рантайм в тестах.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.graph.builder import build_graph
from app.graph.runtime import AgentRuntime
from app.service import build_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Собирает рантайм и граф на старте, закрывает клиент ядра на остановке."""
    settings = app.state.settings
    configure_logging(settings.log_level)

    client = None
    runtime = app.state.runtime
    if runtime is None:
        runtime, client = await build_runtime(settings)
        app.state.runtime = runtime
        app.state.client = client

    app.state.graph = build_graph(runtime)
    yield

    if client is not None:
        await client.aclose()


def create_app(runtime: AgentRuntime | None = None) -> FastAPI:
    """Собирает приложение (фабрика; ``runtime`` — для подмены в тестах)."""
    settings = get_settings()
    app = FastAPI(
        title="uwu-ai-agent",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.runtime = runtime
    app.state.client = None
    # Если рантайм передан явно — граф можно собрать сразу (без lifespan).
    app.state.graph = build_graph(runtime) if runtime is not None else None
    app.include_router(router)
    return app


app = create_app()
