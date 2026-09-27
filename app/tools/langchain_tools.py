"""LangChain-инструменты агента (для tool-calling в LLM).

Оборачивают tool-friendly эндпоинты ядра в ``StructuredTool`` с типизированной
схемой аргументов, чтобы LLM мог выбирать инструмент и передавать аргументы.
Имена/описания берутся из реестра инструментов ядра (``agent_tools``).

Исполнение инструментов выполняет узел ``call_tool`` графа (см.
:mod:`app.graph.nodes`) через ``runtime.tools`` — LangChain-обёртки здесь задают
только **схему** для LLM. Для инструментов, привязанных к покупателю
(``get_cart``/``add_to_cart``/``create_order``), ``customer_id`` не входит в
схему: он подставляется из состояния чата, а не запрашивается у модели.

См. также: :mod:`app.tools.uwu_tools`, docs/CORE_CONTRACT.md.
"""
from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.clients.uwu import UwuClient
from app.config_loader.loader import ToolSpec


class SearchCatalogArgs(BaseModel):
    query: str = Field(description="Поисковый запрос: название или артикул товара")


class GetStockArgs(BaseModel):
    nomenklatura_id: int = Field(description="ID товара (номенклатуры)")


class GetCartArgs(BaseModel):
    """Корзина покупателя — без аргументов (покупатель берётся из чата)."""


class GetZakazArgs(BaseModel):
    order_id: int = Field(description="ID заявки/заказа покупателя")


class AddToCartArgs(BaseModel):
    nomenklatura_id: int = Field(description="ID товара (номенклатуры)")
    quantity: float = Field(description="Количество")


class CreateOrderArgs(BaseModel):
    items: list[dict] = Field(description="Позиции заказа: [{nomenklatura_id, quantity}]")


def _make_tool(name: str, description: str, args_schema: type[BaseModel]) -> BaseTool:
    """Создаёт StructuredTool только со схемой (исполнение — через runtime.tools)."""
    return StructuredTool.from_function(
        coroutine=_noop,
        name=name,
        description=description,
        args_schema=args_schema,
    )


async def _noop(**kwargs: object) -> dict:
    """Заглушка: реальное исполнение выполняет узел ``call_tool`` графа."""
    return dict(kwargs)


def build_langchain_tools(
    client: UwuClient, tool_specs: dict[str, ToolSpec]
) -> list[BaseTool]:
    """Собирает LangChain-инструменты (схемы для LLM) из реестра ядра.

    Инструмент создаётся только если он включён в реестре (ключ присутствует в
    ``tool_specs``). Ключи совпадают с ``agent_tools.key`` ядра. Возвращает
    read- и write-инструменты единым списком (одобрение оператора убрано).
    """
    tools: list[BaseTool] = []

    if "search_catalog" in tool_specs:
        tools.append(
            _make_tool("search_catalog", tool_specs["search_catalog"].description, SearchCatalogArgs)
        )
    if "get_stock" in tool_specs:
        tools.append(
            _make_tool("get_stock", tool_specs["get_stock"].description, GetStockArgs)
        )
    if "get_cart" in tool_specs:
        tools.append(
            _make_tool("get_cart", tool_specs["get_cart"].description, GetCartArgs)
        )
    if "get_order_status" in tool_specs:
        tools.append(
            _make_tool("get_order_status", tool_specs["get_order_status"].description, GetZakazArgs)
        )
    if "add_to_cart" in tool_specs:
        tools.append(
            _make_tool("add_to_cart", tool_specs["add_to_cart"].description, AddToCartArgs)
        )
    if "create_order" in tool_specs:
        tools.append(
            _make_tool("create_order", tool_specs["create_order"].description, CreateOrderArgs)
        )

    return tools
