"""Инструменты агента — обёртки над tool-friendly эндпоинтами ядра.

Один инструмент = один эндпоинт ядра (принцип из docs/CORE_CONTRACT.md):
инструмент не выполняет бизнес-логику сам, а вызывает REST API ядра через
:class:`app.clients.uwu.UwuClient`. Права проверяет ядро по API-ключу.

Все инструменты выполняются **без одобрения оператора**: агент собирает заказы и
консультирует по наличию, но не проводит продажи (документ создаётся в статусе
``DRAFT``, проведение остаётся за оператором). Для инструментов, привязанных к
покупателю (``get_cart``/``add_to_cart``/``create_order``), ``customer_id``
подставляется узлом ``call_tool`` из состояния чата, а не запрашивается у LLM.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.clients.uwu import UwuClient

# Асинхронная функция-инструмент: вызывает эндпоинт ядра и возвращает JSON.
ToolFn = Callable[..., Awaitable[Any]]

# Инструменты, привязанные к покупателю: ``customer_id`` подставляется из чата.
CUSTOMER_SCOPED_TOOLS: frozenset[str] = frozenset({"get_cart", "add_to_cart", "create_order"})


def build_tools(client: UwuClient) -> dict[str, ToolFn]:
    """Собирает словарь инструментов (ключ → асинхронная функция).

    Ключи совпадают с реестром инструментов ядра (``agent_tools.key``).
    ``get_order_status`` оборачивает эндпоинт ``/api/agent/get_zakaz``.
    """
    return {
        "search_catalog": client.search_catalog,
        "get_stock": client.get_stock,
        "get_cart": client.get_cart,
        "get_order_status": client.get_zakaz,
        "add_to_cart": client.add_to_cart,
        "create_order": client.create_order,
    }
