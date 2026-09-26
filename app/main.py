"""Точка входа FastAPI-приложения агента.

Создаёт приложение с настроенным логированием и маршрутами control-plane.
Запуск в контейнере — через ``entrypoint.sh`` (``uvicorn app.main:app``).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация/очистка ресурсов на старте и остановке."""
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    """Собирает и возвращает приложение (фабрика для тестов)."""
    settings = get_settings()
    app = FastAPI(
        title="uwu-ai-agent",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(router)
    return app


app = create_app()
