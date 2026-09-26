"""Настройка логирования сервиса.

Единый формат логов для контейнера и локальной разработки. Уровень задаётся
через ``Settings.log_level`` (см. :mod:`app.core.config`).
"""
from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Инициализирует корневой логгер с единым форматом."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
